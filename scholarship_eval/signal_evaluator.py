"""
Signal Evaluator
================
Evaluates three categories of signal for every application:

  1. AI Confidence     — how certain is the model?
  2. Decision Sensitivity — how costly is an error here?
  3. Disagreement Signals — does anything not add up?

Combines these into a composite risk score and recommends a routing tier:
  AUTO_DECISION       → low risk, high confidence, low sensitivity
  PARALLEL_REVIEW     → moderate uncertainty
  ESCALATION          → high sensitivity or disagreement detected
  SENIOR_ADJUDICATION → maximum risk or policy-mandated

This module is pure logic — no LLM calls. Works identically in stub and live modes.
"""
from dataclasses import dataclass, field
from typing import List
from math import sqrt

from .models import Evidence, ScoringResult, ReviewType, ConfidenceLevel
from .policy import ProgramPolicy

# Rubric decision boundaries (scores out of 100)
APPROVE_BOUNDARY  = 70.0
WAITLIST_BOUNDARY = 50.0

# Award sensitivity → baseline contribution to sensitivity score
_AWARD_SENSITIVITY_MAP = {"low": 0.10, "medium": 0.20, "high": 0.35}


@dataclass
class SignalEvaluation:
    """Complete signal evaluation for one application."""

    # ── Confidence ────────────────────────────────────────────────────────────
    ai_confidence:     float
    confidence_level:  str          # "high" | "medium" | "low"

    # ── Decision sensitivity ──────────────────────────────────────────────────
    sensitivity_score: float        # 0–1
    sensitivity_flags: List[str]
    near_cutoff:       bool
    cutoff_distance:   float        # points from nearest decision boundary

    # ── Disagreement signals ──────────────────────────────────────────────────
    disagreement_score:      float  # 0–1
    disagreement_flags:      List[str]
    evidence_score_mismatch: bool
    rubric_variance:         float  # std-dev of normalised rubric dimensions

    # ── Composite ─────────────────────────────────────────────────────────────
    composite_risk:    float        # 0–1, weighted combination of all signals
    recommended_route: ReviewType
    routing_rationale: str


class SignalEvaluator:
    """
    Evaluates signals for a single application given its scoring output,
    extracted evidence, and the active program policy.
    """

    def evaluate(
        self,
        scoring:  ScoringResult,
        evidence: Evidence,
        policy:   ProgramPolicy,
    ) -> SignalEvaluation:

        total = scoring.rubric_scores.total
        conf  = scoring.confidence

        # ── 1. Decision sensitivity ───────────────────────────────────────────
        cutoff_distance = min(
            abs(total - APPROVE_BOUNDARY),
            abs(total - WAITLIST_BOUNDARY),
        )
        near_cutoff = cutoff_distance <= policy.cutoff_zone_pts

        sensitivity_flags: List[str] = []
        sensitivity_score = _AWARD_SENSITIVITY_MAP.get(policy.award_sensitivity, 0.20)

        if near_cutoff:
            sensitivity_flags.append(
                f"Score {total:.1f} is within {cutoff_distance:.1f} pts of a decision boundary"
            )
            sensitivity_score += 0.35

        if policy.award_sensitivity == "high":
            sensitivity_flags.append("High-value award — elevated scrutiny baseline")
        elif policy.award_sensitivity == "medium":
            sensitivity_flags.append("Moderate award value — standard sensitivity baseline")

        if policy.require_human_near_cutoff and near_cutoff:
            sensitivity_flags.append("Policy: mandatory human review near decision boundary")

        sensitivity_score = min(1.0, sensitivity_score)

        # ── 2. Disagreement signals ───────────────────────────────────────────
        disagreement_flags: List[str] = []
        disagreement_score = 0.0

        # Evidence ↔ Score mismatch
        n_strengths = len(evidence.key_strengths) if evidence.key_strengths else 0
        n_concerns  = len(evidence.key_concerns)  if evidence.key_concerns  else 0
        # Evidence strength: +2 per strength, -1 per concern, normalised to [0,1]
        raw_ev = (n_strengths * 2 - n_concerns)
        evidence_strength = max(0.0, min(1.0, (raw_ev + 4) / 12.0))
        score_normalised  = total / 100.0
        mismatch_delta    = abs(evidence_strength - score_normalised)
        evidence_score_mismatch = mismatch_delta > policy.evidence_mismatch_threshold

        if evidence_score_mismatch:
            direction = "stronger than" if evidence_strength > score_normalised else "weaker than"
            disagreement_flags.append(
                f"Evidence appears {direction} the score suggests "
                f"(evidence={evidence_strength:.2f}, score={score_normalised:.2f}, "
                f"delta={mismatch_delta:.2f})"
            )
            disagreement_score += mismatch_delta * 0.55

        # Rubric variance (inconsistent dimension scores → ambiguous profile)
        dims = [
            scoring.rubric_scores.academic_achievement / 25.0,
            scoring.rubric_scores.financial_need        / 25.0,
            scoring.rubric_scores.leadership_service    / 25.0,
            scoring.rubric_scores.essay_quality         / 25.0,
        ]
        mean = sum(dims) / 4.0
        rubric_variance = sqrt(sum((d - mean) ** 2 for d in dims) / 4.0)

        if rubric_variance > policy.rubric_variance_threshold:
            disagreement_flags.append(
                f"High rubric variance (σ={rubric_variance:.2f}) — "
                "uneven profile may require holistic review"
            )
            disagreement_score += rubric_variance * 0.45

        # Low confidence adds to disagreement signal
        if conf < policy.confidence_low:
            disagreement_flags.append(
                f"Low model confidence ({conf:.2f}) — AI signal unreliable"
            )
            disagreement_score += (policy.confidence_low - conf) * 0.40

        disagreement_score = min(1.0, disagreement_score)

        # ── 3. Composite risk ─────────────────────────────────────────────────
        # Weights: confidence uncertainty 35%, sensitivity 35%, disagreement 30%
        confidence_risk = 1.0 - conf
        composite_risk  = (
            confidence_risk    * 0.35 +
            sensitivity_score  * 0.35 +
            disagreement_score * 0.30
        )
        composite_risk = min(1.0, composite_risk)

        # ── 4. Routing decision ───────────────────────────────────────────────
        route, rationale = self._route(
            conf, sensitivity_score, disagreement_score,
            composite_risk, near_cutoff, policy,
        )

        return SignalEvaluation(
            ai_confidence=round(conf, 3),
            confidence_level=scoring.confidence_level.value,
            sensitivity_score=round(sensitivity_score, 3),
            sensitivity_flags=sensitivity_flags,
            near_cutoff=near_cutoff,
            cutoff_distance=round(cutoff_distance, 1),
            disagreement_score=round(disagreement_score, 3),
            disagreement_flags=disagreement_flags,
            evidence_score_mismatch=evidence_score_mismatch,
            rubric_variance=round(rubric_variance, 3),
            composite_risk=round(composite_risk, 3),
            recommended_route=route,
            routing_rationale=rationale,
        )

    @staticmethod
    def _route(
        conf: float,
        sensitivity: float,
        disagreement: float,
        composite: float,
        near_cutoff: bool,
        policy: ProgramPolicy,
    ) -> tuple[ReviewType, str]:
        """Determine routing tier from signals and policy."""

        # Senior adjudication — highest risk tier
        if (policy.senior_adjudication_enabled
                and composite >= policy.senior_escalation_threshold):
            return (
                ReviewType.SENIOR_ADJUDICATION,
                f"Senior adjudication: composite risk {composite:.2f} ≥ "
                f"policy threshold {policy.senior_escalation_threshold:.2f}",
            )

        # Escalation — high sensitivity or significant disagreement
        if (composite >= policy.escalation_threshold
                or disagreement >= policy.disagreement_tolerance
                or (near_cutoff and policy.require_human_near_cutoff)):
            reasons = []
            if composite >= policy.escalation_threshold:
                reasons.append(f"composite risk {composite:.2f}")
            if disagreement >= policy.disagreement_tolerance:
                reasons.append(f"disagreement {disagreement:.2f} ≥ tolerance {policy.disagreement_tolerance:.2f}")
            if near_cutoff and policy.require_human_near_cutoff:
                reasons.append("policy requires human review near cutoff")
            return ReviewType.ESCALATION, "Escalated: " + "; ".join(reasons)

        # Auto decision — high confidence, low sensitivity, no disagreement
        if (conf >= policy.confidence_high
                and sensitivity <= policy.auto_max_sensitivity
                and disagreement < 0.20):
            return (
                ReviewType.AUTO_DECISION,
                f"Auto: confidence {conf:.2f} ≥ {policy.confidence_high:.2f}, "
                f"sensitivity {sensitivity:.2f} ≤ {policy.auto_max_sensitivity:.2f}",
            )

        # Default: parallel review
        return (
            ReviewType.PARALLEL_REVIEW,
            f"Parallel: confidence {conf:.2f}, "
            f"sensitivity {sensitivity:.2f}, "
            f"disagreement {disagreement:.2f}",
        )
