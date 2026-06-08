"""
Data models for the Agentic AI Astronaut Candidate Selection Platform.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import datetime


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class ConfidenceLevel(Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class DecisionOutcome(Enum):
    APPROVED   = "approved"
    WAITLISTED = "waitlisted"
    DECLINED   = "declined"


class ReviewType(Enum):
    AUTO_DECISION       = "Auto Decision"
    PARALLEL_REVIEW     = "Parallel Review"
    ESCALATION          = "Escalation"
    SENIOR_ADJUDICATION = "Senior Adjudication"
    # Legacy aliases kept for backward compatibility
    AI_ONLY   = "Auto Decision"
    PARALLEL  = "Parallel Review"
    HUMAN_LED = "Escalation"


# ─────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────

@dataclass
class Application:
    """Raw astronaut candidate application."""
    id: str
    name: str
    age: int
    nationality: str

    # Background
    stem_field: str             # e.g. "Aerospace Engineering"
    candidate_level: str        # e.g. "Group 1 Candidate", "Finalist"
    military_background: bool

    # Quantitative — Technical Expertise (verifiable)
    flight_hours: int           # total logged flight hours
    advanced_degrees: int       # 0 = BSc, 1 = MSc, 2 = PhD, 3 = dual PhD

    # Quantitative — Physical & Medical (verifiable)
    physical_fitness_score: float   # 0–100 standardised agency score
    medical_clearance: str          # "Full" | "Conditional" | "Pending"

    # Qualitative — Mission Experience (assessed)
    specializations: List[str]      # e.g. ["EVA", "Robotics", "Navigation"]
    prior_missions: int             # previous spaceflights
    awards: List[str]               # commendations, honours

    # Qualitative — Psychological Readiness (assessed)
    personal_statement: str         # candidate's own narrative
    psychological_profile: str      # evaluator narrative summary

    def to_text(self) -> str:
        """Render the application as a readable text block for LLM consumption."""
        med_str  = self.medical_clearance
        mil_str  = "Yes" if self.military_background else "No"
        deg_map  = {0: "Bachelor's", 1: "Master's", 2: "PhD", 3: "Dual PhD"}
        deg_str  = deg_map.get(self.advanced_degrees, f"{self.advanced_degrees} advanced degrees")
        return f"""
ASTRONAUT CANDIDATE APPLICATION — {self.id}
===========================================
Candidate      : {self.name}, Age {self.age}, {self.nationality}
Background     : {self.stem_field}, {deg_str}, Military: {mil_str}
Status         : {self.candidate_level}

QUANTITATIVE DATA (Verifiable):
  Flight Hours         : {self.flight_hours:,} hrs
  Physical Fitness     : {self.physical_fitness_score:.1f}/100
  Medical Clearance    : {med_str}

MISSION EXPERIENCE:
  Prior Missions       : {self.prior_missions}
  Specializations      : {', '.join(self.specializations) if self.specializations else 'None listed'}
  Awards & Honours     : {', '.join(self.awards) if self.awards else 'None'}

PSYCHOLOGICAL PROFILE (Evaluator Summary):
{self.psychological_profile}

PERSONAL STATEMENT:
{self.personal_statement}
""".strip()


# ─────────────────────────────────────────────
# Stage 1 — Analysis Agent Output
# ─────────────────────────────────────────────

@dataclass
class Evidence:
    """Structured evidence extracted by the Analysis Agent."""
    application_id: str
    academic_strength: str          # technical expertise summary
    financial_need_assessment: str  # physical & medical summary
    leadership_indicators: str      # mission experience summary
    community_impact: str           # crew / team compatibility
    essay_quality: str              # psychological readiness summary
    overall_narrative: str
    key_strengths: List[str]
    key_concerns: List[str]
    raw_extraction: str             # Full LLM response for audit


# ─────────────────────────────────────────────
# Stage 2 — Scoring Agent Output
# ─────────────────────────────────────────────

@dataclass
class RubricScores:
    """Rubric-based scores (each dimension 0–25, total 0–100)."""
    academic_achievement: float     # Technical Expertise
    financial_need: float           # Physical & Medical Fitness
    leadership_service: float       # Mission Experience
    essay_quality: float            # Psychological Readiness

    @property
    def total(self) -> float:
        return (
            self.academic_achievement
            + self.financial_need
            + self.leadership_service
            + self.essay_quality
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "academic_achievement": round(self.academic_achievement, 1),
            "financial_need":       round(self.financial_need, 1),
            "leadership_service":   round(self.leadership_service, 1),
            "essay_quality":        round(self.essay_quality, 1),
            "total":                round(self.total, 1),
        }


@dataclass
class ScoringResult:
    """Full output of the Scoring Agent."""
    application_id: str
    rubric_scores: RubricScores
    ai_recommendation: DecisionOutcome
    confidence: float               # 0.0–1.0
    confidence_level: ConfidenceLevel
    reasoning: str
    raw_scoring: str                # Full LLM response for audit


# ─────────────────────────────────────────────
# Stage 3 — Human Review
# ─────────────────────────────────────────────

@dataclass
class HumanReview:
    """Review from a human evaluator."""
    reviewer_id: str
    reviewer_name: str
    outcome: DecisionOutcome
    score_adjustment: float         # Delta applied to AI total score
    notes: str
    override_reason: Optional[str] = None  # Set if outcome differs from AI rec


# ─────────────────────────────────────────────
# Stage 4 — Final Decision
# ─────────────────────────────────────────────

@dataclass
class AuditStep:
    """A single step in the decision audit trail."""
    step: str
    agent: str
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """The complete, final decision record for one application."""
    application_id: str
    applicant_name:  str
    review_type:     ReviewType
    evidence:        Evidence
    scoring:         ScoringResult
    human_review:    Optional[HumanReview]
    final_outcome:   DecisionOutcome
    agreed:          Optional[bool]       # None when AI-only
    audit_trail:     List[AuditStep]
    signals:         Optional[Any] = None # SignalEvaluation (imported lazily to avoid circular)
    decided_at:      str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat()
    )


# ─────────────────────────────────────────────
# Calibration
# ─────────────────────────────────────────────

@dataclass
class CalibrationRecord:
    """Tracks agreement between AI and human for calibration purposes."""
    application_id: str
    ai_outcome: DecisionOutcome
    human_outcome: DecisionOutcome
    ai_score: float
    human_adjusted_score: float
    agreed: bool
    divergence_reason: Optional[str]
    insight: str
