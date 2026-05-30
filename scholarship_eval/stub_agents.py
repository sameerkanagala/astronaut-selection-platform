"""Stub agents — full pipeline without any API calls. Policy and thresholds configurable."""
from .models import (Application, Evidence, RubricScores, ScoringResult,
                     Decision, DecisionOutcome, ConfidenceLevel, ReviewType, AuditStep)
from .human_review     import HumanReviewLayer
from .signal_evaluator import SignalEvaluator
from .policy           import ProgramPolicy, PRESETS


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
        if app.gpa >= 3.7:                    strengths.append(f"Strong GPA ({app.gpa:.2f})")
        if app.annual_household_income < 45_000: strengths.append("Demonstrated financial need")
        if len(app.extracurriculars) >= 2:    strengths.append("Active extracurricular engagement")
        if app.awards:                         strengths.append(f"Recognition: {app.awards[0]}")
        if elen > 500:                         strengths.append("Articulate personal essay")
        if app.gpa < 2.8:                      concerns.append("GPA below competitive threshold")
        if not app.extracurriculars:           concerns.append("No extracurricular activities")
        if elen < 250:                         concerns.append("Essay lacks depth")
        if not app.awards:                     concerns.append("No awards documented")
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
    def __init__(self, high_threshold=0.78, low_threshold=0.50, quant_weight=0.50):
        self.high_threshold = high_threshold
        self.low_threshold  = low_threshold
        self.quant_weight   = quant_weight

    def score(self, app: Application, evidence: Evidence) -> ScoringResult:
        # ── Raw dimension scores (0–25 each) ──────────────────────────────────
        academic  = min(25.0, (app.gpa / 4.0) * 25.0)
        if   app.annual_household_income <= 30_000: financial = 25.0
        elif app.annual_household_income <= 50_000: financial = 20.0 + (50_000 - app.annual_household_income) / 20_000 * 5.0
        elif app.annual_household_income <= 90_000: financial = 12.0 + (90_000 - app.annual_household_income) / 40_000 * 8.0
        else:                                       financial = max(0.0, 12.0 - (app.annual_household_income - 90_000) / 20_000 * 3.0)
        financial   = min(25.0, financial + app.dependents * 0.8)
        leadership  = min(25.0, len(app.extracurriculars) * 5.5 + len(app.awards) * 2.0)
        essay       = min(25.0, (len(app.essay) / 700) * 20.0 + (3.0 if app.work_experience else 0.0))

        rubric = RubricScores(round(academic,1), round(financial,1), round(leadership,1), round(essay,1))

        # ── Apply signal hierarchy weighting ──────────────────────────────────
        # Quantitative (verifiable): Academic + Financial
        # Qualitative (unverifiable): Leadership + Essay
        # Weighted total = quant_pair * quant_weight*2 + qual_pair * qual_weight*2
        # This preserves 0–100 range while shifting weight toward verified data.
        qw   = max(0.40, min(0.80, self.quant_weight))
        qlw  = 1.0 - qw
        total = ((academic + financial) * qw * 2.0 +
                 (leadership + essay)   * qlw * 2.0)

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
            application_id=app.id, rubric_scores=rubric, ai_recommendation=rec,
            confidence=round(confidence, 2), confidence_level=conf_level,
            reasoning=(f"Total {total:.1f}/100. Academic:{academic:.1f}, Financial:{financial:.1f}, "
                       f"Leadership:{leadership:.1f}, Essay:{essay:.1f}. "
                       f"{'Clear approval.' if total>=70 else 'Borderline.' if total>=50 else 'Below threshold.'}"),
            raw_scoring="[stub mode]")


class StubOrchestrator:
    def __init__(self, verbose=True, policy: ProgramPolicy = None,
                 # legacy kwargs kept for backward compat
                 high_threshold=None, low_threshold=None):
        self.policy = policy or PRESETS["high_volume"]
        # Allow direct threshold overrides (used by old CLI code)
        if high_threshold is not None: self.policy.confidence_high = high_threshold
        if low_threshold  is not None: self.policy.confidence_low  = low_threshold

        self.analysis_agent    = StubAnalysisAgent()
        self.scoring_agent     = StubScoringAgent(self.policy.confidence_high, self.policy.confidence_low,
                                                   getattr(self.policy, 'quant_weight', 0.50))
        self.signal_evaluator  = SignalEvaluator()
        self.human_review      = HumanReviewLayer()
        self.verbose           = verbose

    def evaluate(self, application: Application) -> Decision:
        audit = []
        evidence = self.analysis_agent.extract_evidence(application)
        audit.append(AuditStep(step="1_evidence_extraction", agent="StubAnalysisAgent",
                               summary=evidence.overall_narrative,
                               metadata={"strengths": evidence.key_strengths,
                                         "concerns":  evidence.key_concerns}))

        scoring = self.scoring_agent.score(application, evidence)
        audit.append(AuditStep(step="2_rubric_scoring", agent="StubScoringAgent",
                               summary=f"Total {scoring.rubric_scores.total:.1f}/100 | "
                                       f"{scoring.ai_recommendation.value} | conf={scoring.confidence:.2f}",
                               metadata=scoring.rubric_scores.to_dict()))

        signals = self.signal_evaluator.evaluate(scoring, evidence, self.policy)
        audit.append(AuditStep(step="3_signal_evaluation", agent="SignalEvaluator",
                               summary=f"Composite risk: {signals.composite_risk:.2f} | "
                                       f"Sensitivity: {signals.sensitivity_score:.2f} | "
                                       f"Disagreement: {signals.disagreement_score:.2f}",
                               metadata={
                                   "composite_risk":     signals.composite_risk,
                                   "sensitivity_flags":  signals.sensitivity_flags,
                                   "disagreement_flags": signals.disagreement_flags,
                                   "near_cutoff":        signals.near_cutoff,
                               }))

        review_type = signals.recommended_route
        audit.append(AuditStep(step="4_routing_decision", agent="StubOrchestrator",
                               summary=f"Routed to: {review_type.value} — {signals.routing_rationale}",
                               metadata={"policy": self.policy.program_name}))

        human_review  = None
        final_outcome = scoring.ai_recommendation
        agreed        = None

        needs_human = review_type in (
            ReviewType.PARALLEL_REVIEW,
            ReviewType.ESCALATION,
            ReviewType.SENIOR_ADJUDICATION,
        )

        if needs_human:
            human_review  = self.human_review.review(application, scoring, review_type, self.policy)
            agreed        = human_review.outcome == scoring.ai_recommendation
            final_outcome = human_review.outcome
            audit.append(AuditStep(step="5_human_review",
                                   agent=f"HumanReviewer:{human_review.reviewer_id}",
                                   summary=f"Human: {human_review.outcome.value} | Agreed: {agreed}",
                                   metadata={"override_reason": human_review.override_reason}))
        else:
            audit.append(AuditStep(step="5_human_review", agent="StubOrchestrator",
                                   summary="Skipped — auto decision (low risk, high confidence)."))

        audit.append(AuditStep(step="6_final_decision", agent="StubOrchestrator",
                               summary=f"FINAL: {final_outcome.value.upper()}"))

        return Decision(
            application_id=application.id, applicant_name=application.name,
            review_type=review_type, evidence=evidence, scoring=scoring,
            human_review=human_review, final_outcome=final_outcome,
            agreed=agreed, audit_trail=audit, signals=signals)

    def _log(self, msg):
        if self.verbose: print(msg)
