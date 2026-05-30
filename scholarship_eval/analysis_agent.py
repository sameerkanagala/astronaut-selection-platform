"""
Analysis Agent
==============
Uses Claude to extract structured evidence from a raw scholarship application.

Responsibilities:
  - Parse the application text
  - Identify evidence across five evaluation dimensions
  - Surface key strengths and concerns
  - Return a structured Evidence object ready for the Scoring Agent
"""
import json
import re
from anthropic import Anthropic
from .models import Application, Evidence

# System prompt that defines the Analysis Agent's persona and task
ANALYSIS_SYSTEM_PROMPT = """You are the Analysis Agent in a scholarship evaluation platform.
Your role is to read a scholarship application and extract structured, objective evidence.

You MUST respond with a single valid JSON object — no prose, no markdown fences.
Schema:
{
  "academic_strength": "<concise assessment of academic record, GPA trend, coursework rigor>",
  "financial_need_assessment": "<concise assessment of financial situation and demonstrated need>",
  "leadership_indicators": "<evidence of leadership roles, initiative, mentorship, organizing>",
  "community_impact": "<evidence of service, volunteering, measurable positive impact>",
  "essay_quality": "<assessment of clarity, authenticity, specificity, persuasiveness>",
  "overall_narrative": "<2-3 sentence synthesis of who this applicant is and what motivates them>",
  "key_strengths": ["<strength 1>", "<strength 2>", ...],
  "key_concerns": ["<concern 1>", ...]
}

Rules:
- Be objective and evidence-based. Do not infer beyond what is stated.
- key_strengths and key_concerns should each have 1–4 items.
- Do not recommend an outcome — that is the Scoring Agent's job.
- If information is absent, say "Not reported" rather than speculating.
"""


class AnalysisAgent:
    """
    Extracts structured evidence from a scholarship application using Claude.
    Maintains a short conversation to allow follow-up clarification if needed.
    """

    def __init__(self, client: Anthropic, model: str = "claude-opus-4-6"):
        self.client = client
        self.model = model

    def extract_evidence(self, application: Application) -> Evidence:
        """
        Send the application to Claude and return a structured Evidence object.
        Uses a two-turn conversation: first extraction, then a JSON validation pass.
        """
        application_text = application.to_text()

        # ── Turn 1: Initial extraction ────────────────────────────────────────
        messages = [
            {
                "role": "user",
                "content": (
                    f"Please extract structured evidence from the following application:\n\n"
                    f"{application_text}"
                ),
            }
        ]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=messages,
        )
        raw_extraction = response.content[0].text

        # ── Parse JSON (with a repair turn if needed) ─────────────────────────
        parsed = self._parse_json(raw_extraction)

        if parsed is None:
            # Turn 2: ask Claude to correct its output
            messages.append({"role": "assistant", "content": raw_extraction})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response was not valid JSON. "
                        "Please return ONLY the JSON object with no surrounding text."
                    ),
                }
            )
            retry_response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=ANALYSIS_SYSTEM_PROMPT,
                messages=messages,
            )
            raw_extraction = retry_response.content[0].text
            parsed = self._parse_json(raw_extraction)

        if parsed is None:
            # Fallback — return a minimal evidence record so the pipeline continues
            return Evidence(
                application_id=application.id,
                academic_strength="Extraction failed — manual review required.",
                financial_need_assessment="Extraction failed.",
                leadership_indicators="Extraction failed.",
                community_impact="Extraction failed.",
                essay_quality="Extraction failed.",
                overall_narrative="Extraction failed — manual review required.",
                key_strengths=["Unable to extract"],
                key_concerns=["Evidence extraction error — flag for manual review"],
                raw_extraction=raw_extraction,
            )

        return Evidence(
            application_id=application.id,
            academic_strength=parsed.get("academic_strength", ""),
            financial_need_assessment=parsed.get("financial_need_assessment", ""),
            leadership_indicators=parsed.get("leadership_indicators", ""),
            community_impact=parsed.get("community_impact", ""),
            essay_quality=parsed.get("essay_quality", ""),
            overall_narrative=parsed.get("overall_narrative", ""),
            key_strengths=parsed.get("key_strengths", []),
            key_concerns=parsed.get("key_concerns", []),
            raw_extraction=raw_extraction,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        """Attempt to parse JSON from LLM output, stripping markdown fences."""
        # Strip ```json ... ``` wrappers if present
        cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try extracting the first {...} block
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None
