"""
Human Review Layer
==================
Simulates human scholarship reviewers with policy-aware behaviour.

Key design: the active ProgramPolicy influences reviewer strictness.
  - high_volume  → reviewers lean generous, approve-threshold lower
  - high_dollar  → reviewers are balanced, apply higher scrutiny
  - regulatory   → reviewers are strict, approval threshold is highest
  - escalation / senior_adjudication → reviewer pool shifts toward strict/balanced

This means changing the preset or sliders produces meaningfully different
outcomes on borderline cases, not just different routing labels.
"""
import random
from .models import (Application, ScoringResult, HumanReview,
                     DecisionOutcome, ReviewType)

# Reviewer pool — each has a systematic bias and a review style
_REVIEWERS = [
    {"id": "HR-01", "name": "Dr. Amara Diallo",   "bias": +2.5, "style": "holistic"},
    {"id": "HR-02", "name": "Prof. Samuel Chen",   "bias": -2.0, "style": "strict"},
    {"id": "HR-03", "name": "Ms. Rachel Okafor",   "bias": +0.5, "style": "balanced"},
    {"id": "HR-04", "name": "Mr. David Steinberg", "bias": +1.0, "style": "merit-focused"},
    {"id": "HR-05", "name": "Dr. Fatima Al-Hassan","bias": +3.0, "style": "equity-focused"},
]

# Policy type → (approve_threshold, noise_sigma, generous_pool_weight)
# Higher approve_threshold = harder to get approved
# Higher noise = more variance in reviewer decisions
_POLICY_PARAMS = {
    "high_volume": {"approve": 65.0, "waitlist": 48.0, "noise": 2.5, "strict_weight": 0.10},
    "high_dollar": {"approve": 70.0, "waitlist": 52.0, "noise": 2.0, "strict_weight": 0.35},
    "regulatory":  {"approve": 74.0, "waitlist": 56.0, "noise": 1.5, "strict_weight": 0.55},
    "custom":      {"approve": 68.0, "waitlist": 50.0, "noise": 2.5, "strict_weight": 0.20},
}

# Escalation/senior cases use stricter reviewers regardless of policy
_ESCALATION_STRICT_WEIGHT = 0.50
_SENIOR_STRICT_WEIGHT     = 0.70


class HumanReviewLayer:
    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def review(self, application: Application, scoring: ScoringResult,
               review_type: ReviewType, policy=None) -> HumanReview:

        program_type = getattr(policy, "program_type", "custom") if policy else "custom"
        params = _POLICY_PARAMS.get(program_type, _POLICY_PARAMS["custom"])

        # Pull policy-level overrides if present
        noise_sigma  = getattr(policy, "reviewer_noise_sigma",  params["noise"])       if policy else params["noise"]
        strict_base  = getattr(policy, "reviewer_strictness",   params["strict_weight"]) if policy else params["strict_weight"]
        dis_rate     = getattr(policy, "disagreement_sim_rate",  0.25)                  if policy else 0.25

        # Escalated/senior cases always pull from stricter reviewer pool
        if review_type == ReviewType.SENIOR_ADJUDICATION:
            strict_w = max(strict_base, _SENIOR_STRICT_WEIGHT)
        elif review_type == ReviewType.ESCALATION:
            strict_w = max(strict_base, _ESCALATION_STRICT_WEIGHT)
        else:
            strict_w = strict_base

        reviewer = self._pick_reviewer(strict_w)

        # Score adjustment: bias + policy-scaled noise + contextual
        noise      = self._rng.gauss(0, noise_sigma)
        adjustment = reviewer["bias"] + noise
        adjustment += self._contextual_adjustment(application, reviewer["style"], program_type)
        adjusted   = max(0.0, min(100.0, scoring.rubric_scores.total + adjustment))

        # Policy-driven thresholds
        if adjusted >= params["approve"]:
            outcome = DecisionOutcome.APPROVED
        elif adjusted >= params["waitlist"]:
            outcome = DecisionOutcome.WAITLISTED
        else:
            outcome = DecisionOutcome.DECLINED

        ai_outcome = scoring.ai_recommendation

        # Disagreement simulation — on borderline cases, probabilistically flip outcome
        # to simulate realistic human-AI divergence at the configured rate
        is_borderline = 50 <= scoring.rubric_scores.total <= 75
        if is_borderline and outcome == ai_outcome and self._rng.random() < dis_rate:
            outcomes = [o for o in DecisionOutcome if o != outcome]
            # Flip toward waitlisted first (most realistic disagreement on borderline)
            if DecisionOutcome.WAITLISTED in outcomes:
                outcome = DecisionOutcome.WAITLISTED
            else:
                outcome = self._rng.choice(outcomes)

        override_reason = (
            self._override_reason(ai_outcome, outcome, application, reviewer["style"])
            if outcome != ai_outcome else None
        )

        return HumanReview(
            reviewer_id=reviewer["id"],
            reviewer_name=reviewer["name"],
            outcome=outcome,
            score_adjustment=round(adjustment, 1),
            notes=self._notes(application, scoring, adjusted, reviewer, program_type),
            override_reason=override_reason,
        )

    # ── Reviewer selection ────────────────────────────────────────────────────

    def _pick_reviewer(self, strict_weight: float) -> dict:
        """
        Pick a reviewer weighted toward strict styles when strict_weight is high.
        strict_weight=0 → purely random; strict_weight=1 → always strict/balanced.
        """
        strict_pool   = [r for r in _REVIEWERS if r["style"] in ("strict", "balanced")]
        generous_pool = [r for r in _REVIEWERS if r["style"] not in ("strict", "balanced")]
        if self._rng.random() < strict_weight:
            return self._rng.choice(strict_pool)
        return self._rng.choice(generous_pool)

    # ── Contextual scoring ────────────────────────────────────────────────────

    def _contextual_adjustment(self, app: Application, style: str, program_type: str) -> float:
        delta = 0.0
        if app.age >= 25:
            delta += 3.0 if style in ("holistic", "equity-focused") else 0.5
        if app.annual_household_income < 40_000:
            delta += 2.5 if style == "equity-focused" else 1.0
        if app.dependents >= 3:
            delta += 1.5
        if app.gpa < 2.6:
            delta -= 5.0 if style == "strict" else 2.0
        if app.gpa >= 3.8 and style == "merit-focused":
            delta += 2.0
        if len(app.essay) < 300:
            delta -= 3.5
        # Regulatory/high-dollar programs penalise weaker profiles more
        if program_type in ("regulatory", "high_dollar"):
            if app.gpa < 3.0:      delta -= 2.0
            if not app.awards:     delta -= 1.0
            if not app.extracurriculars: delta -= 1.5
        return delta

    # ── Text helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _notes(app, scoring, adjusted, reviewer, program_type) -> str:
        delta = adjusted - scoring.rubric_scores.total
        direction = "upward" if delta >= 0 else "downward"
        style_comment = {
            "holistic":      f"Weighted {app.name}'s full context and trajectory.",
            "strict":        f"Applied rubric strictly; {app.name}'s record must stand on its merits.",
            "balanced":      f"Considered both scores and qualitative context.",
            "merit-focused": f"Academic and leadership achievement weighted heavily.",
            "equity-focused":f"Applied an equity lens for structural barriers {app.name} may have faced.",
        }.get(reviewer["style"], "")
        policy_note = {
            "regulatory":  " Regulatory program — elevated approval bar applied.",
            "high_dollar": " High-value award — additional scrutiny applied.",
        }.get(program_type, "")
        return (f"AI score: {scoring.rubric_scores.total:.1f}/100. "
                f"My adjusted score: {adjusted:.1f}/100 ({direction} {abs(delta):.1f} pts). "
                f"{style_comment}{policy_note}")

    @staticmethod
    def _override_reason(ai_outcome, human_outcome, app, style) -> str:
        direction = ("upgrading"
                     if list(DecisionOutcome).index(human_outcome)
                        < list(DecisionOutcome).index(ai_outcome)
                     else "downgrading")
        reasons = {
            "holistic":      f"{direction.capitalize()} — lived experience and trajectory not captured by rubric.",
            "strict":        f"{direction.capitalize()} — documented evidence does not support AI assessment.",
            "equity-focused":f"{direction.capitalize()} — equity-adjusted review warrants different outcome.",
            "merit-focused": f"{direction.capitalize()} — re-weighting merit indicators changes outcome.",
            "balanced":      f"{direction.capitalize()} — contextual factors shift recommendation.",
        }
        return reasons.get(style, f"{direction.capitalize()} after independent review.")
