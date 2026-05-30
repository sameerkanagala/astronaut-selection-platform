"""
Data models for the Agentic AI Scholarship Evaluation Platform.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import datetime


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class ConfidenceLevel(Enum):
    HIGH = "high"       # > 0.78  → AI-only decision
    MEDIUM = "medium"   # 0.50–0.78 → parallel AI + human review
    LOW = "low"         # < 0.50  → human-led decision


class DecisionOutcome(Enum):
    APPROVED = "approved"
    WAITLISTED = "waitlisted"
    DECLINED = "declined"


class ReviewType(Enum):
    AI_ONLY = "AI-Only"
    PARALLEL = "Parallel AI + Human"
    HUMAN_LED = "Human-Led"


# ─────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────

@dataclass
class Application:
    """Raw scholarship application as submitted by an applicant."""
    id: str
    name: str
    age: int
    gpa: float                         # 0.0–4.0
    major: str
    year: str                          # Freshman / Sophomore / Junior / Senior
    annual_household_income: int       # USD
    dependents: int
    essay: str
    extracurriculars: List[str]
    work_experience: Optional[str]
    recommendation_summary: str        # Condensed letter content
    awards: List[str]

    def to_text(self) -> str:
        """Render the application as a readable text block for LLM consumption."""
        return f"""
SCHOLARSHIP APPLICATION — {self.id}
====================================
Applicant      : {self.name}, Age {self.age}
Academic       : {self.major}, {self.year}, GPA {self.gpa:.2f}
Financial      : Annual household income ${self.annual_household_income:,}, {self.dependents} dependents
Work Experience: {self.work_experience or 'None reported'}
Awards         : {', '.join(self.awards) if self.awards else 'None'}
Extracurriculars: {', '.join(self.extracurriculars) if self.extracurriculars else 'None'}

PERSONAL ESSAY:
{self.essay}

RECOMMENDATION SUMMARY:
{self.recommendation_summary}
""".strip()


# ─────────────────────────────────────────────
# Stage 1 — Analysis Agent Output
# ─────────────────────────────────────────────

@dataclass
class Evidence:
    """Structured evidence extracted by the Analysis Agent."""
    application_id: str
    academic_strength: str
    financial_need_assessment: str
    leadership_indicators: str
    community_impact: str
    essay_quality: str
    overall_narrative: str
    key_strengths: List[str]
    key_concerns: List[str]
    raw_extraction: str                # Full LLM response for audit


# ─────────────────────────────────────────────
# Stage 2 — Scoring Agent Output
# ─────────────────────────────────────────────

@dataclass
class RubricScores:
    """Rubric-based scores (each dimension 0–25, total 0–100)."""
    academic_achievement: float
    financial_need: float
    leadership_service: float
    essay_quality: float

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
            "financial_need": round(self.financial_need, 1),
            "leadership_service": round(self.leadership_service, 1),
            "essay_quality": round(self.essay_quality, 1),
            "total": round(self.total, 1),
        }


@dataclass
class ScoringResult:
    """Full output of the Scoring Agent."""
    application_id: str
    rubric_scores: RubricScores
    ai_recommendation: DecisionOutcome
    confidence: float                  # 0.0–1.0
    confidence_level: ConfidenceLevel
    reasoning: str
    raw_scoring: str                   # Full LLM response for audit


# ─────────────────────────────────────────────
# Stage 3 — Human Review
# ─────────────────────────────────────────────

@dataclass
class HumanReview:
    """Review from a human evaluator."""
    reviewer_id: str
    reviewer_name: str
    outcome: DecisionOutcome
    score_adjustment: float            # Delta applied to AI total score
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
    applicant_name: str
    review_type: ReviewType
    evidence: Evidence
    scoring: ScoringResult
    human_review: Optional[HumanReview]
    final_outcome: DecisionOutcome
    agreed: Optional[bool]             # None when AI-only
    audit_trail: List[AuditStep]
    decided_at: str = field(
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
