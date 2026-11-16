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
        indent=2,
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
        _clear_results_cache()
    else:
        os.makedirs("results", exist_ok=True)
        with open(os.path.join("results", filename), "w") as f:
            f.write(payload)

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


def load_result(filename: str) -> dict:
    """Load one specific saved results file (as returned by list_results())
    by its filename, from S3 if configured, else the local results/ folder."""
    if S3_BUCKET_NAME:
        body = _s3().get_object(Bucket=S3_BUCKET_NAME, Key=f"results/{filename}")["Body"].read()
        return json.loads(body)

    path = os.path.join("results", filename)
    with open(path) as f:
        return json.load(f)


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
                if obj["Key"].endswith(".json"):
                    objs.append(obj)
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
    for fname in sorted(os.listdir(folder), reverse=True):
        if not fname.endswith(".json"):
            continue
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
