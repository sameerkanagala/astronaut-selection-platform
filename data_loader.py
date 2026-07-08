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
import os
from typing import List, Optional

import boto3

from scholarship_eval.models import Application

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_s3_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=AWS_REGION)
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
    apps = _load_from_s3() if S3_BUCKET_NAME else _load_from_local()

    if app_ids:
        by_id = {a.id: a for a in apps}
        return [by_id[i] for i in app_ids if i in by_id]
    return apps


def _load_from_s3() -> List[Application]:
    s3 = _s3()
    apps = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="applications/"):
        for obj in page.get("Contents", []):
            fname = obj["Key"].rsplit("/", 1)[-1]
            if not fname or not fname.endswith(".json") or fname.startswith("_"):
                continue
            body = s3.get_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"])["Body"].read()
            apps.append(_application_from_dict(json.loads(body)))
    return sorted(apps, key=lambda a: a.id)


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
        )
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


def list_results() -> List[dict]:
    """List past result files with basic metadata, newest first."""
    if S3_BUCKET_NAME:
        s3 = _s3()
        items = []
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="results/"):
            for obj in page.get("Contents", []):
                fname = obj["Key"].rsplit("/", 1)[-1]
                if not fname.endswith(".json"):
                    continue
                meta = {}
                try:
                    body = s3.get_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"])["Body"].read()
                    meta = json.loads(body)
                except Exception:
                    pass
                normalized = _normalize_meta(meta, obj["LastModified"].isoformat())
                items.append({
                    "filename": fname,
                    "size_bytes": obj["Size"],
                    **normalized,
                })
        items.sort(key=lambda r: r["filename"], reverse=True)
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
        except Exception:
            pass
        fallback_ts = datetime.datetime.utcfromtimestamp(os.path.getmtime(path)).isoformat()
        normalized = _normalize_meta(meta, fallback_ts)
        items.append({
            "filename": fname,
            "size_bytes": os.path.getsize(path),
            **normalized,
        })
    return items
