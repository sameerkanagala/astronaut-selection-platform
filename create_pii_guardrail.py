"""
One-time setup: creates the dedicated Bedrock Guardrail used by PIIRedactor
to de-identify astronaut candidates before Redaction Only mode reaches the
scoring stage. Independent of any guardrail created for
sibling projects (bedrock_poc, mcp-scholarship-eval-platform) — this one
belongs only to astronaut-selection-platform.

Run once:
    python create_pii_guardrail.py

Prints a guardrail_id and guardrail_version. Set these as env vars (and on
the Railway service — see README.md) before running Redaction Only or Live
Claude mode:
    export GUARDRAIL_ID=<id>
    export GUARDRAIL_VERSION=<version>
"""
import os

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")

# PII entity types masked in free text (personal_statement, psychological_profile,
# specializations, awards). Full catalog:
# docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html
MASKED_PII_TYPES = [
    "NAME",
    "EMAIL",
    "PHONE",
    "ADDRESS",
    "USERNAME",
    "US_SOCIAL_SECURITY_NUMBER",
    "US_PASSPORT_NUMBER",
    "DRIVER_ID",
    "URL",
]

# Financial/account identifiers are blocked outright rather than masked,
# in the unlikely event a candidate mentions one in free text.
BLOCKED_PII_TYPES = [
    "US_BANK_ACCOUNT_NUMBER",
    "US_BANK_ROUTING_NUMBER",
    "CREDIT_DEBIT_CARD_NUMBER",
    "CREDIT_DEBIT_CARD_CVV",
]

# Known gap: Bedrock Guardrails' built-in PII catalog has no
# ORGANIZATION/AGENCY entity type, so a named agency, unit, or employer in
# free text will pass through unmasked. Add known names here as custom
# regex patterns if you need that level of de-identification, e.g.:
#   {"name": "known_agencies", "pattern": r"\b(Acme Space Agency|...)\b",
#    "action": "ANONYMIZE"}
CUSTOM_REGEX_PATTERNS: list[dict] = []


def main():
    bedrock = boto3.client("bedrock", region_name=REGION)

    # IMPORTANT: setting only the legacy `action` field leaves Bedrock's
    # default behavior in place, which is to enable a PII filter on OUTPUT
    # only - input-side evaluation is silently disabled unless inputEnabled
    # and inputAction are set explicitly. Since PIIRedactor calls
    # ApplyGuardrail with source="INPUT" (redacting before anything reaches
    # scoring), every entity below must explicitly enable both sides or the
    # filter never actually runs on the text we're trying to protect.
    def _entity(entity_type: str, action: str) -> dict:
        return {
            "type": entity_type,
            "action": action,
            "inputAction": action,
            "inputEnabled": True,
            "outputAction": action,
            "outputEnabled": True,
        }

    pii_entities_config = [
        _entity(t, "ANONYMIZE") for t in MASKED_PII_TYPES
    ] + [
        _entity(t, "BLOCK") for t in BLOCKED_PII_TYPES
    ]

    sensitive_info_config = {"piiEntitiesConfig": pii_entities_config}
    if CUSTOM_REGEX_PATTERNS:
        sensitive_info_config["regexesConfig"] = [
            {"action": "ANONYMIZE", **pattern} for pattern in CUSTOM_REGEX_PATTERNS
        ]

    response = bedrock.create_guardrail(
        name="astronaut-selection-pii-redaction",
        description=(
            "De-identifies astronaut candidates (name, email, phone, address, SSN, "
            "passport, driver ID, URLs) before they reach the scoring stage. Blocks "
            "records containing bank account or card numbers."
        ),
        sensitiveInformationPolicyConfig=sensitive_info_config,
        blockedInputMessaging=(
            "This input contains information that cannot be processed "
            "automatically and has been flagged for manual review."
        ),
        blockedOutputsMessaging=(
            "The response contained information that cannot be returned and "
            "has been blocked."
        ),
    )

    guardrail_id = response["guardrailId"]
    guardrail_arn = response["guardrailArn"]

    version_response = bedrock.create_guardrail_version(
        guardrailIdentifier=guardrail_id,
        description="Initial version",
    )
    guardrail_version = version_response["version"]

    print("Guardrail created.")
    print(f"  guardrailArn:     {guardrail_arn}")
    print(f"  guardrailId:      {guardrail_id}")
    print(f"  guardrailVersion: {guardrail_version}")
    print()
    print("Export these before running the app locally in Redaction Only or Live mode:")
    print(f"  export GUARDRAIL_ID={guardrail_id}")
    print(f"  export GUARDRAIL_VERSION={guardrail_version}")
    print(f"  export AWS_REGION={REGION}")
    print()
    print("Also set GUARDRAIL_ID and GUARDRAIL_VERSION as Railway service variables.")


if __name__ == "__main__":
    main()
