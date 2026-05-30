"""
Human Review Layer
==================
Simulates human scholarship reviewers with realistic variance.

In production this module would:
  - Send a review task to a human via a UI or API
  - Wait for their response (async)
  - Record their decision and notes

In this prototype it simulates reviewers using a deterministic but
context-sensitive algorithm that reflects realistic human behaviour:
  - Reviewers have a small systematic bias (some lean generous, some strict)
  - Reviewers respond to contextual signals (non-traditional profiles, gaps, etc.)
  - Reviewers occasionally override the AI — more so in human-led cases
  - Each review includes a natural-language note and override reason (if applicable)
"""
import random
from .models import (
    Application, ScoringResult, HumanReview,
    DecisionOutcome, ReviewType,
)

# Simulated reviewer pool
_REVIEWERS = [
    {"id": "HR-01", "name": "Dr. Amara Diallo",      "bias": +2.0, "style": "holistic"},
    {"id": "HR-02", "name": "Prof. Samuel Chen",      "bias": -1.5, "style": "strict"},
    {"id": "HR-03", "name": "Ms. Rachel Okafor",      "bias": +0.5, "style": "balanced"},
    {"id": "HR-04", "name": "Mr. David Steinberg",    "bias": +1.0, "style": "merit-focused"},
    {"id": "HR-05", "name": "Dr. Fatima Al-Hassan",   "bias": +3.0, "style": "equity-focused"},
]

# Score thresholds for human-derived decisions
_APPROVE_THRESHOLD  = 68.0
_WAITLIST_THRESHOLD = 50.0


class HumanReviewLayer:
    """
    Simulates a panel of human reviewers.
    Called by the Orchestrator for MEDIUM and LOW confidence cases.
    """

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def review(
        self,
        application: Application,
        scoring: ScoringResult,
        review_type: ReviewType,
    ) -> HumanReview:
        """
        Simulate a human reviewer evaluating the application.
        Returns a HumanReview with outcome, notes, and optional override reason.
        """
        reviewer = self._rng.choice(_REVIEWERS)

        # ── Compute reviewer's adjusted score ─────────────────────────────────
        # Base: AI total + reviewer systematic bias + small random noise
        noise = self._rng.gauss(0, 2.5)       # ±2.5pt Gaussian noise
        adjustment = reviewer["bias"] + noise
        adjusted_total = scoring.rubric_scores.total + adjustment

        # Apply contextual adjustments based on profile signals
        adjustment += self._contextual_adjustment(application, reviewer["style"])
        adjusted_total = scoring.rubric_scores.total + adjustment
        adjusted_total = max(0.0, min(100.0, adjusted_total))  # clamp

        # ── Derive human outcome from adjusted score ──────────────────────────
        if adjusted_total >= _APPROVE_THRESHOLD:
            human_outcome = DecisionOutcome.APPROVED
        elif adjusted_total >= _WAITLIST_THRESHOLD:
            human_outcome = DecisionOutcome.WAITLISTED
        else:
            human_outcome = DecisionOutcome.DECLINED

        # ── Determine override ────────────────────────────────────────────────
        ai_outcome = scoring.ai_recommendation
        override_reason = None
        if human_outcome != ai_outcome:
            override_reason = self._generate_override_reason(
                ai_outcome, human_outcome, application, reviewer["style"]
            )

        # ── Generate review notes ─────────────────────────────────────────────
        notes = self._generate_notes(application, scoring, adjusted_total, reviewer)

        return HumanReview(
            reviewer_id=reviewer["id"],
            reviewer_name=reviewer["name"],
            outcome=human_outcome,
            score_adjustment=round(adjustment, 1),
            notes=notes,
            override_reason=override_reason,
        )

    # ── Contextual adjustments ────────────────────────────────────────────────

    def _contextual_adjustment(self, app: Application, style: str) -> float:
        """
        Apply profile-sensitive adjustments that reflect how real reviewers
        respond to non-standard application signals.
        """
        delta = 0.0

        # Non-traditional age / career changer
        if app.age >= 28:
            delta += 3.0 if style in ("holistic", "equity-focused") else 0.0

        # High financial need
        if app.annual_household_income < 40_000:
            delta += 2.0 if style == "equity-focused" else 1.0

        # Many dependents
        if app.dependents >= 3:
            delta += 1.5

        # Very low GPA — strict reviewers penalise more
        if app.gpa < 2.6:
            delta -= 4.0 if style == "strict" else -2.0

        # Strong GPA — merit-focused reviewers reward more
        if app.gpa >= 3.8 and style == "merit-focused":
            delta += 2.0

        # Short or weak essay (heuristic: < 200 chars)
        if len(app.essay) < 300:
            delta -= 3.0

        return delta

    # ── Text generation helpers ───────────────────────────────────────────────

    @staticmethod
    def _generate_notes(
        app: Application,
        scoring: ScoringResult,
        adjusted_total: float,
        reviewer: dict,
    ) -> str:
        name = app.name
        style = reviewer["style"]
        ai_total = scoring.rubric_scores.total
        delta = adjusted_total - ai_total

        direction = "upward" if delta >= 0 else "downward"
        magnitude = abs(delta)

        style_comment = {
            "holistic": f"I've weighted {name}'s full context, including factors the rubric may undervalue.",
            "strict":   f"I apply the rubric strictly; {name}'s record must stand on its merits.",
            "balanced": f"I've considered both quantitative scores and qualitative context for {name}.",
            "merit-focused": f"Academic and leadership achievement are primary drivers in my assessment of {name}.",
            "equity-focused": f"I've applied an equity lens, considering structural barriers {name} may have faced.",
        }.get(style, "")

        return (
            f"AI score: {ai_total:.1f}/100. My adjusted score: {adjusted_total:.1f}/100 "
            f"({direction} adjustment of {magnitude:.1f} points). "
            f"{style_comment}"
        )

    @staticmethod
    def _generate_override_reason(
        ai_outcome: DecisionOutcome,
        human_outcome: DecisionOutcome,
        app: Application,
        style: str,
    ) -> str:
        direction = (
            "upgrading" if (
                list(DecisionOutcome).index(human_outcome)
                < list(DecisionOutcome).index(ai_outcome)
            ) else "downgrading"
        )

        reasons = {
            "holistic": (
                f"{direction.capitalize()} based on holistic review — "
                f"the applicant's lived experience and trajectory are not fully captured by the rubric."
            ),
            "strict": (
                f"{direction.capitalize()} — applying rubric criteria strictly, "
                f"the documented evidence does not support the AI's assessment."
            ),
            "equity-focused": (
                f"{direction.capitalize()} — an equity-adjusted review of structural barriers "
                f"faced by {app.name} warrants a different outcome."
            ),
            "merit-focused": (
                f"{direction.capitalize()} — re-weighting merit indicators changes the outcome."
            ),
            "balanced": (
                f"{direction.capitalize()} — on balance, contextual factors shift the recommendation."
            ),
        }
        return reasons.get(style, f"{direction.capitalize()} after independent review.")
