"""
Astronaut Candidate Selection Platform — Flask Web Application
Uses a background-thread + polling architecture for reliable delivery
on any proxy/CDN (Railway, Heroku, etc.) without SSE buffering issues.

Flow:
  POST /api/evaluate  → starts background job, returns {job_id}
  GET  /api/poll/<id> → returns new events since last poll (drain queue)
  GET  /api/presets   → returns program policy presets
  GET  /api/applications → returns applicant list
"""
import json
import os
import traceback
import threading
import uuid
from collections import deque
from flask import Flask, render_template, request, jsonify, send_from_directory

from scholarship_eval.mock_data import APPLICATIONS
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

def _run_job(job_id: str, mode: str, api_key: str, model: str,
             selected: list, policy):
    try:
        if mode == "live":
            if not api_key:
                _push(job_id, "error", message="API key required for live mode.")
                return
            from anthropic import Anthropic
            from scholarship_eval.orchestrator import Orchestrator
            client       = Anthropic(api_key=api_key)
            orchestrator = Orchestrator(client=client, model=model,
                                        policy=policy, verbose=False)
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

            _push(job_id, "result",
                  index=i + 1, total=len(selected),
                  decision=decision_to_dict(decision))

        from scholarship_eval.calibration import CalibrationSystem
        report = CalibrationSystem().analyse(decisions)
        _push(job_id, "calibration", report=calibration_to_dict(report))
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

@app.route("/api/applications")
def list_applications():
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
        for a in APPLICATIONS
    ])


@app.route("/api/presets")
def get_presets():
    return jsonify({k: policy_to_dict(v) for k, v in PRESETS.items()})


@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    """Start a background evaluation job. Returns {job_id} immediately."""
    body    = request.json or {}
    mode    = body.get("mode", "stub")
    api_key = body.get("api_key", "").strip()
    model   = body.get("model", "claude-haiku-4-5-20251001")
    app_ids = body.get("app_ids", [a.id for a in APPLICATIONS])

    # Build policy
    policy_data = body.get("policy", {})
    preset_key  = policy_data.get("program_type", "initial_screening")
    import copy
    if preset_key in PRESETS:
        policy = copy.deepcopy(PRESETS[preset_key])
        for k, v in policy_data.items():
            if hasattr(policy, k) and k not in ("program_name", "program_type", "description"):
                try: setattr(policy, k, type(getattr(policy, k))(v))
                except: pass
    else:
        policy = policy_from_dict(policy_data)

    app_map  = {a.id: a for a in APPLICATIONS}
    selected = [app_map[aid] for aid in app_ids if aid in app_map]

    if not selected:
        return jsonify({"error": "No valid application IDs provided"}), 400

    job_id = _new_job()
    t = threading.Thread(
        target=_run_job,
        args=(job_id, mode, api_key, model, selected, policy),
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


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
