"""Orchestration Layer — routes applications based on configurable confidence thresholds."""
import datetime
from anthropic import Anthropic
from .models import (Application, Decision, DecisionOutcome,
                     ReviewType, ConfidenceLevel, AuditStep)
from .analysis_agent import AnalysisAgent
from .scoring_agent  import ScoringAgent
from .human_review   import HumanReviewLayer


class Orchestrator:
    def __init__(self, client: Anthropic, model: str = "claude-haiku-4-5-20251001",
                 verbose: bool = True,
                 high_threshold: float = 0.78,
                 low_threshold:  float = 0.50):
        self.high_threshold  = high_threshold
        self.low_threshold   = low_threshold
        self.analysis_agent  = AnalysisAgent(client, model)
        self.scoring_agent   = ScoringAgent(client, model, high_threshold, low_threshold)
        self.human_review_layer = HumanReviewLayer()
        self.verbose         = verbose

    def evaluate(self, application: Application) -> Decision:
        audit = []
        self._log(f"\n{'═'*55}\n  {application.id} — {application.name}\n{'═'*55}")

        self._log("  [1/4] Analysis Agent …")
        evidence = self.analysis_agent.extract_evidence(application)
        audit.append(AuditStep(step="1_evidence_extraction", agent="AnalysisAgent",
                               summary=evidence.overall_narrative,
                               metadata={"key_strengths": evidence.key_strengths,
                                         "key_concerns":  evidence.key_concerns}))

        self._log("  [2/4] Scoring Agent …")
        scoring = self.scoring_agent.score(application, evidence)
        audit.append(AuditStep(step="2_rubric_scoring", agent="ScoringAgent",
                               summary=(f"Total {scoring.rubric_scores.total:.1f}/100 | "
                                        f"{scoring.ai_recommendation.value} | "
                                        f"conf={scoring.confidence:.2f}"),
                               metadata=scoring.rubric_scores.to_dict()))

        review_type = self._route(scoring.confidence)
        audit.append(AuditStep(step="3_routing_decision", agent="Orchestrator",
                               summary=f"Routed to: {review_type.value}",
                               metadata={"confidence": scoring.confidence,
                                         "high_threshold": self.high_threshold,
                                         "low_threshold":  self.low_threshold}))
        self._log(f"  [3/4] Routed → {review_type.value}")

        human_review = None
        final_outcome = scoring.ai_recommendation
        agreed = None

        if review_type in (ReviewType.PARALLEL, ReviewType.HUMAN_LED):
            self._log("  [4/4] Human Review …")
            human_review = self.human_review_layer.review(application, scoring, review_type)
            agreed       = human_review.outcome == scoring.ai_recommendation
            final_outcome = human_review.outcome
            audit.append(AuditStep(step="4_human_review",
                                   agent=f"HumanReviewer:{human_review.reviewer_id}",
                                   summary=(f"Human: {human_review.outcome.value} | "
                                            f"Agreed: {agreed}"),
                                   metadata={"override_reason": human_review.override_reason,
                                             "adjustment": human_review.score_adjustment}))
        else:
            audit.append(AuditStep(step="4_human_review", agent="Orchestrator",
                                   summary="Skipped — high-confidence AI-only."))
            self._log("  [4/4] Human review skipped")

        audit.append(AuditStep(step="5_final_decision", agent="Orchestrator",
                               summary=f"FINAL: {final_outcome.value.upper()}",
                               metadata={"review_type": review_type.value, "agreed": agreed}))
        self._log(f"  ✓ {final_outcome.value.upper()}")

        return Decision(application_id=application.id,
                        applicant_name=application.name,
                        review_type=review_type,
                        evidence=evidence, scoring=scoring,
                        human_review=human_review,
                        final_outcome=final_outcome,
                        agreed=agreed, audit_trail=audit)

    def _route(self, confidence: float) -> ReviewType:
        if confidence >= self.high_threshold:
            return ReviewType.AI_ONLY
        elif confidence >= self.low_threshold:
            return ReviewType.PARALLEL
        else:
            return ReviewType.HUMAN_LED

    def _log(self, msg):
        if self.verbose: print(msg)
