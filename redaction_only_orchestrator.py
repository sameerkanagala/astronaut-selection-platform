"""Redaction-Only Orchestrator.

Runs PII redaction via StubPIIRedactor (local, zero-cost, regex-based —
see pii_redaction.py), then scores every candidate with the same free
heuristic logic. This demonstrates redaction without any Claude/model
usage or cost, and without calling any third-party PII detection service.

Pipeline: StubPIIRedactor -> StubAnalysisAgent -> StubScoringAgent ->
SignalEvaluator -> routing -> simulated HumanReviewLayer.
"""
from scholarship_eval.models import Application, Decision, ReviewType, AuditStep
from scholarship_eval.stub_agents import StubAnalysisAgent, StubScoringAgent
from scholarship_eval.human_review import HumanReviewLayer
from scholarship_eval.signal_evaluator import SignalEvaluator
from scholarship_eval.policy import ProgramPolicy, PRESETS


class RedactionOnlyOrchestrator:
    def __init__(self, redactor, policy: ProgramPolicy = None, verbose: bool = True):
        """`redactor` is a StubPIIRedactor (or any object sharing its
        `.redact()` interface)."""
        self.policy = policy or PRESETS["initial_screening"]
        self.redactor = redactor
        self.analysis_agent = StubAnalysisAgent()
        self.scoring_agent = StubScoringAgent(
            self.policy.confidence_high, self.policy.confidence_low,
            getattr(self.policy, "quant_weight", 0.50))
        self.signal_evaluator = SignalEvaluator()
        self.human_review_layer = HumanReviewLayer()
        self.verbose = verbose

    def evaluate(self, application: Application) -> Decision:
        audit = []

        self._log(f"\n{'='*55}\n  {application.id} — {application.name} (redaction-only)\n{'='*55}")
        self._log(f"  [0/5] PII Redaction (simulated locally, no AWS call) ...")
        redacted, redaction_report = self.redactor.redact(application)
        entity_counts = redaction_report.entity_counts()
        total_entities = sum(entity_counts.values())
        blocked = redaction_report.blocked_fields()
        source = "Simulated redaction (local pattern matching, no AWS call)"
        summary = (
            f"{source} masked {total_entities} PII entit{'y' if total_entities == 1 else 'ies'} "
            f"({', '.join(f'{t}:{c}' for t, c in entity_counts.items()) or 'none detected'}) "
            f"before this candidate reached the scoring stage."
            + (f" BLOCKED fields (guardrail intervened): {', '.join(blocked)}." if blocked else "")
        )
        audit.append(AuditStep(step="0_pii_redaction", agent="StubPIIRedactor", summary=summary,
                                metadata={"entity_counts": entity_counts, "blocked_fields": blocked,
                                          "guardrail_intervened": redaction_report.guardrail_intervened}))

        self._log("  [1/5] Analysis (stub heuristics, no Claude call) ...")
        evidence = self.analysis_agent.extract_evidence(redacted)
        audit.append(AuditStep(step="1_evidence_extraction", agent="StubAnalysisAgent",
                                summary=evidence.overall_narrative,
                                metadata={"strengths": evidence.key_strengths, "concerns": evidence.key_concerns}))

        self._log("  [2/5] Scoring (stub heuristics, no Claude call) ...")
        scoring = self.scoring_agent.score(redacted, evidence)
        audit.append(AuditStep(step="2_rubric_scoring", agent="StubScoringAgent",
                                summary=(f"Total {scoring.rubric_scores.total:.1f}/100 | "
                                         f"{scoring.ai_recommendation.value} | conf={scoring.confidence:.2f}"),
                                metadata=scoring.rubric_scores.to_dict()))

        self._log("  [3/5] Signal Evaluator ...")
        signals = self.signal_evaluator.evaluate(scoring, evidence, self.policy)
        audit.append(AuditStep(step="3_signal_evaluation", agent="SignalEvaluator",
                                summary=(f"Composite risk: {signals.composite_risk:.2f} | "
                                         f"Sensitivity: {signals.sensitivity_score:.2f} | "
                                         f"Disagreement: {signals.disagreement_score:.2f}"),
                                metadata={"composite_risk": signals.composite_risk,
                                          "sensitivity_flags": signals.sensitivity_flags,
                                          "disagreement_flags": signals.disagreement_flags,
                                          "near_cutoff": signals.near_cutoff}))

        review_type = signals.recommended_route
        audit.append(AuditStep(step="4_routing_decision", agent="RedactionOnlyOrchestrator",
                                summary=f"Routed to: {review_type.value} — {signals.routing_rationale}",
                                metadata={"policy": self.policy.program_name}))
        self._log(f"  [4/5] Routed -> {review_type.value}")

        human_review = None
        final_outcome = scoring.ai_recommendation
        agreed = None
        needs_human = review_type in (ReviewType.PARALLEL_REVIEW, ReviewType.ESCALATION, ReviewType.SENIOR_ADJUDICATION)
        if needs_human:
            self._log("  [5/5] Human Review ...")
            human_review = self.human_review_layer.review(redacted, scoring, review_type, self.policy)
            agreed = human_review.outcome == scoring.ai_recommendation
            final_outcome = human_review.outcome
            audit.append(AuditStep(step="5_human_review", agent=f"HumanReviewer:{human_review.reviewer_id}",
                                    summary=f"Human: {human_review.outcome.value} | Agreed: {agreed}",
                                    metadata={"override_reason": human_review.override_reason}))
        else:
            audit.append(AuditStep(step="5_human_review", agent="RedactionOnlyOrchestrator",
                                    summary="Skipped — auto decision (low risk, high confidence)."))
            self._log("  [5/5] Human review skipped (auto decision)")

        audit.append(AuditStep(step="6_final_decision", agent="RedactionOnlyOrchestrator",
                                summary=f"FINAL: {final_outcome.value.upper()}"))
        self._log(f"  -> {final_outcome.value.upper()}")

        return Decision(
            application_id=application.id, applicant_name=application.name,
            review_type=review_type, evidence=evidence, scoring=scoring,
            human_review=human_review, final_outcome=final_outcome,
            agreed=agreed, audit_trail=audit, signals=signals,
            redacted_application=redacted, redaction_report=redaction_report)

    def _log(self, msg):
        if self.verbose:
            print(msg)
