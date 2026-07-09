"""
PII Redaction Layer
====================
De-identifies an Application before any of its fields are placed into a
prompt sent to Claude (or shown to the simulated Human Review Layer).
Uses Amazon Bedrock Guardrails' standalone `ApplyGuardrail` API, which
scans/masks text independent of any model invocation — this runs as a
pure preprocessing step ahead of the 5-stage evaluation pipeline (see
orchestrator.py), not as a side effect of a model call.

Design notes
------------
- A structured `name` field is replaced deterministically with a
  non-identifying, stable placeholder tied to the pseudonymous candidate
  id (e.g. "Candidate IEA-001"). There's no ambiguity about whether a
  "name" field contains a name, so no need to spend a guardrail call on it.
- Free-text fields (personal statement, evaluator psychological profile)
  can contain embedded PII that isn't obvious from the field itself — a
  reference to family, a home address, an email mentioned in passing.
  These are run through the Bedrock Guardrails sensitive-information
  filter, which masks matches with tags like {NAME} or {EMAIL}, or
  blocks the field entirely for entity types configured as BLOCK.
- List fields (specializations, awards) are joined with an invisible
  separator into a single guardrail call each, then split back into a
  list — same trick used for extracurriculars/awards in the sibling
  scholarship project, so a 10-item award list doesn't cost 10 API calls.
- Fields that are legitimate downstream inputs (flight_hours,
  physical_fitness_score, medical_clearance, advanced_degrees,
  prior_missions, age, nationality, stem_field, candidate_level,
  military_background) are NOT redacted here. They're personal in the
  sense that they're about one candidate, but they aren't identifying,
  and the Scoring Agent's rubric explicitly needs them to assess
  technical/physical readiness — redacting them would break the rubric,
  not just hide identity.
- Known coverage gap: Bedrock Guardrails' built-in PII entity catalog
  does NOT include an ORGANIZATION entity type, so an employer or unit
  name mentioned in free text won't be masked by this alone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import boto3

from scholarship_eval.models import Application

# Free-text fields scanned for embedded PII.
_TEXT_FIELDS = ["personal_statement", "psychological_profile"]
_LIST_FIELDS = ["specializations", "awards"]

# Invisible separator used to bundle list fields into a single guardrail
# call, then split the masked result back into a list.
_JOIN_MARK = "\n⁣⁣⁣\n"


@dataclass
class RedactionFinding:
    field: str
    type: str
    action: str
    match: str = ""  # the raw PII value, for highlighting the "before" view in a report


@dataclass
class RedactionReport:
    application_id: str
    findings: List[RedactionFinding] = field(default_factory=list)
    guardrail_intervened: bool = False
    # "bedrock" (default) = a real ApplyGuardrail call produced this report.
    # "stub" = StubPIIRedactor produced it via local regex matching, no AWS
    # call at all. The frontend's Redaction tab reads this to label the
    # result honestly rather than implying every visitor triggers billed
    # AWS usage.
    engine: str = "bedrock"

    def entity_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for f in self.findings:
            counts[f.type] = counts.get(f.type, 0) + 1
        return counts

    def blocked_fields(self) -> List[str]:
        """Fields where the guardrail's action was BLOCK rather than
        ANONYMIZE. AWS's real API returns the per-entity action as a
        past-tense string ("ANONYMIZED", "BLOCKED") rather than the
        present-tense config-time verb — checking with startswith("BLOCK")
        is robust to either form."""
        return sorted({f.field for f in self.findings if f.action.upper().startswith("BLOCK")})


@dataclass
class RedactedApplication:
    """De-identified view of an Application. Safe to hand to an LLM or
    the simulated Human Review Layer."""
    id: str
    name: str
    age: int
    nationality: str
    stem_field: str
    candidate_level: str
    military_background: bool
    flight_hours: int
    advanced_degrees: int
    physical_fitness_score: float
    medical_clearance: str
    specializations: List[str]
    prior_missions: int
    awards: List[str]
    personal_statement: str
    psychological_profile: str

    def to_text(self) -> str:
        med_str = self.medical_clearance
        mil_str = "Yes" if self.military_background else "No"
        deg_map = {0: "Bachelor's", 1: "Master's", 2: "PhD", 3: "Dual PhD"}
        deg_str = deg_map.get(self.advanced_degrees, f"{self.advanced_degrees} advanced degrees")
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


class PIIRedactor:
    """Wraps Bedrock Guardrails' ApplyGuardrail to de-identify an Application."""

    def __init__(self, guardrail_id: str, guardrail_version: str,
                 region: str = "us-east-1", client: Any = None):
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self.client = client or boto3.client("bedrock-runtime", region_name=region)

    def redact(self, application: Application) -> Tuple[RedactedApplication, RedactionReport]:
        report = RedactionReport(application_id=application.id)
        report.findings.append(RedactionFinding(field="name", type="NAME", action="ANONYMIZE"))
        placeholder_name = f"Candidate {application.id}"

        raw_values: Dict[str, str] = {
            "personal_statement": application.personal_statement or "",
            "psychological_profile": application.psychological_profile or "",
            "specializations": _JOIN_MARK.join(application.specializations or []),
            "awards": _JOIN_MARK.join(application.awards or []),
        }

        # One ApplyGuardrail call per field, rather than bundling every
        # field into a single call — see pii_redaction.py in the sibling
        # scholarship project for the full reasoning (empty `outputs`
        # means nothing was flagged, not an echo of the input).
        masked_values: Dict[str, str] = {}
        for name, text in raw_values.items():
            if not text.strip():
                masked_values[name] = text
                continue

            response = self.client.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.guardrail_version,
                source="INPUT",
                outputScope="FULL",
                content=[{"text": {"text": text}}],
            )

            if response.get("action") == "GUARDRAIL_INTERVENED":
                report.guardrail_intervened = True
                outputs = response.get("outputs", [])
                masked_values[name] = outputs[0]["text"] if outputs else text
            else:
                masked_values[name] = text

            for assessment in response.get("assessments", []):
                pii_entities = assessment.get("sensitiveInformationPolicy", {}).get("piiEntities", [])
                for entity in pii_entities:
                    if entity.get("detected"):
                        report.findings.append(RedactionFinding(
                            field=name, type=entity["type"], action=entity["action"],
                            match=entity.get("match", "")))

        redacted = RedactedApplication(
            id=application.id,
            name=placeholder_name,
            age=application.age,
            nationality=application.nationality,
            stem_field=application.stem_field,
            candidate_level=application.candidate_level,
            military_background=application.military_background,
            flight_hours=application.flight_hours,
            advanced_degrees=application.advanced_degrees,
            physical_fitness_score=application.physical_fitness_score,
            medical_clearance=application.medical_clearance,
            specializations=[s for s in masked_values["specializations"].split(_JOIN_MARK) if s],
            prior_missions=application.prior_missions,
            awards=[s for s in masked_values["awards"].split(_JOIN_MARK) if s],
            personal_statement=masked_values["personal_statement"],
            psychological_profile=masked_values["psychological_profile"],
        )
        return redacted, report


class StubPIIRedactor:
    """Zero-cost stand-in for PIIRedactor, used when ALLOW_REAL_REDACTION is
    false (see app.py) — e.g. on a public deployment where Redaction Only
    mode has no password gate and would otherwise let any visitor trigger
    real, billed Amazon Bedrock Guardrails calls just by clicking a button.

    Detects the same three PII shapes the demo dataset actually contains —
    a person's name introduced by a military/academic honorific, an email
    address, a phone number — using local regex matching instead of a real
    ApplyGuardrail call. Same public `.redact()` interface and return
    shapes as PIIRedactor, so the rest of the pipeline and the UI don't
    need to know which one ran. The only difference downstream is
    RedactionReport.engine ("stub" instead of "bedrock"), which the
    frontend's Redaction tab uses to label the result honestly rather than
    implying a real AWS call happened.

    This is a heuristic demo aid, not a security control — it will miss
    PII shapes outside these three patterns. It exists purely so a public
    visitor can see a convincing before/after redaction demo without
    costing the site owner anything.
    """

    _EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
    _PHONE_RE = re.compile(r"\+?\d[\d\-.\s]{6,}\d")
    _NAME_RE = re.compile(
        r"\b(?:Dr|Prof|Professor|Colonel|Commander|Wing Commander|Captain|Capt|"
        r"Major|General|Mr|Mrs|Ms)\.?\s+[A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,2}\b"
    )
    # Strips a leading honorific off the candidate's own `name` field (some
    # entries store it as e.g. "Dr. Sarah Chen") so _own_name_pattern() can
    # build a plain-name match from what's left.
    _TITLE_PREFIX_RE = re.compile(
        r"^(?:Dr|Prof|Professor|Colonel|Commander|Wing Commander|Captain|Capt|"
        r"Major|General|Mr|Mrs|Ms)\.?\s+"
    )

    def redact(self, application: Application) -> Tuple[RedactedApplication, RedactionReport]:
        report = RedactionReport(application_id=application.id, engine="stub")
        report.findings.append(RedactionFinding(field="name", type="NAME", action="ANONYMIZE"))
        placeholder_name = f"Candidate {application.id}"

        raw_values: Dict[str, str] = {
            "personal_statement": application.personal_statement or "",
            "psychological_profile": application.psychological_profile or "",
            "specializations": _JOIN_MARK.join(application.specializations or []),
            "awards": _JOIN_MARK.join(application.awards or []),
        }

        # The honorific-based _NAME_RE above only catches OTHER people (an
        # evaluator, a reference) introduced with a title. It won't catch the
        # candidate's own name if free text refers back to them by surname
        # alone (e.g. an evaluator writing "...Briggs's performance..."), so
        # build a second pattern from the candidate's own name specifically.
        own_name_re = self._own_name_pattern(application.name)

        masked_values = {
            field_name: self._mask_text(text, field_name, report, own_name_re)
            for field_name, text in raw_values.items()
        }

        redacted = RedactedApplication(
            id=application.id,
            name=placeholder_name,
            age=application.age,
            nationality=application.nationality,
            stem_field=application.stem_field,
            candidate_level=application.candidate_level,
            military_background=application.military_background,
            flight_hours=application.flight_hours,
            advanced_degrees=application.advanced_degrees,
            physical_fitness_score=application.physical_fitness_score,
            medical_clearance=application.medical_clearance,
            specializations=[s for s in masked_values["specializations"].split(_JOIN_MARK) if s],
            prior_missions=application.prior_missions,
            awards=[s for s in masked_values["awards"].split(_JOIN_MARK) if s],
            personal_statement=masked_values["personal_statement"],
            psychological_profile=masked_values["psychological_profile"],
        )
        return redacted, report

    def _own_name_pattern(self, name: str) -> Optional["re.Pattern"]:
        """Build a regex matching the candidate's own name — both the full
        name and the surname alone — from the structured `name` field, so
        it's masked wherever it appears in free text, honorific or not."""
        if not name:
            return None
        plain = self._TITLE_PREFIX_RE.sub("", name).strip()
        tokens = [t for t in re.split(r"\s+", plain) if t]
        if not tokens:
            return None
        alternatives = []
        if len(tokens) > 1:
            alternatives.append(re.escape(plain))  # full name, e.g. "Tom Briggs"
        alternatives.append(re.escape(tokens[-1]))  # surname alone, e.g. "Briggs"
        return re.compile(r"\b(?:" + "|".join(alternatives) + r")\b")

    def _mask_text(self, text: str, field_name: str, report: RedactionReport,
                    own_name_re: Optional["re.Pattern"] = None) -> str:
        if not text.strip():
            return text

        def _sub(pattern: "re.Pattern", entity_type: str, s: str) -> str:
            def _repl(m: "re.Match") -> str:
                report.findings.append(RedactionFinding(
                    field=field_name, type=entity_type, action="ANONYMIZE", match=m.group(0)))
                report.guardrail_intervened = True
                return f"{{{entity_type}}}"
            return pattern.sub(_repl, s)

        text = _sub(self._EMAIL_RE, "EMAIL", text)
        text = _sub(self._PHONE_RE, "PHONE", text)
        if own_name_re:
            text = _sub(own_name_re, "NAME", text)
        text = _sub(self._NAME_RE, "NAME", text)
        return text
