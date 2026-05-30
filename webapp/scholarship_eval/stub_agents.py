"""Stub agents — full pipeline without any API calls. Thresholds are configurable."""
from .models import (Application, Evidence, RubricScores, ScoringResult,
                     HumanReview, Decision, DecisionOutcome, ConfidenceLevel,
                     ReviewType, AuditStep)
from .human_review import HumanReviewLayer


class StubAnalysisAgent:
    def extract_evidence(self, app: Application) -> Evidence:
        gpa_c = ("Exceptional academic record." if app.gpa >= 3.8
                 else "Solid academic record." if app.gpa >= 3.0
                 else "Below-average academic record; context required.")
        need_c = (f"High financial need: ${app.annual_household_income:,}, {app.dependents} dependents."
                  if app.annual_household_income < 45_000
                  else f"Moderate financial need: ${app.annual_household_income:,}."
                  if app.annual_household_income < 90_000
                  else f"Lower financial need: ${app.annual_household_income:,}.")
        leadership = (f"Strong leadership: {', '.join(app.extracurriculars[:2])}."
                      if app.extracurriculars else "No leadership activities reported.")
        community  = ("Demonstrated community impact." if len(app.extracurriculars) >= 2
                      else "Limited community engagement.")
        elen = len(app.essay)
        essay_c = ("Compelling, specific personal essay." if elen > 500
                   else "Adequate essay with some detail." if elen > 250
                   else "Brief, generic essay lacking specificity.")
        strengths, concerns = [], []
        if app.gpa >= 3.7:            strengths.append(f"Strong GPA ({app.gpa:.2f})")
        if app.annual_household_income < 45_000: strengths.append("Demonstrated financial need")
        if len(app.extracurriculars) >= 2: strengths.append("Active extracurricular engagement")
        if app.awards:                strengths.append(f"Recognition: {app.awards[0]}")
        if elen > 500:                strengths.append("Articulate personal essay")
        if app.gpa < 2.8:             concerns.append("GPA below competitive threshold")
        if not app.extracurriculars:  concerns.append("No extracurricular activities")
        if elen < 250:                concerns.append("Essay lacks depth")
        if not app.awards:            concerns.append("No awards documented")
        return Evidence(
            application_id=app.id,
            academic_strength=gpa_c, financial_need_assessment=need_c,
            leadership_indicators=leadership, community_impact=community,
            essay_quality=essay_c,
            overall_narrative=(f"{app.name} is a {app.year.lower()} studying {app.major}. "
                               f"{gpa_c} {need_c}"),
            key_strengths=strengths or ["Application submitted"],
            key_concerns=concerns  or ["No major concerns identified"],
            raw_extraction="[stub mode]")


class StubScoringAgent:
    def __init__(self, high_threshold=0.78, low_threshold=0.50):
        self.high_threshold = high_threshold
        self.low_threshold  = low_threshold

    def score(self, app: Application, evidence: Evidence) -> ScoringResult:
        academic  = min(25.0, (app.gpa / 4.0) * 25.0)
        if   app.annual_household_income <= 30_000: financial = 25.0
        elif app.annual_household_income <= 50_000: financial = 20.0 + (50_000 - app.annual_household_income) / 20_000 * 5.0
        elif app.annual_household_income <= 90_000: financial = 12.0 + (90_000 - app.annual_household_income) / 40_000 * 8.0
        else: financial = max(0.0, 12.0 - (app.annual_household_income - 90_000) / 20_000 * 3.0)
        financial   = min(25.0, financial + app.dependents * 0.8)
        leadership  = min(25.0, len(app.extracurriculars) * 5.5 + len(app.awards) * 2.0)
        essay       = min(25.0, (len(app.essay) / 700) * 20.0 + (3.0 if app.work_experience else 0.0))

        rubric = RubricScores(round(academic,1), round(financial,1),
                              round(leadership,1), round(essay,1))
        total  = rubric.total

        if   total >= 70: rec = DecisionOutcome.APPROVED
        elif total >= 50: rec = DecisionOutcome.WAITLISTED
        else:             rec = DecisionOutcome.DECLINED

        dist       = min(abs(total - 70), abs(total - 50))
        confidence = min(0.97, 0.50 + dist / 40.0)
        if 48 <= total <= 72: confidence = min(confidence, 0.72)
        if 55 <= total <= 65: confidence = min(confidence, 0.55)

        if   confidence >= self.high_threshold: conf_level = ConfidenceLevel.HIGH
        elif confidence >= self.low_threshold:  conf_level = ConfidenceLevel.MEDIUM
        else:                                   conf_level = ConfidenceLevel.LOW

        return ScoringResult(
            application_id=app.id, rubric_scores=rubric,
            ai_recommendation=rec, confidence=round(confidence, 2),
            confidence_level=conf_level,
            reasoning=(f"Total {total:.1f}/100. Academic:{academic:.1f}, "
                       f"Financial:{financial:.1f}, Leadership:{leadership:.1f}, Essay:{essay:.1f}. "
                       f"{'Clear approval.' if total>=70 else 'Borderline.' if total>=50 else 'Below threshold.'}"),
            raw_scoring="[stub mode]")


class StubOrchestrator:
    def __init__(self, verbose=True, high_threshold=0.78, low_threshold=0.50):
        self.high_threshold  = high_threshold
        self.low_threshold   = low_threshold
        self.analysis_agent  = StubAnalysisAgent()
        self.scoring_agent   = StubScoringAgent(high_threshold, low_threshold)
        self.human_review    = HumanReviewLayer()
        self.verbose         = verbose

    def evaluate(self, application: Application) -> Decision:
        audit = []
        evidence = self.analysis_agent.extract_evidence(application)
        audit.append(AuditStep(step="1_evidence_extraction", agent="StubAnalysisAgent",
                               summary=evidence.overall_narrative,
                               metadata={"key_strengths": evidence.key_strengths,
                                         "key_concerns":  evidence.key_concerns}))

        scoring = self.scoring_agent.score(application, evidence)
        audit.append(AuditStep(step="2_rubric_scoring", agent="StubScoringAgent",
                               summary=f"Total {scoring.rubric_scores.total:.1f}/100 | {scoring.ai_recommendation.value} | conf={scoring.confidence:.2f}",
                               metadata=scoring.rubric_scores.to_dict()))

        review_type = self._route(scoring.confidence)
        audit.append(AuditStep(step="3_routing_decision", agent="StubOrchestrator",
                               summary=f"Routed to: {review_type.value}",
                               metadata={"high_threshold": self.high_threshold,
                                         "low_threshold":  self.low_threshold}))

        human_review = None
        final_outcome = scoring.ai_recommendation
        agreed = None

        if review_type in (ReviewType.PARALLEL, ReviewType.HUMAN_LED):
            human_review  = self.human_review.review(application, scoring, review_type)
            agreed        = human_review.outcome == scoring.ai_recommendation
            final_outcome = human_review.outcome
            audit.append(AuditStep(step="4_human_review",
                                   agent=f"HumanReviewer:{human_review.reviewer_id}",
                                   summary=f"Human: {human_review.outcome.value} | Agreed: {agreed}",
                                   metadata={"override_reason": human_review.override_reason}))
        else:
            audit.append(AuditStep(step="4_human_review", agent="StubOrchestrator",
                                   summary="Skipped — high-confidence AI-only."))

        audit.append(AuditStep(step="5_final_decision", agent="StubOrchestrator",
                               summary=f"FINAL: {final_outcome.value.upper()}",
                               metadata={"review_type": review_type.value}))
        return Decision(application_id=application.id,
                        applicant_name=application.name,
                        review_type=review_type,
                        evidence=evidence, scoring=scoring,
                        human_review=human_review, final_outcome=final_outcome,
                        agreed=agreed, audit_trail=audit)

    def _route(self, confidence: float) -> ReviewType:
        if   confidence >= self.high_threshold: return ReviewType.AI_ONLY
        elif confidence >= self.low_threshold:  return ReviewType.PARALLEL
        else:                                   return ReviewType.HUMAN_LED

    def _log(self, msg):
        if self.verbose: print(msg)
