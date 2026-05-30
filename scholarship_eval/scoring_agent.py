"""
Scoring Agent — configurable confidence thresholds.
Thresholds are injected at construction time so the web UI can override them.
"""
import json, re
from anthropic import Anthropic
from .models import (
    Application, Evidence, RubricScores, ScoringResult,
    DecisionOutcome, ConfidenceLevel,
)

SCORING_SYSTEM_PROMPT = """You are the Scoring Agent in a scholarship evaluation platform.
You receive structured evidence about an applicant and apply a rubric to produce scores and a recommendation.

RUBRIC (each dimension 0–25 points, total 0–100):
1. academic_achievement  — GPA, rigor, improvement trend, awards
2. financial_need        — household income, dependents, demonstrated hardship
3. leadership_service    — leadership roles, service hours, measurable impact
4. essay_quality         — specificity, authenticity, clarity, compelling narrative

confidence is a float 0.0–1.0 reflecting how clear-cut the recommendation is.
High confidence (≥0.78): strong signal in most dimensions; outcome is unambiguous.
Medium confidence (0.50–0.77): mixed signals or unusual profile.
Low confidence (<0.50): highly ambiguous or conflicting evidence.

RECOMMENDATION THRESHOLDS (as a guide):
- approved    : total ≥ 70
- waitlisted  : total 50–69
- declined    : total < 50

Respond ONLY with a single valid JSON object — no prose, no markdown fences.
Schema:
{
  "academic_achievement": <float 0-25>,
  "financial_need": <float 0-25>,
  "leadership_service": <float 0-25>,
  "essay_quality": <float 0-25>,
  "recommendation": "approved" | "waitlisted" | "declined",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<2-4 sentence explanation>"
}"""


class ScoringAgent:
    def __init__(self, client: Anthropic, model: str = "claude-haiku-4-5-20251001",
                 high_threshold: float = 0.78, low_threshold: float = 0.50):
        self.client         = client
        self.model          = model
        self.high_threshold = high_threshold
        self.low_threshold  = low_threshold

    def score(self, application: Application, evidence: Evidence) -> ScoringResult:
        evidence_text = self._format_evidence(application, evidence)
        messages = [{"role": "user", "content":
                     f"Apply the rubric to this applicant evidence:\n\n{evidence_text}"}]

        response = self.client.messages.create(
            model=self.model, max_tokens=800,
            system=SCORING_SYSTEM_PROMPT, messages=messages)
        raw = response.content[0].text
        parsed = self._parse_json(raw)

        if parsed is None:
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": "Return ONLY the JSON scoring object."}]
            raw = self.client.messages.create(
                model=self.model, max_tokens=800,
                system=SCORING_SYSTEM_PROMPT, messages=messages).content[0].text
            parsed = self._parse_json(raw)

        if parsed is None:
            return ScoringResult(
                application_id=application.id,
                rubric_scores=RubricScores(0, 0, 0, 0),
                ai_recommendation=DecisionOutcome.WAITLISTED,
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                reasoning="Scoring extraction failed — flagged for human review.",
                raw_scoring=raw or "")

        rubric = RubricScores(
            academic_achievement=float(parsed.get("academic_achievement", 0)),
            financial_need=float(parsed.get("financial_need", 0)),
            leadership_service=float(parsed.get("leadership_service", 0)),
            essay_quality=float(parsed.get("essay_quality", 0)),
        )
        rec = {"approved": DecisionOutcome.APPROVED,
               "waitlisted": DecisionOutcome.WAITLISTED,
               "declined": DecisionOutcome.DECLINED}.get(
            parsed.get("recommendation","waitlisted").lower(), DecisionOutcome.WAITLISTED)

        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
        if confidence >= self.high_threshold:
            conf_level = ConfidenceLevel.HIGH
        elif confidence >= self.low_threshold:
            conf_level = ConfidenceLevel.MEDIUM
        else:
            conf_level = ConfidenceLevel.LOW

        return ScoringResult(
            application_id=application.id, rubric_scores=rubric,
            ai_recommendation=rec, confidence=confidence,
            confidence_level=conf_level,
            reasoning=parsed.get("reasoning", ""), raw_scoring=raw)

    @staticmethod
    def _format_evidence(app, ev):
        return (f"APPLICANT: {app.name} ({app.id})\n"
                f"GPA: {app.gpa:.2f} | Major: {app.major} | Year: {app.year}\n"
                f"Household Income: ${app.annual_household_income:,} | Dependents: {app.dependents}\n\n"
                f"EXTRACTED EVIDENCE:\n"
                f"Academic Strength     : {ev.academic_strength}\n"
                f"Financial Need        : {ev.financial_need_assessment}\n"
                f"Leadership Indicators : {ev.leadership_indicators}\n"
                f"Community Impact      : {ev.community_impact}\n"
                f"Essay Quality         : {ev.essay_quality}\n"
                f"Overall Narrative     : {ev.overall_narrative}\n"
                f"Key Strengths : {', '.join(ev.key_strengths)}\n"
                f"Key Concerns  : {', '.join(ev.key_concerns) if ev.key_concerns else 'None'}")

    @staticmethod
    def _parse_json(text):
        cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if m:
                try: return json.loads(m.group())
                except: pass
        return None
