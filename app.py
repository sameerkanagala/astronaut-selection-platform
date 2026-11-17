"""
Astronaut Candidate Selection Platform — Flask Web Application
================================================================
Background-thread + polling architecture (no SSE, avoids proxy buffering
on Railway/Heroku). This is a demo-only deployment — no Anthropic API key
is ever accepted from a visitor, and no model or third-party PII-detection
service is ever called. (S3 is still used for storing applications/results
— see data_loader.py — that's the only AWS service this app touches.)

The UI runs a single fixed pipeline: local, zero-cost PII redaction
(stage 0, regex-based — see pii_redaction.py), then free heuristic
scoring/analysis for the rest of the pipeline. `/api/evaluate` still
accepts a `mode` field and supports a second, purely-heuristic mode with
no redaction stage (used only if called directly, e.g. from a script) —
the frontend always sends `mode: "redaction_only"`.

Applications and results are stored in a real AWS S3 bucket dedicated to
this project (data_loader.py), with a local applications/results folder
fallback for development.

Flow:
  POST /api/evaluate  → starts background job, returns {job_id}
  GET  /api/poll/<id> → returns new events since last poll (drain queue)
  GET  /api/presets   → returns program policy presets
  GET  /api/applications → returns applicant list
  GET  /api/results   → list persisted result files
  GET  /api/results/<filename> → load a specific past run
"""
import copy
import json
import os
import traceback
import threading
import uuid
from collections import deque
from flask import Flask, render_template, request, jsonify, send_from_directory

import data_loader
from scholarship_eval.models   import DecisionOutcome, ReviewType
from scholarship_eval.policy   import PRESETS, policy_from_dict, policy_to_dict

app = Flask(__name__)

# ── In-memory job store ───────────────────────────────────────────────────────
# { job_id: { "status": "running"|"done"|"error", "queue": deque, "lock": Lock } }
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _new_job() -> str:
    job_id = uuid.uuid4().hex[:10]
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running",
            "queue":  deque(),
            "lock":   threading.Lock(),
        }
    return job_id


def _push(job_id: str, event_type: str, **data):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job:
        with job["lock"]:
            job["queue"].append({"type": event_type, **data})


def _drain(job_id: str) -> tuple[str, list]:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return "not_found", []
    with job["lock"]:
        events = list(job["queue"])
        job["queue"].clear()
        status = job["status"]
    return status, events


# ── Serialisers ───────────────────────────────────────────────────────────────

def decision_to_dict(decision) -> dict:
    sc = decision.scoring
    hr = decision.human_review
    rr = getattr(decision, "redaction_report", None)
    redacted_app = getattr(decision, "redacted_application", None)
    return {
        "app_id":            decision.application_id,
        "name":              decision.applicant_name,
        "review_type":       decision.review_type.value,
        "total_score":       round(sc.rubric_scores.total, 1),
        "rubric": {
            "academic":      round(sc.rubric_scores.academic_achievement, 1),
            "financial":     round(sc.rubric_scores.financial_need, 1),
            "leadership":    round(sc.rubric_scores.leadership_service, 1),
            "essay":         round(sc.rubric_scores.essay_quality, 1),
        },
        "confidence":        round(sc.confidence, 2),
        "confidence_level":  sc.confidence_level.value,
        "ai_recommendation": sc.ai_recommendation.value,
        "final_outcome":     decision.final_outcome.value,
        "agreed":            decision.agreed,
        "reasoning":         sc.reasoning,
        "evidence": {
            "academic":      decision.evidence.academic_strength,
            "financial":     decision.evidence.financial_need_assessment,
            "leadership":    decision.evidence.leadership_indicators,
            "community":     decision.evidence.community_impact,
            "essay":         decision.evidence.essay_quality,
            "narrative":     decision.evidence.overall_narrative,
            "strengths":     decision.evidence.key_strengths,
            "concerns":      decision.evidence.key_concerns,
        },
        "human_review": {
            "reviewer":      hr.reviewer_name,
            "outcome":       hr.outcome.value,
            "adjustment":    hr.score_adjustment,
            "notes":         hr.notes,
            "override":      hr.override_reason,
        } if hr else None,
        "signals": {
            "composite_risk":     decision.signals.composite_risk,
            "sensitivity_score":  decision.signals.sensitivity_score,
            "disagreement_score": decision.signals.disagreement_score,
            "near_cutoff":        decision.signals.near_cutoff,
            "cutoff_distance":    decision.signals.cutoff_distance,
            "rubric_variance":    decision.signals.rubric_variance,
            "sensitivity_flags":  decision.signals.sensitivity_flags,
            "disagreement_flags": decision.signals.disagreement_flags,
            "routing_rationale":  decision.signals.routing_rationale,
        } if decision.signals else None,
        "audit_trail": [
            {"step": s.step, "agent": s.agent, "summary": s.summary,
             "timestamp": s.timestamp, "metadata": s.metadata}
            for s in decision.audit_trail
        ],
        # Only populated when redaction ran (older saved result files from
        # before this demo was locked to a single always-redacting pipeline
        # may lack it — templates/index.html's Redaction tab checks for
        # that and explains why).
        "redaction": {
            "engine": getattr(rr, "engine", "stub"),
            "entity_counts": rr.entity_counts(),
            "blocked_fields": rr.blocked_fields(),
            "guardrail_intervened": rr.guardrail_intervened,
            "findings": [
                {"field": f.field, "type": f.type, "action": f.action, "match": f.match}
                for f in rr.findings
            ],
            "redacted_fields": {
                "personal_statement": redacted_app.personal_statement,
                "psychological_profile": redacted_app.psychological_profile,
                "specializations": redacted_app.specializations,
                "awards": redacted_app.awards,
            } if redacted_app else None,
        } if rr else None,
    }


def calibration_to_dict(report) -> dict:
    return {
        "total_evaluated":      report.total_evaluated,
        "reviewed_by_human":    report.reviewed_by_human,
        "agreement_rate":       report.agreement_rate,
        "disagreements":        report.disagreements,
        "avg_score_delta":      report.avg_score_delta,
        "score_variance":       report.score_variance,
        "outcome_distribution": report.outcome_distribution,
        "insights":             report.calibration_insights,
        "records": [
            {"app_id": r.application_id, "ai_outcome": r.ai_outcome.value,
             "human_outcome": r.human_outcome.value, "ai_score": r.ai_score,
             "human_score": r.human_adjusted_score, "agreed": r.agreed,
             "insight": r.insight}
            for r in report.records
        ],
    }


# ── Background worker ─────────────────────────────────────────────────────────

def _build_redaction_only_orchestrator():
    """Constructed lazily, only when a job actually runs."""
    from pii_redaction import StubPIIRedactor
    from redaction_only_orchestrator import RedactionOnlyOrchestrator

    return RedactionOnlyOrchestrator(redactor=StubPIIRedactor(), verbose=False)


def _run_job(job_id: str, mode: str, selected: list, policy):
    decision_dicts = []
    try:
        if mode == "redaction_only":
            orchestrator = _build_redaction_only_orchestrator()
            orchestrator.policy = policy
            orchestrator.scoring_agent.high_threshold = policy.confidence_high
            orchestrator.scoring_agent.low_threshold = policy.confidence_low
            orchestrator.scoring_agent.quant_weight = getattr(policy, "quant_weight", 0.50)
        else:
            from scholarship_eval.stub_agents import StubOrchestrator
            orchestrator = StubOrchestrator(verbose=False, policy=policy)

        _push(job_id, "start", total=len(selected))

        decisions = []
        for i, application in enumerate(selected):
            _push(job_id, "processing",
                  index=i + 1, total=len(selected),
                  app_id=application.id, name=application.name)

            decision = orchestrator.evaluate(application)
            decisions.append(decision)
            d = decision_to_dict(decision)
            decision_dicts.append(d)

            _push(job_id, "result", index=i + 1, total=len(selected), decision=d)

        from scholarship_eval.calibration import CalibrationSystem
        report = CalibrationSystem().analyse(decisions)
        calib_dict = calibration_to_dict(report)
        _push(job_id, "calibration", report=calib_dict)

        # ── Persist results (real S3 in production, local results/ in dev) ──
        filename = data_loader.save_results(job_id, decision_dicts, calib_dict)
        _push(job_id, "saved", filename=filename)

        _push(job_id, "done")

        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "done"

    except Exception as exc:
        _push(job_id, "error", message=str(exc), detail=traceback.format_exc())
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "error"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/about")
def about():
    return send_from_directory('static', 'about.html')


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/applications")
def list_applications():
    apps = data_loader.load_applications()
    return jsonify([
        {"id": a.id, "name": a.name, "age": a.age,
         "nationality": a.nationality,
         "stem_field": a.stem_field, "candidate_level": a.candidate_level,
         "military_background": a.military_background,
         "flight_hours": a.flight_hours, "advanced_degrees": a.advanced_degrees,
         "physical_fitness_score": a.physical_fitness_score,
         "medical_clearance": a.medical_clearance,
         "specializations": a.specializations, "prior_missions": a.prior_missions,
         "awards": a.awards,
         "personal_statement": a.personal_statement,
         "psychological_profile": a.psychological_profile}
        for a in apps
    ])


@app.route("/api/presets")
def get_presets():
    return jsonify({k: policy_to_dict(v) for k, v in PRESETS.items()})


@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    """Start a background evaluation job. Returns {job_id} immediately."""
    body    = request.json or {}
    mode    = body.get("mode", "stub")
    app_ids = body.get("app_ids", None)  # None = all applications

    # Build policy
    policy_data = body.get("policy", {})
    preset_key  = policy_data.get("program_type", "initial_screening")
    if preset_key in PRESETS:
        policy = copy.deepcopy(PRESETS[preset_key])
        for k, v in policy_data.items():
            if hasattr(policy, k) and k not in ("program_name", "program_type", "description"):
                try: setattr(policy, k, type(getattr(policy, k))(v))
                except Exception: pass
    else:
        policy = policy_from_dict(policy_data)

    selected = data_loader.load_applications(app_ids)

    if not selected:
        return jsonify({"error": "No applications found. Add applications/*.json files "
                                 "(local dev) or upload them to the S3 bucket's "
                                 "applications/ prefix."}), 400

    job_id = _new_job()
    t = threading.Thread(
        target=_run_job,
        args=(job_id, mode, selected, policy),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/poll/<job_id>")
def poll(job_id):
    """Return all queued events since the last poll, plus the job status."""
    status, events = _drain(job_id)
    if status == "not_found":
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"status": status, "events": events})


@app.route("/api/results")
def list_results():
    return jsonify(data_loader.list_results())


@app.route("/api/results/latest")
def get_latest_result():
    """Full data of the newest saved run (plus its filename), or 404."""
    data = data_loader.latest_result()
    if data is None:
        return jsonify({"error": "No saved runs yet"}), 404
    return jsonify(data)


@app.route("/api/results/<path:filename>")
def get_result(filename):
    try:
        data = data_loader.load_result(filename)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Result file not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[app] Storage mode: {data_loader.storage_mode()}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
