"""
Dual-backend data loader for the astronaut selection platform.

Real AWS S3 in production (when S3_BUCKET_NAME is set — a bucket
dedicated to this project, not shared with any sibling project), falls
back to a local applications/ folder for convenience if S3 isn't
configured. Also persists evaluation results to the same bucket under a
results/ prefix.
"""
import datetime
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from scholarship_eval.models import Application

log = logging.getLogger(__name__)

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

CACHE_TTL_SECONDS = 300
FETCH_WORKERS = 8

# Retention: only this many saved runs are kept (older ones are pruned after
# each save) and only this many are ever listed. Override with MAX_SAVED_RUNS.
try:
    MAX_SAVED_RUNS = max(1, int(os.environ.get("MAX_SAVED_RUNS", "8")))
except ValueError:
    MAX_SAVED_RUNS = 8

# Safety: prune_results() refuses to delete more than this many files in one
# call (logs an error and deletes nothing instead).
MAX_PRUNE_PER_CALL = 20

# The one definition of "a saved run file": exactly what save_results()
# writes, directly under results/. Anything else under results/ (other
# tools' outputs, nested keys, _index.json, ...) is never listed, loaded
# by name, or deleted.
RUN_FILE_RE = re.compile(r"^results_\d{8}_\d{6}_[A-Za-z0-9-]+\.json$")


def _is_run_filename(name: str) -> bool:
    return bool(RUN_FILE_RE.fullmatch(name))


def _run_key_filename(key: str) -> Optional[str]:
    """Filename if `key` is a top-level run file under results/, else None."""
    if not key.startswith("results/"):
        return None
    name = key[len("results/"):]
    return name if _is_run_filename(name) else None


_s3_client = None

# Applications cache (S3 mode only): id -> Application, plus the time it was
# last populated.
_cache_lock = threading.Lock()
_apps_cache: Dict[str, Application] = {}
_apps_listed_at: float = 0.0

# Results listing cache (S3 mode only): the assembled list, and per-object
# metadata keyed by (key, etag). Saved results are immutable, so the
# per-object entries never need expiring.
_results_list_cache: Optional[tuple] = None  # (list, built_at)
_results_meta_cache: Dict[tuple, dict] = {}

# Parsed results by filename (LRU, capped at MAX_SAVED_RUNS). Saved results
# never change, so entries only leave by eviction or pruning.
_result_cache: "OrderedDict[str, dict]" = OrderedDict()


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3", region_name=AWS_REGION,
            config=Config(max_pool_connections=32),
        )
    return _s3_client


def storage_mode() -> str:
    return "s3" if S3_BUCKET_NAME else "local"


def _application_from_dict(d: dict) -> Application:
    return Application(
        id=d["id"],
        name=d["name"],
        age=d["age"],
        nationality=d["nationality"],
        stem_field=d["stem_field"],
        candidate_level=d["candidate_level"],
        military_background=bool(d.get("military_background", False)),
        flight_hours=d["flight_hours"],
        advanced_degrees=d.get("advanced_degrees", 0),
        physical_fitness_score=d["physical_fitness_score"],
        medical_clearance=d["medical_clearance"],
        specializations=d.get("specializations", []),
        prior_missions=d.get("prior_missions", 0),
        awards=d.get("awards", []),
        personal_statement=d.get("personal_statement", ""),
        psychological_profile=d.get("psychological_profile", ""),
    )


def load_applications(app_ids: Optional[List[str]] = None) -> List[Application]:
    """Load applications from S3 if configured, else from the local
    applications/ folder. If app_ids is given, only return those, in the
    order given (falls back to id order if a requested id isn't found)."""
    if S3_BUCKET_NAME:
        return _load_from_s3(app_ids)

    apps = _load_from_local()
    if app_ids:
        by_id = {a.id: a for a in apps}
        return [by_id[i] for i in app_ids if i in by_id]
    return apps


def _fetch_application(key: str) -> Optional[Application]:
    """Fetch one applications/*.json object; None if it vanished."""
    try:
        body = _s3().get_object(Bucket=S3_BUCKET_NAME, Key=key)["Body"].read()
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise
    return _application_from_dict(json.loads(body))


def _load_from_s3(app_ids: Optional[List[str]]) -> List[Application]:
    """Serve from the in-memory cache (5-min TTL); on a miss, list the
    applications/ prefix and fetch every object concurrently.

    Note: an application's id (e.g. "IEA-001") is not its object key
    ("applications/app_001.json"), so a subset can't be fetched by key
    without first reading the objects. The whole set is small, so a miss
    loads all of it and the requested ids are filtered from the cache."""
    global _apps_listed_at
    with _cache_lock:
        if time.monotonic() - _apps_listed_at < CACHE_TTL_SECONDS:
            by_id = {a.id: a for a in _apps_cache.values()}
            return _select(by_id, app_ids)

    keys = []
    paginator = _s3().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="applications/"):
        for obj in page.get("Contents", []):
            fname = obj["Key"].rsplit("/", 1)[-1]
            if fname and fname.endswith(".json") and not fname.startswith("_"):
                keys.append(obj["Key"])
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        fetched = [a for a in pool.map(_fetch_application, keys) if a is not None]

    with _cache_lock:
        _apps_cache.clear()
        _apps_cache.update({a.id: a for a in fetched})
        _apps_listed_at = time.monotonic()
    return _select({a.id: a for a in fetched}, app_ids)


def _select(by_id: Dict[str, Application], app_ids: Optional[List[str]]) -> List[Application]:
    if app_ids:
        return [by_id[i] for i in app_ids if i in by_id]
    return sorted(by_id.values(), key=lambda a: a.id)


def _load_from_local() -> List[Application]:
    apps = []
    folder = "applications"
    if not os.path.isdir(folder):
        return apps
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        with open(os.path.join(folder, fname)) as f:
            apps.append(_application_from_dict(json.load(f)))
    return apps


def save_results(job_id: str, decision_dicts: list, calibration: Optional[dict] = None) -> str:
    """Persist a batch of already-serialized decision dicts (plus the
    calibration report for this run, if any) to results/ — S3 if
    configured, else a local results/ folder. Returns the filename
    written (not the full key)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"results_{timestamp}_{job_id[:6]}.json"
    payload = json.dumps(
        {
            "run_id": job_id,
            "timestamp": now.isoformat(),
            "applicant_count": len(decision_dicts),
            "decisions": decision_dicts,
            "calibration": calibration,
        },
        separators=(",", ":"),
    )

    if S3_BUCKET_NAME:
        _s3().put_object(
            Bucket=S3_BUCKET_NAME, Key=f"results/{filename}",
            Body=payload.encode("utf-8"), ContentType="application/json",
            # Lets list_results() avoid downloading the body.
            Metadata={
                "applicant-count": str(len(decision_dicts)),
                "run-id": job_id,
                "timestamp": now.isoformat(),
            },
        )
    else:
        os.makedirs("results", exist_ok=True)
        with open(os.path.join("results", filename), "w") as f:
            f.write(payload)

    _clear_results_cache()
    # Seed the parse cache so opening this run needs no storage read.
    _cache_result(filename, json.loads(payload))
    try:
        prune_results()
    except Exception:
        log.warning("Pruning old results failed (the save itself succeeded)", exc_info=True)

    return filename


def _normalize_meta(meta: dict, fallback_timestamp: str) -> dict:
    raw_ts = meta.get("timestamp")
    timestamp = raw_ts if isinstance(raw_ts, str) and "-" in raw_ts else fallback_timestamp
    applicant_count = meta.get("applicant_count") or len(meta.get("decisions") or [])
    return {
        "run_id": meta.get("run_id", meta.get("job_id", "—")),
        "timestamp": timestamp,
        "applicant_count": applicant_count,
    }


def _cache_result(filename: str, data: dict) -> None:
    with _cache_lock:
        _result_cache[filename] = data
        _result_cache.move_to_end(filename)
        while len(_result_cache) > MAX_SAVED_RUNS:
            _result_cache.popitem(last=False)


def load_result(filename: str) -> dict:
    """Load one specific saved results file (as returned by list_results())
    by its filename, from S3 if configured, else the local results/ folder.
    Parsed results are cached in memory (they never change). Raises
    FileNotFoundError if the file doesn't exist (e.g. it was pruned) and
    ValueError if the name isn't a run filename (also blocks ../ traversal)."""
    if not _is_run_filename(filename):
        raise ValueError("Invalid result filename")
    with _cache_lock:
        hit = _result_cache.get(filename)
        if hit is not None:
            _result_cache.move_to_end(filename)
            return hit

    if S3_BUCKET_NAME:
        try:
            body = _s3().get_object(Bucket=S3_BUCKET_NAME, Key=f"results/{filename}")["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise FileNotFoundError(filename) from e
            raise
        data = json.loads(body)
    else:
        with open(os.path.join("results", filename)) as f:
            data = json.load(f)

    _cache_result(filename, data)
    return data


def latest_result() -> Optional[dict]:
    """The newest saved run's full data (plus its "filename"), or None."""
    for item in list_results():
        try:
            return {**load_result(item["filename"]), "filename": item["filename"]}
        except FileNotFoundError:
            continue  # pruned between listing and loading
    return None


def prune_results() -> int:
    """Delete all but the newest MAX_SAVED_RUNS run files (see RUN_FILE_RE).
    Other files under results/ are never touched. Refuses (logs an error,
    deletes nothing) if more than MAX_PRUNE_PER_CALL files would go. Returns
    how many were deleted. Raises on storage errors; save_results() catches
    and logs them."""
    if S3_BUCKET_NAME:
        runs = []  # (filename, original S3 key)
        paginator = _s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="results/"):
            for obj in page.get("Contents", []):
                name = _run_key_filename(obj["Key"])
                if name:
                    runs.append((name, obj["Key"]))
    else:
        folder = "results"
        if not os.path.isdir(folder):
            return 0
        runs = [(n, os.path.join(folder, n)) for n in os.listdir(folder)
                if _is_run_filename(n) and os.path.isfile(os.path.join(folder, n))]

    runs.sort(key=lambda r: r[0], reverse=True)
    doomed = runs[MAX_SAVED_RUNS:]
    if not doomed:
        return 0
    if len(doomed) > MAX_PRUNE_PER_CALL:
        log.error("Refusing to prune %d result files (limit %d per call); "
                  "deleting nothing. Check results/ and MAX_SAVED_RUNS.",
                  len(doomed), MAX_PRUNE_PER_CALL)
        return 0

    deleted = []
    if S3_BUCKET_NAME:
        # Keys are the ones S3 returned, not rebuilt from the filename.
        resp = _s3().delete_objects(
            Bucket=S3_BUCKET_NAME,
            Delete={"Objects": [{"Key": key} for _, key in doomed], "Quiet": True},
        )
        failed = {e["Key"] for e in resp.get("Errors", [])}
        for e in resp.get("Errors", []):
            log.warning("Could not delete %s: %s %s", e.get("Key"), e.get("Code"), e.get("Message"))
        deleted = [name for name, key in doomed if key not in failed]
    else:
        for name, path in doomed:
            try:
                os.remove(path)
                deleted.append(name)
            except OSError:
                log.warning("Could not delete %s", path, exc_info=True)

    if deleted:
        gone = set(deleted)
        with _cache_lock:
            for n in gone:
                _result_cache.pop(n, None)
            for k in [k for k in _results_meta_cache if k[0].rsplit("/", 1)[-1] in gone]:
                del _results_meta_cache[k]
        _clear_results_cache()
    return len(deleted)


def _clear_results_cache():
    global _results_list_cache
    with _cache_lock:
        _results_list_cache = None


_KEY_TS_RE = re.compile(r"^results_(\d{8})_(\d{6})_")


def _result_meta_from_s3(obj: dict) -> dict:
    """Normalized metadata for one results/ object. Uses the key name for the
    timestamp and the object's user metadata (HeadObject, no body download)
    for the rest; files saved before metadata existed fall back to reading
    the body once. Cached per (key, ETag) — saved results never change."""
    cache_key = (obj["Key"], obj.get("ETag"))
    with _cache_lock:
        hit = _results_meta_cache.get(cache_key)
    if hit is not None:
        return hit

    fname = obj["Key"].rsplit("/", 1)[-1]
    fallback_ts = obj["LastModified"].isoformat()
    m = _KEY_TS_RE.match(fname)
    if m:
        try:
            fallback_ts = datetime.datetime.strptime(
                m.group(1) + m.group(2), "%Y%m%d%H%M%S"
            ).replace(tzinfo=datetime.timezone.utc).isoformat()
        except ValueError:
            pass

    s3 = _s3()
    try:
        user_meta = s3.head_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"]).get("Metadata", {})
        if "applicant-count" in user_meta:
            meta = {
                "run_id": user_meta.get("run-id", "—"),
                "timestamp": user_meta.get("timestamp", fallback_ts),
                "applicant_count": int(user_meta["applicant-count"]),
            }
        else:
            body = s3.get_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"])["Body"].read()
            meta = _normalize_meta(json.loads(body), fallback_ts)
    except Exception:
        # Don't cache a failure; show the row with what the key tells us.
        log.warning("Could not read metadata for %s", obj["Key"], exc_info=True)
        return {"run_id": "—", "timestamp": fallback_ts, "applicant_count": 0}

    with _cache_lock:
        _results_meta_cache[cache_key] = meta
    return meta


def list_results() -> List[dict]:
    """List past result files with basic metadata, newest first."""
    global _results_list_cache
    if S3_BUCKET_NAME:
        with _cache_lock:
            cached = _results_list_cache
        if cached and time.monotonic() - cached[1] < CACHE_TTL_SECONDS:
            return cached[0]

        objs = []
        paginator = _s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="results/"):
            for obj in page.get("Contents", []):
                if _run_key_filename(obj["Key"]):
                    objs.append(obj)
        # Only the newest MAX_SAVED_RUNS are listed, so only fetch those.
        objs.sort(key=lambda o: o["Key"], reverse=True)
        objs = objs[:MAX_SAVED_RUNS]
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            metas = list(pool.map(_result_meta_from_s3, objs))
        items = [
            {"filename": o["Key"].rsplit("/", 1)[-1], "size_bytes": o["Size"], **m}
            for o, m in zip(objs, metas)
        ]
        items.sort(key=lambda r: r["filename"], reverse=True)
        with _cache_lock:
            _results_list_cache = (items, time.monotonic())
        return items

    folder = "results"
    if not os.path.isdir(folder):
        return []
    items = []
    names = sorted((n for n in os.listdir(folder) if _is_run_filename(n)), reverse=True)
    for fname in names[:MAX_SAVED_RUNS]:
        path = os.path.join(folder, fname)
        meta = {}
        try:
            with open(path) as f:
                meta = json.load(f)
        except (OSError, ValueError):
            log.warning("Could not read results file %s", path, exc_info=True)
        fallback_ts = datetime.datetime.utcfromtimestamp(os.path.getmtime(path)).isoformat()
        normalized = _normalize_meta(meta, fallback_ts)
        items.append({
            "filename": fname,
            "size_bytes": os.path.getsize(path),
            **normalized,
        })
    return items
