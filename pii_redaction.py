"""
PII Redaction Layer
====================
De-identifies an Application before any of its fields are placed into a
prompt sent to Claude (or shown to the simulated Human Review Layer). This
runs as a pure preprocessing step ahead of the 5-stage evaluation pipeline
(see orchestrator.py), not as a side effect of a model call.

This is a local, zero-cost, regex-based redaction pass — StubPIIRedactor
below — not a real call to any third-party PII detection service. It's a
heuristic demo aid, not a security control: it catches the PII shapes the
demo dataset actually contains (a person's name introduced by a
military/academic honorific, an email address, a phone number), but it
will miss PII shapes outside those patterns.

Design notes
------------
- A structured `name` field is replaced deterministically with a
  non-identifying, stable placeholder tied to the pseudonymous candidate
  id (e.g. "Candidate IEA-001").
- Free-text fields (personal statement, evaluator psychological profile)
  can contain embedded PII that isn't obvious from the field itself — a
  reference to family, a home address, an email mentioned in passing.
  These are scanned with local regex matching, which masks matches with
  tags like {NAME} or {EMAIL}.
- List fields (specializations, awards) are joined with an invisible
  separator into a single pass each, then split back into a list.
- Fields that are legitimate downstream inputs (flight_hours,
  physical_fitness_score, medical_clearance, advanced_degrees,
  prior_missions, age, nationality, stem_field, candidate_level,
  military_background) are NOT redacted here. They're personal in the
  sense that they're about one candidate, but they aren't identifying,
  and the Scoring Agent's rubric explicitly needs them to assess
  technical/physical readiness — redacting them would break the rubric,
  not just hide identity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from scholarship_eval.models import Application

# Free-text fields scanned for embedded PII.
_TEXT_FIELDS = ["personal_statement", "psychological_profile"]
_LIST_FIELDS = ["specializations", "awards"]

# Invisible separator used to bundle list fields into a single pass,
# then split the masked result back into a list.
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
    # Always "stub" — StubPIIRedactor (local regex matching, no AWS call)
    # is the only redactor this app has. Kept as a field for compatibility
    # with any previously saved result files that recorded it.
    engine: str = "stub"

    def entity_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for f in self.findings:
            counts[f.type] = counts.get(f.type, 0) + 1
        return counts

    def blocked_fields(self) -> List[str]:
        """Fields where a finding's action was BLOCK rather than ANONYMIZE.
        StubPIIRedactor only ever anonymizes, so this is always empty in
        practice — kept for compatibility with the report shape."""
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


class StubPIIRedactor:
    """Local, zero-cost PII redaction — no AWS or third-party call of any
    kind. Detects the three PII shapes the demo dataset actually contains:
    a person's name introduced by a military/academic honorific, an email
    address, a phone number.

    This is a heuristic demo aid, not a security control — it will miss
    PII shapes outside these three patterns.
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
