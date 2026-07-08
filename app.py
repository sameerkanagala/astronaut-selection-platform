"""
Astronaut Candidate Selection Platform — Flask Web Application
================================================================
Background-thread + polling architecture (no SSE, avoids proxy buffering
on Railway/Heroku). Three run modes:

  Stub Demo       — pure heuristic simulation. No AWS calls of any kind.
  Redaction Only  — real Amazon Bedrock Guardrails redaction (stage 0),
                    then the same free stub heuristics for scoring. No
                    Claude call, no Anthropic API key needed.
  Live Claude     — real Bedrock Guardrails redaction, then real Claude
                    calls via the direct Anthropic API using a
                    user-supplied API key (unchanged from before).

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

REGION = os.environ.get("AWS_REGION", "us-east-1")

# Set ALLOW_LIVE_MODE=false on a public deployment to hide Live Claude mode
# from the UI and reject it server-side, so visitors are never invited to
# paste their own Anthropic API key into an unfamiliar public site. Stub
# Demo and Redaction Only are unaffected — neither needs a visitor-supplied
# key. Leave unset (default: enabled) for local/private use.
LIVE_MODE_ENABLED = os.environ.get("ALLOW_LIVE_MODE", "true").strip().lower() != "false"

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
        # Only populated in Redaction Only / Live Claude modes (Stub Demo
        # never touches Bedrock, so this is None there — templates/index.html's
        # Redaction tab checks for that and explains why).
        "redaction": {
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

def _build_live_orchestrator(api_key: str, model: str):
    """Constructed lazily, only when a "live" job actually runs — Stub Demo
    and Redaction Only must work without an Anthropic API key configured."""
    from anthropic import Anthropic
    from scholarship_eval.orchestrator import Orchestrator
    from pii_redaction import PIIRedactor

    guardrail_id = os.environ["GUARDRAIL_ID"]
    guardrail_version = os.environ["GUARDRAIL_VERSION"]
    client = Anthropic(api_key=api_key)
    redactor = PIIRedactor(guardrail_id=guardrail_id, guardrail_version=guardrail_version, region=REGION)
    return Orchestrator(client=client, model=model, redactor=redactor, verbose=False)


def _build_redaction_only_orchestrator():
    """Constructed lazily, same reasoning as _build_live_orchestrator. Only
    needs GUARDRAIL_ID/GUARDRAIL_VERSION/AWS credentials — no Anthropic API
    key, since this mode never calls Claude."""
    from redaction_only_orchestrator import RedactionOnlyOrchestrator
    from pii_redaction import PIIRedactor

    guardrail_id = os.environ["GUARDRAIL_ID"]
    guardrail_version = os.environ["GUARDRAIL_VERSION"]
    redactor = PIIRedactor(guardrail_id=guardrail_id, guardrail_version=guardrail_version, region=REGION)
    return RedactionOnlyOrchestrator(redactor=redactor, verbose=False)


def _run_job(job_id: str, mode: str, api_key: str, model: str, selected: list, policy):
    decision_dicts = []
    try:
        if mode == "live":
            if not api_key:
                _push(job_id, "error", message="Anthropic API key required for Live Claude mode.")
                with _jobs_lock:
                    if job_id in _jobs:
                        _jobs[job_id]["status"] = "error"
                return
            try:
                orchestrator = _build_live_orchestrator(api_key, model)
                orchestrator.policy = policy
                orchestrator.scoring_agent.high_threshold = policy.confidence_high
                orchestrator.scoring_agent.low_threshold = policy.confidence_low
            except KeyError as missing:
                _push(job_id, "error",
                      message=f"Live mode is missing required server configuration: {missing}. "
                              f"GUARDRAIL_ID / GUARDRAIL_VERSION / AWS credentials must be set as "
                              f"environment variables on this service (redaction runs on the server's "
                              f"AWS credentials, separately from your Anthropic API key).")
                with _jobs_lock:
                    if job_id in _jobs:
                        _jobs[job_id]["status"] = "error"
                return
        elif mode == "redaction_only":
            try:
                orchestrator = _build_redaction_only_orchestrator()
                orchestrator.policy = policy
                orchestrator.scoring_agent.high_threshold = policy.confidence_high
                orchestrator.scoring_agent.low_threshold = policy.confidence_low
                orchestrator.scoring_agent.quant_weight = getattr(policy, "quant_weight", 0.50)
            except KeyError as missing:
                _push(job_id, "error",
                      message=f"Redaction Only mode is missing required server configuration: {missing}. "
                              f"GUARDRAIL_ID / GUARDRAIL_VERSION / AWS credentials must be set as "
                              f"environment variables on this service (no Anthropic API key needed "
                              f"for this mode).")
                with _jobs_lock:
                    if job_id in _jobs:
                        _jobs[job_id]["status"] = "error"
                return
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


@app.route("/api/config")
def get_config():
    """Frontend feature flags. Currently just whether Live Claude mode
    (visitor-supplied Anthropic API key) is exposed on this deployment."""
    return jsonify({"live_mode_enabled": LIVE_MODE_ENABLED})


@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    """Start a background evaluation job. Returns {job_id} immediately."""
    body    = request.json or {}
    mode    = body.get("mode", "stub")
    api_key = body.get("api_key", "").strip()
    model   = body.get("model", "claude-haiku-4-5-20251001")
    app_ids = body.get("app_ids", None)  # None = all applications

    if mode == "live" and not LIVE_MODE_ENABLED:
        return jsonify({"error": "Live Claude mode is disabled on this deployment. "
                                  "Run the app locally with your own Anthropic API key "
                                  "to use it."}), 403

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


@app.route("/api/results")
def list_results():
    return jsonify(data_loader.list_results())


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
