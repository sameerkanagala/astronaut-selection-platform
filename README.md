# Astronaut Candidate Selection Platform

Agentic AI candidate evaluation pipeline — Analysis → Scoring → Signal
Evaluation → Policy-driven Routing → simulated Human Review — with a
**local PII redaction pass** running before any of it. Astronauts have
personal data too: every candidate's personal statement, psychological
profile, specializations, and awards are de-identified (via regex-based
pattern matching, no third-party call) before an AI agent or simulated
reviewer ever sees them.

Includes a full Funnel Dashboard (`/dashboard`) and a narrative project
overview (`/about`).

## 1. AWS account & credentials

An IAM user/role with S3 access, then:

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

## 4. Run locally

```bash
python app.py
```

This is a demo-only application — there is no mode that calls a real LLM,
no Anthropic API key is ever accepted from a user, and PII redaction is a
local regex-based pass with no third-party call (see `pii_redaction.py`).

Open `http://localhost:5000`. Open `/dashboard` for the Funnel Dashboard,
or `/about` for the project overview.

## Configurable Settings (in the UI)

| Setting | Description | Default |
|---|---|---|
| Preset | Initial Screening / Mission Assignment / Deep Space | Initial Screening |
| Candidates | Select any subset of the 10 candidates | All |

There's no run-mode toggle in the UI — every visitor runs the same fixed
demo pipeline (heuristic scoring + a local, simulated redaction pass).

## Deploy on Railway

1. Go to [railway.com](https://railway.com) → **New Project** → **Deploy from GitHub repo**
2. Select this repo — Railway auto-detects `railway.toml` / `Procfile`
3. Set these environment variables on the service:
   ```
   S3_BUCKET_NAME       = astronaut-selection-<your-account-id>
   AWS_REGION           = us-east-1
   ```
   (AWS credentials via `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, or
   an attached IAM role.)

> The demo works with zero configuration beyond the S3 bucket — no AWS
> Bedrock access, no Anthropic API key, nothing else to set up.

## Project Structure

```
├── app.py                          # Flask app: job queue, demo pipeline, results
├── data_loader.py                  # Dual-backend loader (S3 / local)
├── pii_redaction.py                # StubPIIRedactor (local regex-based redaction)
├── redaction_only_orchestrator.py  # Redaction + heuristic-scoring orchestrator
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

- The redaction pass is a local regex-based heuristic, not a security
  control — it catches the PII shapes the demo dataset actually contains
  (names introduced by a title, emails, phone numbers), but it isn't a
  general-purpose PII detector, and mission/organization names aren't
  masked.
- Single Railway worker (`--workers 1`) is intentional — the in-memory job
  store isn't shared across workers.

All candidate profiles, names, and data in this project are fictional.
