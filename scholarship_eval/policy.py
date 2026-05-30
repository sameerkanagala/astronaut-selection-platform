"""
Program Policy
==============
Externalises routing logic into program-specific, configurable policy objects.
Different programs (high-volume merit scholarship vs. high-dollar regulatory grant)
can have different risk tolerances, scrutiny levels, and escalation requirements
without changing core infrastructure.

Each policy controls:
  - Confidence thresholds          (when AI confidence is sufficient)
  - Decision sensitivity rules     (cost of being wrong)
  - Disagreement tolerance         (how much signal divergence triggers escalation)
  - Escalation thresholds          (composite risk scores for each routing tier)
  - Human oversight requirements   (mandatory review rules)
"""
from dataclasses import dataclass, field
from typing import Literal


AwardSensitivity = Literal["low", "medium", "high"]


@dataclass
class ProgramPolicy:
    """
    A complete routing and governance policy for one scholarship program.
    All thresholds are on a 0–1 scale unless otherwise noted.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    program_name: str = "Custom Program"
    program_type: str = "custom"       # high_volume | high_dollar | regulatory | custom
    description:  str = ""

    # ── Confidence thresholds ─────────────────────────────────────────────────
    confidence_high: float = 0.78      # ≥ this: AI has strong signal
    confidence_low:  float = 0.50      # < this: AI signal is weak

    # ── Decision sensitivity ──────────────────────────────────────────────────
    cutoff_zone_pts:   float = 5.0     # pts from approve/waitlist boundary = high sensitivity
    award_sensitivity: AwardSensitivity = "medium"  # baseline sensitivity from award value/impact
    # Sensitivity score contribution per award level:
    #   low=0.10  medium=0.20  high=0.35

    # ── Disagreement signals ──────────────────────────────────────────────────
    disagreement_tolerance:       float = 0.45  # composite disagreement above this → escalate
    evidence_mismatch_threshold:  float = 0.35  # evidence vs score divergence above this → flag
    rubric_variance_threshold:    float = 0.25  # std-dev of rubric dims above this → flag

    # ── Routing thresholds (composite risk score 0–1) ─────────────────────────
    auto_max_sensitivity:        float = 0.25   # max sensitivity allowed for auto routing
    escalation_threshold:        float = 0.55   # composite risk ≥ this → escalation
    senior_escalation_threshold: float = 0.75   # composite risk ≥ this → senior adjudication

    # ── Mandatory oversight rules ─────────────────────────────────────────────
    require_human_near_cutoff:   bool  = False  # always human review if score near boundary
    min_reviewers_escalated:     int   = 1      # number of reviewers for escalated cases
    senior_adjudication_enabled: bool  = True   # allow senior adjudication tier

    # ── Simulated disagreement controls ──────────────────────────────────────
    # These control how likely human reviewers are to disagree with AI in
    # the simulation, making preset differences visible in the results.
    reviewer_strictness:   float = 0.20  # 0=very generous, 1=very strict (shifts approval bar)
    disagreement_sim_rate: float = 0.25  # probability a borderline case triggers human override
    reviewer_noise_sigma:  float = 2.5   # std-dev of score noise (higher=more variance/disagreement)

    # ── Fairness & governance ─────────────────────────────────────────────────
    fairness_monitoring: bool = True
    audit_all_decisions: bool = True


# ── Program Presets ────────────────────────────────────────────────────────────

PRESETS: dict[str, ProgramPolicy] = {

    "high_volume": ProgramPolicy(
        program_name="High-Volume Merit Scholarship",
        program_type="high_volume",
        description=(
            "Large applicant pool, moderate award value. Optimised for throughput. "
            "AI automation encouraged for clear-cut cases. Human review reserved "
            "for ambiguous applications. Generous approval bar."
        ),
        confidence_high=0.78, confidence_low=0.50,
        cutoff_zone_pts=5.0, award_sensitivity="low",
        disagreement_tolerance=0.50, evidence_mismatch_threshold=0.40,
        rubric_variance_threshold=0.28, auto_max_sensitivity=0.30,
        escalation_threshold=0.60, senior_escalation_threshold=0.80,
        require_human_near_cutoff=False, min_reviewers_escalated=1,
        senior_adjudication_enabled=True, fairness_monitoring=True,
        reviewer_strictness=0.10, disagreement_sim_rate=0.15, reviewer_noise_sigma=2.0,
    ),

    "high_dollar": ProgramPolicy(
        program_name="High-Dollar Grant Program",
        program_type="high_dollar",
        description=(
            "High-value award ($25k+). Every error carries financial and reputational cost. "
            "Stricter thresholds, mandatory human review near cutoffs, higher reviewer "
            "disagreement rate, and elevated approval bar."
        ),
        confidence_high=0.85, confidence_low=0.60,
        cutoff_zone_pts=8.0, award_sensitivity="high",
        disagreement_tolerance=0.35, evidence_mismatch_threshold=0.30,
        rubric_variance_threshold=0.22, auto_max_sensitivity=0.15,
        escalation_threshold=0.48, senior_escalation_threshold=0.68,
        require_human_near_cutoff=True, min_reviewers_escalated=2,
        senior_adjudication_enabled=True, fairness_monitoring=True,
        reviewer_strictness=0.45, disagreement_sim_rate=0.40, reviewer_noise_sigma=3.0,
    ),

    "regulatory": ProgramPolicy(
        program_name="Regulatory / Compliance Program",
        program_type="regulatory",
        description=(
            "Federal or regulated funding. Maximum scrutiny, mandatory human oversight, "
            "full audit trails. AI is advisory. Strict approval bar, high disagreement "
            "simulation, senior adjudication for borderline cases."
        ),
        confidence_high=0.90, confidence_low=0.65,
        cutoff_zone_pts=10.0, award_sensitivity="high",
        disagreement_tolerance=0.25, evidence_mismatch_threshold=0.25,
        rubric_variance_threshold=0.20, auto_max_sensitivity=0.10,
        escalation_threshold=0.42, senior_escalation_threshold=0.62,
        require_human_near_cutoff=True, min_reviewers_escalated=2,
        senior_adjudication_enabled=True, fairness_monitoring=True,
        reviewer_strictness=0.70, disagreement_sim_rate=0.60, reviewer_noise_sigma=3.5,
    ),

    "custom": ProgramPolicy(
        program_name="Custom Program",
        program_type="custom",
        description="Manually configured policy — all parameters adjustable.",
    ),
}


def policy_from_dict(d: dict) -> ProgramPolicy:
    """Build a ProgramPolicy from a JSON-safe dict (e.g. from the web frontend)."""
    return ProgramPolicy(
        program_name=d.get("program_name", "Custom Program"),
        program_type=d.get("program_type", "custom"),
        description=d.get("description", ""),
        confidence_high=float(d.get("confidence_high", 0.78)),
        confidence_low=float(d.get("confidence_low",  0.50)),
        cutoff_zone_pts=float(d.get("cutoff_zone_pts", 5.0)),
        award_sensitivity=d.get("award_sensitivity", "medium"),
        disagreement_tolerance=float(d.get("disagreement_tolerance", 0.45)),
        evidence_mismatch_threshold=float(d.get("evidence_mismatch_threshold", 0.35)),
        rubric_variance_threshold=float(d.get("rubric_variance_threshold", 0.25)),
        auto_max_sensitivity=float(d.get("auto_max_sensitivity", 0.25)),
        escalation_threshold=float(d.get("escalation_threshold", 0.55)),
        senior_escalation_threshold=float(d.get("senior_escalation_threshold", 0.75)),
        require_human_near_cutoff=bool(d.get("require_human_near_cutoff", False)),
        min_reviewers_escalated=int(d.get("min_reviewers_escalated", 1)),
        senior_adjudication_enabled=bool(d.get("senior_adjudication_enabled", True)),
        fairness_monitoring=bool(d.get("fairness_monitoring", True)),
        reviewer_strictness=float(d.get("reviewer_strictness", 0.20)),
        disagreement_sim_rate=float(d.get("disagreement_sim_rate", 0.25)),
        reviewer_noise_sigma=float(d.get("reviewer_noise_sigma", 2.5)),
    )


def policy_to_dict(p: ProgramPolicy) -> dict:
    """Serialise a ProgramPolicy to a JSON-safe dict."""
    return {
        "program_name":               p.program_name,
        "program_type":               p.program_type,
        "description":                p.description,
        "confidence_high":            p.confidence_high,
        "confidence_low":             p.confidence_low,
        "cutoff_zone_pts":            p.cutoff_zone_pts,
        "award_sensitivity":          p.award_sensitivity,
        "disagreement_tolerance":     p.disagreement_tolerance,
        "evidence_mismatch_threshold":p.evidence_mismatch_threshold,
        "rubric_variance_threshold":  p.rubric_variance_threshold,
        "auto_max_sensitivity":       p.auto_max_sensitivity,
        "escalation_threshold":       p.escalation_threshold,
        "senior_escalation_threshold":p.senior_escalation_threshold,
        "require_human_near_cutoff":   p.require_human_near_cutoff,
        "min_reviewers_escalated":     p.min_reviewers_escalated,
        "senior_adjudication_enabled": p.senior_adjudication_enabled,
        "fairness_monitoring":         p.fairness_monitoring,
        "reviewer_strictness":         p.reviewer_strictness,
        "disagreement_sim_rate":       p.disagreement_sim_rate,
        "reviewer_noise_sigma":        p.reviewer_noise_sigma,
    }
