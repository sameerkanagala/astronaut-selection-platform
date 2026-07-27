# Astronaut Candidate Selection Platform

Agentic AI candidate evaluation pipeline — Analysis → Scoring → Signal
Evaluation → Policy-driven Routing → simulated Human Review — now with
**PII redaction via Amazon Bedrock Guardrails** running before any of it.
Astronauts have personal data too: every candidate's personal statement,
psychological profile, specializations, and awards are de-identified
before an AI agent or simulated reviewer ever sees them.

Includes a full Funnel Dashboard (`/dashboard`) and a narrative project
overview (`/about`).

## 1. AWS account & credentials

An IAM user/role with S3 + Bedrock access, then:

```bash
aws configure
```

## 2. Create the dedicated S3 bucket

A bucket just for this project (bucket names are globally unique, so a
good pattern is your account ID as a suffix):

```bash
aws s3 mb s3://astronaut-selection-<your-account-id> --region us-east-1
```

## 3. Upload the candidate applications

```bash
pip install -r requirements.txt

export S3_BUCKET_NAME=astronaut-selection-<your-account-id>
export AWS_REGION=us-east-1

# Upload the 10 JSON files in applications/ to the bucket
aws s3 sync applications/ s3://$S3_BUCKET_NAME/applications/
```

## 4. Create the Bedrock Guardrail (PII redaction)

Use the same guardrail-creation approach as the sibling `bedrock_poc`
project (or reuse an existing PII guardrail already created in your
account) — set `inputEnabled`/`inputAction` explicitly on every PII
entity so masking applies before a model call, not just on output:

```bash
export GUARDRAIL_ID=<id>
export GUARDRAIL_VERSION=<version>
```

## 5. Run locally

```bash
# Stub Demo — zero AWS calls, no env vars needed
python app.py

# Redaction Only — real Bedrock Guardrails, no Claude call
# (requires GUARDRAIL_ID / GUARDRAIL_VERSION / AWS credentials above)
python app.py
```

This is a demo-only application — there is no mode that calls a real LLM,
and no Anthropic API key is ever accepted from a user.

Open `http://localhost:5000`. Open `/dashboard` for the Funnel Dashboard,
or `/about` for the project overview.

## Configurable Settings (in the UI)

| Setting | Description | Default |
|---|---|---|
| Run Mode | Stub Demo / Redaction Only | Stub Demo |
| Preset | Initial Screening / Mission Assignment / Deep Space | Initial Screening |
| Candidates | Select any subset of the 10 candidates | All |

## Deploy on Railway

1. Go to [railway.com](https://railway.com) → **New Project** → **Deploy from GitHub repo**
2. Select this repo — Railway auto-detects `railway.toml` / `Procfile`
3. Set these environment variables on the service:
   ```
   S3_BUCKET_NAME       = astronaut-selection-<your-account-id>
   AWS_REGION           = us-east-1
   GUARDRAIL_ID         = <id>
   GUARDRAIL_VERSION    = <version>
   ```
   (AWS credentials via `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, or
   an attached IAM role.)
4. **Redaction Only has no password gate**, so on a public deployment also
   set `ALLOW_REAL_REDACTION = false`. This makes Redaction Only fall back
   to `StubPIIRedactor` — a local regex-based stand-in with zero AWS calls
   — instead of a real, billed Amazon Bedrock Guardrails call per visitor
   click. The Redaction tab clearly labels which one ran ("Simulated" vs
   "Real Amazon Bedrock Guardrails call"). Leave it unset locally to use
   real Bedrock redaction.

> Stub Demo mode works with zero configuration.

## Project Structure

```
├── app.py                          # Flask app: job queue, 2 run modes, results
├── data_loader.py                  # Dual-backend loader (S3 / local)
├── pii_redaction.py                # PIIRedactor (Bedrock Guardrails)
├── redaction_only_orchestrator.py  # Redaction Only mode orchestrator
├── requirements.txt
├── railway.toml                    # Railway deployment config
├── Procfile                        # Gunicorn start command
├── templates/
│   ├── index.html                  # Evaluator UI (sidebar + audit panel)
│   └── dashboard.html              # Funnel Dashboard
├── static/
│   └── about.html                  # Narrative project overview
├── applications/
│   └── app_001.json … app_010.json # The 10 candidate applications
└── scholarship_eval/
    ├── models.py                   # Data models (Application, Decision, ...)
    ├── mock_data.py                # Legacy — superseded by applications/*.json
    ├── policy.py                   # ProgramPolicy + presets
    ├── analysis_agent.py           # Evidence extraction (Claude)
    ├── scoring_agent.py            # Rubric scoring (Claude)
    ├── orchestrator.py             # Pipeline coordinator (stage 0 + 1-5)
    ├── human_review.py             # Simulated human reviewers
    ├── signal_evaluator.py         # Composite risk + routing
    ├── calibration.py              # AI–human agreement analysis
    └── stub_agents.py              # Offline demo mode
```

## Known limitations

- Bedrock Guardrails' built-in PII catalog has no dedicated entity type for
  mission/organization names, so an agency or unit name mentioned in free
  text won't be masked by the standard catalog alone.
- Single Railway worker (`--workers 1`) is intentional — the in-memory job
  store isn't shared across workers.

All candidate profiles, names, and data in this project are fictional.
