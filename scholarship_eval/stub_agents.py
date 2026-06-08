"""Stub agents — full pipeline without any API calls. Policy and thresholds configurable."""
from .models import (Application, Evidence, RubricScores, ScoringResult,
                     Decision, DecisionOutcome, ConfidenceLevel, ReviewType, AuditStep)
from .human_review     import HumanReviewLayer
from .signal_evaluator import SignalEvaluator
from .policy           import ProgramPolicy, PRESETS


class StubAnalysisAgent:
    def extract_evidence(self, app: Application) -> Evidence:
        # ── Technical Expertise (Quantitative) ───────────────────────────────────
        if app.flight_hours >= 2000:
            tech_c = f"Extensive flight experience: {app.flight_hours:,} hrs. Highly operationally qualified."
        elif app.flight_hours >= 1000:
            tech_c = f"Solid flight experience: {app.flight_hours:,} hrs. Meets baseline mission requirements."
        elif app.flight_hours >= 500:
            tech_c = f"Developing flight experience: {app.flight_hours:,} hrs. Below preferred threshold."
        else:
            tech_c = f"Limited flight hours: {app.flight_hours:,} hrs. Significant gap for mission readiness."

        deg_map = {0: "Bachelor's degree", 1: "Master's degree", 2: "PhD", 3: "Dual PhD"}
        deg_str = deg_map.get(app.advanced_degrees, f"{app.advanced_degrees} advanced degrees")
        tech_c += f" {deg_str} in {app.stem_field}."

        # ── Physical & Medical (Quantitative) ────────────────────────────────────
        if app.physical_fitness_score >= 90:
            phys_c = f"Exceptional physical fitness: {app.physical_fitness_score:.1f}/100."
        elif app.physical_fitness_score >= 80:
            phys_c = f"Strong physical fitness: {app.physical_fitness_score:.1f}/100."
        elif app.physical_fitness_score >= 70:
            phys_c = f"Adequate physical fitness: {app.physical_fitness_score:.1f}/100. Improvement recommended."
        else:
            phys_c = f"Below-threshold fitness: {app.physical_fitness_score:.1f}/100. Remediation required."
        phys_c += f" Medical clearance: {app.medical_clearance}."

        # ── Mission Experience (Qualitative) ─────────────────────────────────────
        if app.prior_missions >= 2:
            mission_c = f"Veteran astronaut: {app.prior_missions} prior missions."
        elif app.prior_missions == 1:
            mission_c = "One prior spaceflight — demonstrated mission readiness."
        else:
            mission_c = "No prior spaceflights — candidate class standard."

        if app.specializations:
            mission_c += f" Specializations: {', '.join(app.specializations)}."
        else:
            mission_c += " No declared specializations."

        # ── Crew / Team Compatibility ─────────────────────────────────────────────
        if app.military_background:
            crew_c = "Military background — trained in hierarchical crew operations and high-stakes teamwork."
        else:
            crew_c = "Civilian background — scientific or engineering team collaboration experience."
        if len(app.specializations) >= 3:
            crew_c += " Multi-role capable; strong crew utility."

        # ── Psychological Readiness (Qualitative) ─────────────────────────────────
        stmt_len = len(app.personal_statement)
        if stmt_len > 600:
            psych_c = "Substantive personal statement demonstrating self-awareness and mission clarity."
        elif stmt_len > 300:
            psych_c = "Adequate personal statement with relevant context."
        else:
            psych_c = "Brief personal statement — limited insight into candidate's motivations."
        if app.psychological_profile:
            psych_c += " Evaluator profile available."

        # ── Strengths & Concerns ──────────────────────────────────────────────────
        strengths, concerns = [], []

        if app.flight_hours >= 1500:         strengths.append(f"High flight hours ({app.flight_hours:,} hrs)")
        if app.physical_fitness_score >= 88: strengths.append(f"Excellent fitness score ({app.physical_fitness_score:.0f}/100)")
        if app.prior_missions >= 1:          strengths.append(f"Prior spaceflight experience ({app.prior_missions} mission(s))")
        if len(app.specializations) >= 3:    strengths.append(f"Multi-specialization: {', '.join(app.specializations[:2])}...")
        if app.awards:                       strengths.append(f"Recognised: {app.awards[0]}")
        if app.advanced_degrees >= 2:        strengths.append(f"Advanced academic credentials ({deg_str})")
        if app.medical_clearance == "Full":  strengths.append("Full medical clearance")
        if stmt_len > 600:                   strengths.append("Compelling, specific personal statement")

        if app.flight_hours < 500:           concerns.append(f"Flight hours below mission threshold ({app.flight_hours} hrs)")
        if app.physical_fitness_score < 75:  concerns.append("Fitness score below recommended baseline")
        if app.medical_clearance != "Full":  concerns.append(f"Medical clearance: {app.medical_clearance}")
        if not app.specializations:          concerns.append("No declared mission specializations")
        if stmt_len < 250:                   concerns.append("Personal statement lacks depth")
        if app.prior_missions == 0 and app.flight_hours < 800:
            concerns.append("Limited operational experience for mission assignment")

        return Evidence(
            application_id=app.id,
            academic_strength=tech_c,
            financial_need_assessment=phys_c,
            leadership_indicators=mission_c,
            community_impact=crew_c,
            essay_quality=psych_c,
            overall_narrative=(
                f"{app.name} is a {app.candidate_level} specialising in {app.stem_field}. "
                f"{tech_c} {phys_c}"
            ),
            key_strengths=strengths or ["Application submitted — meets baseline eligibility"],
            key_concerns=concerns   or ["No major concerns identified"],
            raw_extraction="[stub mode]",
        )


class StubScoringAgent:
    def __init__(self, high_threshold=0.78, low_threshold=0.50, quant_weight=0.50):
        self.high_threshold = high_threshold
        self.low_threshold  = low_threshold
        self.quant_weight   = quant_weight

    def score(self, app: Application, evidence: Evidence) -> ScoringResult:
        # ── Dimension 1: Technical Expertise (Quantitative) 0-25 ─────────────────
        technical = min(22.0, (app.flight_hours / 2500) * 22.0) + min(3.0, app.advanced_degrees * 1.0)
        technical = min(25.0, technical)

        # ── Dimension 2: Physical & Medical Fitness (Quantitative) 0-25 ──────────
        physical = (app.physical_fitness_score / 100) * 22.0
        if app.medical_clearance == "Full":
            physical += 3.0
        elif app.medical_clearance == "Conditional":
            physical -= 3.0
        physical = min(25.0, max(0.0, physical))

        # ── Dimension 3: Mission Experience (Qualitative) 0-25 ───────────────────
        mission = min(12.0, len(app.specializations) * 4.0)
        mission += min(9.0, app.prior_missions * 4.5)
        mission += min(4.0, len(app.awards) * 1.5)
        mission = min(25.0, mission)

        # ── Dimension 4: Psychological Readiness (Qualitative) 0-25 ─────────────
        psych = min(18.0, (len(app.personal_statement) / 650) * 18.0)
        if app.prior_missions >= 1: psych += 4.0
        if app.military_background: psych += 2.0
        psych = min(25.0, psych)

        rubric = RubricScores(
            round(technical, 1),
            round(physical, 1),
            round(mission, 1),
            round(psych, 1),
        )

        # ── Apply signal hierarchy weighting ─────────────────────────────────────
        # Quantitative (verifiable): Technical + Physical
        # Qualitative  (assessed):   Mission Experience + Psychological
        qw  = max(0.40, min(0.80, self.quant_weight))
        qlw = 1.0 - qw
        total = ((technical + physical) * qw * 2.0 +
                 (mission   + psych)    * qlw * 2.0)

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
            application_id=app.id,
            rubric_scores=rubric,
            ai_recommendation=rec,
            confidence=round(confidence, 2),
            confidence_level=conf_level,
            reasoning=(
                f"Total {total:.1f}/100. "
                f"Technical:{technical:.1f}, Physical:{physical:.1f}, "
                f"Mission:{mission:.1f}, Psychological:{psych:.1f}. "
                f"{'Clear selection.' if total>=70 else 'Borderline — human review warranted.' if total>=50 else 'Below selection threshold.'}"
            ),
            raw_scoring="[stub mode]",
        )


class StubOrchestrator:
    def __init__(self, verbose=True, policy: ProgramPolicy = None,
                 high_threshold=None, low_threshold=None):
        self.policy = policy or PRESETS["initial_screening"]
        if high_threshold is not None: self.policy.confidence_high = high_threshold
        if low_threshold  is not None: self.policy.confidence_low  = low_threshold

        self.analysis_agent   = StubAnalysisAgent()
        self.scoring_agent    = StubScoringAgent(
            self.policy.confidence_high,
            self.policy.confidence_low,
            getattr(self.policy, 'quant_weight', 0.50),
        )
        self.signal_evaluator = SignalEvaluator()
        self.human_review     = HumanReviewLayer()
        self.verbose          = verbose

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
