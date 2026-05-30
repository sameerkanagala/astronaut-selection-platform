"""
Scholarship Evaluation Platform — Flask Web Application
Streams evaluation results via Server-Sent Events (SSE).
"""
import json
import os
import traceback
from flask import Flask, render_template, request, Response, stream_with_context, jsonify

from scholarship_eval.mock_data import APPLICATIONS
from scholarship_eval.models import DecisionOutcome, ReviewType

app = Flask(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def sse(event_type: str, **data) -> str:
    """Format a Server-Sent Event string."""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"


def decision_to_dict(decision) -> dict:
    """Serialise a Decision object for JSON transport."""
    sc = decision.scoring
    hr = decision.human_review
    return {
        "app_id":          decision.application_id,
        "name":            decision.applicant_name,
        "review_type":     decision.review_type.value,
        "total_score":     round(sc.rubric_scores.total, 1),
        "rubric": {
            "academic":    round(sc.rubric_scores.academic_achievement, 1),
            "financial":   round(sc.rubric_scores.financial_need, 1),
            "leadership":  round(sc.rubric_scores.leadership_service, 1),
            "essay":       round(sc.rubric_scores.essay_quality, 1),
        },
        "confidence":      round(sc.confidence, 2),
        "confidence_level": sc.confidence_level.value,
        "ai_recommendation": sc.ai_recommendation.value,
        "final_outcome":   decision.final_outcome.value,
        "agreed":          decision.agreed,
        "reasoning":       sc.reasoning,
        "evidence": {
            "academic":    decision.evidence.academic_strength,
            "financial":   decision.evidence.financial_need_assessment,
            "leadership":  decision.evidence.leadership_indicators,
            "community":   decision.evidence.community_impact,
            "essay":       decision.evidence.essay_quality,
            "narrative":   decision.evidence.overall_narrative,
            "strengths":   decision.evidence.key_strengths,
            "concerns":    decision.evidence.key_concerns,
        },
        "human_review": {
            "reviewer":    hr.reviewer_name,
            "outcome":     hr.outcome.value,
            "adjustment":  hr.score_adjustment,
            "notes":       hr.notes,
            "override":    hr.override_reason,
        } if hr else None,
        "audit_trail": [
            {
                "step":      s.step,
                "agent":     s.agent,
                "summary":   s.summary,
                "timestamp": s.timestamp,
            }
            for s in decision.audit_trail
        ],
    }


def calibration_to_dict(report) -> dict:
    """Serialise a CalibrationReport for JSON transport."""
    return {
        "total_evaluated":     report.total_evaluated,
        "reviewed_by_human":   report.reviewed_by_human,
        "agreement_rate":      report.agreement_rate,
        "disagreements":       report.disagreements,
        "avg_score_delta":     report.avg_score_delta,
        "score_variance":      report.score_variance,
        "outcome_distribution": report.outcome_distribution,
        "insights":            report.calibration_insights,
        "records": [
            {
                "app_id":       r.application_id,
                "ai_outcome":   r.ai_outcome.value,
                "human_outcome":r.human_outcome.value,
                "ai_score":     r.ai_score,
                "human_score":  r.human_adjusted_score,
                "agreed":       r.agreed,
                "insight":      r.insight,
            }
            for r in report.records
        ],
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/applications")
def list_applications():
    """Return the full list of available mock applicants."""
    return jsonify([
        {
            "id":       a.id,
            "name":     a.name,
            "gpa":      a.gpa,
            "major":    a.major,
            "year":     a.year,
            "income":   a.annual_household_income,
            "dependents": a.dependents,
            "awards":   a.awards,
            "activities": a.extracurriculars,
        }
        for a in APPLICATIONS
    ])


@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    """
    Stream evaluation results as SSE.

    Expected JSON body:
    {
        "mode":           "stub" | "live",
        "api_key":        "sk-ant-...",   // live mode only
        "model":          "claude-haiku-4-5-20251001",
        "app_ids":        ["APP-001", ...],
        "high_threshold": 0.78,
        "low_threshold":  0.50
    }
    """
    body           = request.json or {}
    mode           = body.get("mode", "stub")
    api_key        = body.get("api_key", "").strip()
    model          = body.get("model", "claude-haiku-4-5-20251001")
    app_ids        = body.get("app_ids", [a.id for a in APPLICATIONS])
    high_threshold = float(body.get("high_threshold", 0.78))
    low_threshold  = float(body.get("low_threshold",  0.50))

    # Select applications
    app_map     = {a.id: a for a in APPLICATIONS}
    selected    = [app_map[aid] for aid in app_ids if aid in app_map]

    if not selected:
        return jsonify({"error": "No valid application IDs provided"}), 400

    def generate():
        try:
            # Build orchestrator
            if mode == "live":
                if not api_key:
                    yield sse("error", message="API key is required for live mode.")
                    return
                from anthropic import Anthropic
                from scholarship_eval.orchestrator import Orchestrator
                client      = Anthropic(api_key=api_key)
                orchestrator = Orchestrator(
                    client=client,
                    model=model,
                    verbose=False,
                    high_threshold=high_threshold,
                    low_threshold=low_threshold,
                )
            else:
                from scholarship_eval.stub_agents import StubOrchestrator
                orchestrator = StubOrchestrator(
                    verbose=False,
                    high_threshold=high_threshold,
                    low_threshold=low_threshold,
                )

            yield sse("start", total=len(selected))

            decisions = []
            for i, application in enumerate(selected):
                yield sse("processing",
                          index=i + 1,
                          total=len(selected),
                          app_id=application.id,
                          name=application.name)

                decision = orchestrator.evaluate(application)
                decisions.append(decision)

                yield sse("result",
                          index=i + 1,
                          total=len(selected),
                          decision=decision_to_dict(decision))

            # Calibration
            from scholarship_eval.calibration import CalibrationSystem
            report = CalibrationSystem().analyse(decisions)
            yield sse("calibration", report=calibration_to_dict(report))
            yield sse("done")

        except Exception as exc:
            yield sse("error", message=str(exc), detail=traceback.format_exc())

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",       # prevents nginx buffering on Railway
            "Connection":        "keep-alive",
        },
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
