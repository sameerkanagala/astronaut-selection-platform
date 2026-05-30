"""
Orchestration Layer
===================
Policy-driven coordinator that evaluates all signals and routes each
application to the appropriate tier: Auto Decision, Parallel Review,
Escalation, or Senior Adjudication.
"""
from anthropic import Anthropic
from .models import Application, Decision, ReviewType, AuditStep
from .analysis_agent   import AnalysisAgent
from .scoring_agent    import ScoringAgent
from .human_review     import HumanReviewLayer
from .signal_evaluator import SignalEvaluator
from .policy           import ProgramPolicy, PRESETS


class Orchestrator:
    def __init__(
        self,
        client:  Anthropic,
        model:   str          = "claude-haiku-4-5-20251001",
        policy:  ProgramPolicy = None,
        verbose: bool          = True,
    ):
        self.policy          = policy or PRESETS["high_volume"]
        self.analysis_agent  = AnalysisAgent(client, model)
        self.scoring_agent   = ScoringAgent(
            client, model,
            high_threshold=self.policy.confidence_high,
            low_threshold=self.policy.confidence_low,
        )
        self.signal_evaluator   = SignalEvaluator()
        self.human_review_layer = HumanReviewLayer()
        self.verbose            = verbose

    def evaluate(self, application: Application) -> Decision:
        audit = []
        self._log(f"\n{'═'*55}\n  {application.id} — {application.name}\n{'═'*55}")

        # Stage 1: Evidence extraction
        self._log("  [1/5] Analysis Agent …")
        evidence = self.analysis_agent.extract_evidence(application)
        audit.append(AuditStep(step="1_evidence_extraction", agent="AnalysisAgent",
                               summary=evidence.overall_narrative,
                               metadata={"strengths": evidence.key_strengths,
                                         "concerns":  evidence.key_concerns}))

        # Stage 2: Rubric scoring
        self._log("  [2/5] Scoring Agent …")
        scoring = self.scoring_agent.score(application, evidence)
        audit.append(AuditStep(step="2_rubric_scoring", agent="ScoringAgent",
                               summary=f"Total {scoring.rubric_scores.total:.1f}/100 | "
                                       f"{scoring.ai_recommendation.value} | conf={scoring.confidence:.2f}",
                               metadata=scoring.rubric_scores.to_dict()))

        # Stage 3: Signal evaluation
        self._log("  [3/5] Signal Evaluator …")
        signals = self.signal_evaluator.evaluate(scoring, evidence, self.policy)
        audit.append(AuditStep(step="3_signal_evaluation", agent="SignalEvaluator",
                               summary=f"Composite risk: {signals.composite_risk:.2f} | "
                                       f"Sensitivity: {signals.sensitivity_score:.2f} | "
                                       f"Disagreement: {signals.disagreement_score:.2f}",
                               metadata={
                                   "composite_risk":    signals.composite_risk,
                                   "sensitivity_score": signals.sensitivity_score,
                                   "disagreement_score":signals.disagreement_score,
                                   "near_cutoff":       signals.near_cutoff,
                                   "sensitivity_flags": signals.sensitivity_flags,
                                   "disagreement_flags":signals.disagreement_flags,
                               }))

        # Stage 4: Routing (policy-driven)
        review_type = signals.recommended_route
        audit.append(AuditStep(step="4_routing_decision", agent="Orchestrator",
                               summary=f"Routed to: {review_type.value} — {signals.routing_rationale}",
                               metadata={"policy": self.policy.program_name}))
        self._log(f"  [4/5] Routed → {review_type.value}")

        # Stage 5: Human review (parallel, escalation, senior)
        human_review  = None
        final_outcome = scoring.ai_recommendation
        agreed        = None

        needs_human = review_type in (
            ReviewType.PARALLEL_REVIEW,
            ReviewType.ESCALATION,
            ReviewType.SENIOR_ADJUDICATION,
        )

        if needs_human:
            self._log("  [5/5] Human Review …")
            human_review  = self.human_review_layer.review(application, scoring, review_type, self.policy)
            agreed        = human_review.outcome == scoring.ai_recommendation
            final_outcome = human_review.outcome
            audit.append(AuditStep(step="5_human_review",
                                   agent=f"HumanReviewer:{human_review.reviewer_id}",
                                   summary=f"Human: {human_review.outcome.value} | Agreed: {agreed}",
                                   metadata={"override_reason": human_review.override_reason,
                                             "adjustment":      human_review.score_adjustment}))
        else:
            audit.append(AuditStep(step="5_human_review", agent="Orchestrator",
                                   summary="Skipped — auto decision (low risk, high confidence)."))
            self._log("  [5/5] Human review skipped (auto decision)")

        audit.append(AuditStep(step="6_final_decision", agent="Orchestrator",
                               summary=f"FINAL: {final_outcome.value.upper()}",
                               metadata={"review_type": review_type.value, "agreed": agreed}))
        self._log(f"  ✓ {final_outcome.value.upper()}")

        return Decision(
            application_id=application.id,
            applicant_name=application.name,
            review_type=review_type,
            evidence=evidence,
            scoring=scoring,
            human_review=human_review,
            final_outcome=final_outcome,
            agreed=agreed,
            audit_trail=audit,
            signals=signals,
        )

    def _log(self, msg):
        if self.verbose: print(msg)
