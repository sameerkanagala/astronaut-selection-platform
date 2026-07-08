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
        redactor              = None,   # PIIRedactor, injected by app.py's live-mode builder
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
        self.redactor            = redactor
        self.verbose            = verbose

    def evaluate(self, application: Application) -> Decision:
        audit = []
        self._log(f"\n{'═'*55}\n  {application.id} — {application.name}\n{'═'*55}")

        # Stage 0: PII redaction (Bedrock Guardrails) — de-identifies the
        # candidate before any LLM or simulated reviewer ever sees it.
        # Every stage below operates on `redacted`, not `application`.
        redaction_report = None
        if self.redactor is not None:
            self._log("  [0/5] PII Redaction (Bedrock Guardrails) …")
            redacted, redaction_report = self.redactor.redact(application)
            entity_counts = redaction_report.entity_counts()
            blocked = redaction_report.blocked_fields()
            audit.append(AuditStep(
                step="0_pii_redaction", agent="PIIRedactor",
                summary=(f"De-identified before any LLM call. Entities masked: "
                         f"{entity_counts or 'none detected'}."
                         + (f" Blocked fields: {blocked}." if blocked else "")),
                metadata={"entity_counts": entity_counts, "blocked_fields": blocked,
                          "guardrail_intervened": redaction_report.guardrail_intervened}))
        else:
            redacted = application

        # Stage 1: Evidence extraction
        self._log("  [1/5] Analysis Agent …")
        evidence = self.analysis_agent.extract_evidence(redacted)
        audit.append(AuditStep(step="1_evidence_extraction", agent="AnalysisAgent",
                               summary=evidence.overall_narrative,
                               metadata={"strengths": evidence.key_strengths,
                                         "concerns":  evidence.key_concerns}))

        # Stage 2: Rubric scoring
        self._log("  [2/5] Scoring Agent …")
        scoring = self.scoring_agent.score(redacted, evidence)
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
            # Human review also operates on the de-identified view when
            # redaction is active — blind review, same as the LLM stages.
            human_review  = self.human_review_layer.review(redacted, scoring, review_type, self.policy)
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
            redacted_application=redacted if self.redactor is not None else None,
            redaction_report=redaction_report,
        )

    def _log(self, msg):
        if self.verbose: print(msg)
