"""
Calibration System
==================
A closed-loop calibration engine that:
  1. Collects AI vs human decision pairs from completed evaluations
  2. Measures agreement rate, score variance, and systematic divergences
  3. Surfaces actionable insights to:
       - Refine AI evaluation logic
       - Identify human reviewer drift
       - Improve rubric consistency

In production, calibration insights would feed back into:
  - Prompt engineering for the Analysis and Scoring Agents
  - Reviewer training and recalibration sessions
  - Rubric weight adjustments

Here they are computed and rendered as a human-readable report.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from collections import Counter, defaultdict
from statistics import mean, stdev

from .models import Decision, CalibrationRecord, DecisionOutcome, ReviewType


@dataclass
class CalibrationReport:
    """Aggregated calibration metrics for a batch of evaluated applications."""
    total_evaluated: int
    reviewed_by_human: int
    agreement_rate: float                  # 0.0–1.0
    disagreements: int
    avg_score_delta: float                 # Human adj. vs AI total
    score_variance: float                  # Std dev of adjustments
    outcome_distribution: dict             # {outcome: count}
    reviewer_breakdown: dict               # {reviewer_id: {agree: n, disagree: n}}
    divergence_patterns: List[str]         # Common override reasons
    calibration_insights: List[str]        # Actionable recommendations
    records: List[CalibrationRecord] = field(default_factory=list)


class CalibrationSystem:
    """
    Analyses a batch of completed decisions to produce calibration metrics
    and alignment insights for the AI and human reviewer populations.
    """

    def analyse(self, decisions: List[Decision]) -> CalibrationReport:
        """
        Process all decisions and return a CalibrationReport.
        Only cases with human reviews are included in agreement metrics.
        """
        records: List[CalibrationRecord] = []
        outcome_counts: Counter = Counter()
        reviewer_stats: dict = defaultdict(lambda: {"agree": 0, "disagree": 0})
        score_deltas: List[float] = []
        divergence_reasons: List[str] = []

        for decision in decisions:
            outcome_counts[decision.final_outcome.value] += 1

            if decision.human_review is None:
                continue  # AI-only — skip for agreement metrics

            hr = decision.human_review
            ai_score = decision.scoring.rubric_scores.total
            human_score = ai_score + hr.score_adjustment
            agreed = decision.agreed if decision.agreed is not None else (
                hr.outcome == decision.scoring.ai_recommendation
            )
            score_deltas.append(hr.score_adjustment)

            if agreed:
                reviewer_stats[hr.reviewer_id]["agree"] += 1
            else:
                reviewer_stats[hr.reviewer_id]["disagree"] += 1
                if hr.override_reason:
                    divergence_reasons.append(hr.override_reason)

            insight = self._record_insight(decision, agreed, hr.score_adjustment)

            records.append(CalibrationRecord(
                application_id=decision.application_id,
                ai_outcome=decision.scoring.ai_recommendation,
                human_outcome=hr.outcome,
                ai_score=round(ai_score, 1),
                human_adjusted_score=round(human_score, 1),
                agreed=agreed,
                divergence_reason=hr.override_reason,
                insight=insight,
            ))

        reviewed_count = len(records)
        if reviewed_count == 0:
            agreement_rate = 1.0
            avg_delta = 0.0
            variance = 0.0
        else:
            agreements = sum(1 for r in records if r.agreed)
            agreement_rate = agreements / reviewed_count
            avg_delta = mean(score_deltas) if score_deltas else 0.0
            variance = stdev(score_deltas) if len(score_deltas) > 1 else 0.0

        insights = self._generate_insights(
            records, agreement_rate, avg_delta, variance, reviewer_stats
        )

        return CalibrationReport(
            total_evaluated=len(decisions),
            reviewed_by_human=reviewed_count,
            agreement_rate=round(agreement_rate, 3),
            disagreements=sum(1 for r in records if not r.agreed),
            avg_score_delta=round(avg_delta, 2),
            score_variance=round(variance, 2),
            outcome_distribution=dict(outcome_counts),
            reviewer_breakdown={
                rid: dict(stats) for rid, stats in reviewer_stats.items()
            },
            divergence_patterns=list(set(divergence_reasons))[:5],
            calibration_insights=insights,
            records=records,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _record_insight(decision: Decision, agreed: bool, delta: float) -> str:
        if agreed:
            return f"AI and human aligned on {decision.final_outcome.value} (Δ score: {delta:+.1f})"
        return (
            f"Disagreement: AI→{decision.scoring.ai_recommendation.value}, "
            f"Human→{decision.human_review.outcome.value}. "
            f"Score delta: {delta:+.1f}. "
            f"Reason: {decision.human_review.override_reason or 'Not stated'}"
        )

    @staticmethod
    def _generate_insights(
        records: List[CalibrationRecord],
        agreement_rate: float,
        avg_delta: float,
        variance: float,
        reviewer_stats: dict,
    ) -> List[str]:
        insights = []

        # Agreement health
        if agreement_rate >= 0.85:
            insights.append(
                f"✓ AI–human agreement rate is strong ({agreement_rate:.0%}). "
                "Current evaluation logic is well-calibrated."
            )
        elif agreement_rate >= 0.70:
            insights.append(
                f"⚠ Agreement rate ({agreement_rate:.0%}) is moderate. "
                "Review cases of disagreement to identify rubric gaps."
            )
        else:
            insights.append(
                f"✗ Low agreement rate ({agreement_rate:.0%}). "
                "Immediate re-calibration recommended — consider rubric revision."
            )

        # Systematic bias direction
        if avg_delta > 2.0:
            insights.append(
                f"Reviewers are scoring {avg_delta:+.1f} pts above AI on average. "
                "AI scoring may be undervaluing qualitative factors — review essay and "
                "community-impact rubric dimensions."
            )
        elif avg_delta < -2.0:
            insights.append(
                f"Reviewers are scoring {avg_delta:+.1f} pts below AI on average. "
                "AI scoring may be inflating merit — tighten rubric thresholds."
            )
        else:
            insights.append(
                f"Score delta is near-zero ({avg_delta:+.1f} pts on average) — "
                "no systematic human/AI bias detected."
            )

        # Variance
        if variance > 6.0:
            insights.append(
                f"High score variance (σ={variance:.1f}) among human adjustments. "
                "Reviewer alignment sessions recommended to improve consistency."
            )

        # Reviewer-level breakdown
        for rid, stats in reviewer_stats.items():
            total = stats["agree"] + stats["disagree"]
            if total >= 2:
                disagree_rate = stats["disagree"] / total
                if disagree_rate >= 0.6:
                    insights.append(
                        f"Reviewer {rid} disagrees with AI in {disagree_rate:.0%} of cases — "
                        "may need individual calibration session."
                    )

        # Pattern in disagreements
        upgrades = sum(
            1 for r in records
            if not r.agreed
            and list(DecisionOutcome).index(r.human_outcome)
            < list(DecisionOutcome).index(r.ai_outcome)
        )
        downgrades = sum(1 for r in records if not r.agreed) - upgrades
        if upgrades > downgrades:
            insights.append(
                "Most overrides are upgrades (human more generous than AI). "
                "Consider whether AI rubric adequately captures non-traditional merit."
            )
        elif downgrades > upgrades:
            insights.append(
                "Most overrides are downgrades (human stricter than AI). "
                "Review whether AI is being too lenient on borderline cases."
            )

        return insights


# ── Standalone report renderer ─────────────────────────────────────────────

def render_calibration_report(report: CalibrationReport) -> str:
    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║          CALIBRATION SYSTEM — BATCH ANALYSIS REPORT         ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
        f"  Applications evaluated     : {report.total_evaluated}",
        f"  Cases with human review    : {report.reviewed_by_human}",
        f"  AI–Human agreement rate    : {report.agreement_rate:.0%}",
        f"  Disagreements              : {report.disagreements}",
        f"  Avg score delta (human–AI) : {report.avg_score_delta:+.2f} pts",
        f"  Score adjustment variance  : σ = {report.score_variance:.2f}",
        "",
        "  OUTCOME DISTRIBUTION",
        "  " + "─" * 40,
    ]
    for outcome, count in sorted(report.outcome_distribution.items()):
        bar = "█" * count
        lines.append(f"  {outcome:<12} {bar} ({count})")

    if report.reviewer_breakdown:
        lines += [
            "",
            "  REVIEWER AGREEMENT BREAKDOWN",
            "  " + "─" * 40,
        ]
        for rid, stats in report.reviewer_breakdown.items():
            total = stats["agree"] + stats["disagree"]
            rate = stats["agree"] / total if total else 0
            lines.append(
                f"  {rid}  agree={stats['agree']}  disagree={stats['disagree']}  "
                f"({rate:.0%} agreement)"
            )

    lines += [
        "",
        "  CALIBRATION INSIGHTS",
        "  " + "─" * 40,
    ]
    for i, insight in enumerate(report.calibration_insights, 1):
        # Wrap long lines
        words = insight.split()
        current, wrapped = [], []
        for w in words:
            if sum(len(x) for x in current) + len(current) + len(w) > 70:
                wrapped.append("  " + " ".join(current))
                current = [w]
            else:
                current.append(w)
        if current:
            wrapped.append("  " + " ".join(current))
        lines.append(f"\n  [{i}] {wrapped[0].strip()}")
        for extra in wrapped[1:]:
            lines.append(f"      {extra.strip()}")

    if report.records:
        lines += [
            "",
            "  CASE-LEVEL RECORDS",
            "  " + "─" * 40,
        ]
        for r in report.records:
            status = "✓ agree" if r.agreed else "✗ disagree"
            lines.append(
                f"  {r.application_id}  AI:{r.ai_score:.0f}→{r.ai_outcome.value:<10}  "
                f"Human:{r.human_adjusted_score:.0f}→{r.human_outcome.value:<10}  {status}"
            )

    lines.append("")
    return "\n".join(lines)
