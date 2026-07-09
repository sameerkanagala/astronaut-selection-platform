# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (stub mode — no AWS or Anthropic credentials needed)
python app.py
# Open http://localhost:5000

# Run with Redaction Only mode (real Bedrock Guardrails, no Claude call)
GUARDRAIL_ID=... GUARDRAIL_VERSION=... AWS_REGION=us-east-1 python app.py

# Run with Live Claude mode (real Bedrock Guardrails + real Claude)
# Same env vars as above; the Anthropic API key is entered in the UI per-run,
# not set as a server env var — Live mode needs both.

# Production server (matches Railway deploy)
gunicorn app:app --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 300
```

There are no automated tests. Manual testing is done through the browser UI or by importing `scholarship_eval` modules directly.

## Storage

Applications and results are stored in a **dedicated AWS S3 bucket** for
this project (not shared with any sibling project).

- **S3 mode** (production): when `S3_BUCKET_NAME` (and `AWS_REGION`) are set
- **Local mode** (development fallback): reads `applications/*.json`, writes `results/`

### Environment variables

| Variable | Purpose |
|---|---|
| `S3_BUCKET_NAME` | Dedicated S3 bucket for this project's `applications/` and `results/` |
| `AWS_REGION` | Region for both S3 and Bedrock Guardrails (default `us-east-1`) |
| `GUARDRAIL_ID` / `GUARDRAIL_VERSION` | Bedrock Guardrail used by `PIIRedactor` (required for Redaction Only and Live modes) |
| `ALLOW_LIVE_MODE` | Set to `false` on a public deployment to hide Live Claude mode in the UI and reject it server-side (`/api/evaluate` returns 403), so visitors are never invited to paste their own Anthropic API key into an unfamiliar public site. Defaults to enabled (unset = `true`). Stub Demo and Redaction Only are unaffected. |
| `ALLOW_REAL_REDACTION` | Set to `false` on a public deployment to make Redaction Only (and Live Claude's redaction stage) fall back to `StubPIIRedactor` — a local regex-based stand-in with zero AWS calls and zero cost — instead of a real Amazon Bedrock Guardrails call. Redaction Only has no password gate, so without this any visitor could trigger real, billed AWS usage just by clicking a button. Defaults to enabled (unset = `true`). The Redaction tab labels results "Simulated" vs "Real Amazon Bedrock Guardrails call" accordingly, driven by `/api/config`'s `real_redaction_enabled` flag. |

AWS credentials themselves come from the environment/instance role in the
usual boto3 way (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` or an
attached IAM role on Railway) — not passed through the app.

### Bucket layout

```
applications/app_001.json   ← one file per candidate
applications/app_002.json
...
results/results_<timestamp>_<job_id>.json   ← one file per evaluation run
```

### Viewing past runs

Use the `/api/results` endpoint, the Past Runs accordion in the sidebar, or
the Past Runs dropdown on `/dashboard`.

## Architecture

Every candidate now passes through a redaction stage before anything else,
then the same 5-stage evaluation pipeline as before:

0. **PIIRedactor** (`pii_redaction.py`) — real Amazon Bedrock Guardrails
   call. Masks or blocks PII in `personal_statement`, `psychological_profile`,
   `specializations`, and `awards` before any LLM or simulated reviewer sees
   them. Produces a `RedactedApplication` + `RedactionReport` (entities
   masked, blocked fields, guardrail-intervened flag).
1. **AnalysisAgent / StubAnalysisAgent** — extracts `Evidence` from the
   (possibly redacted) `Application`.
2. **ScoringAgent / StubScoringAgent** — produces rubric scores (0–25 × 4
   dimensions: Technical Expertise, Physical & Medical Fitness, Mission
   Experience, Psychological Readiness).
3. **SignalEvaluator** — computes composite risk score, determines routing
   tier.
4. **Routing** — maps composite risk to `ReviewType`.
5. **HumanReviewLayer** — simulates reviewer personas.

### Run modes

Three modes, selectable in the sidebar (and, more narrowly, from the
Funnel Dashboard's own Run control):

- **Stub Demo** — pure heuristic simulation. Zero AWS or Anthropic calls.
- **Redaction Only** — a genuine Bedrock Guardrails call redacts every
  candidate (provable in the per-candidate Redaction tab), but scoring
  still uses the free heuristic logic. No Claude call, no model cost.
  Falls back to `StubPIIRedactor` when `ALLOW_REAL_REDACTION=false`.

When both `ALLOW_LIVE_MODE=false` and `ALLOW_REAL_REDACTION=false` (the
public deployment's permanent state), the Run Mode toggle itself is hidden
in `templates/index.html` — Stub Demo and Redaction Only would otherwise
be functionally identical (same heuristic scoring either way, and no real
AWS call happens in either case), so the UI just always runs the fuller
(simulated) redaction demo instead of offering a choice with no real
difference. See the `bothDisabled` branch of the `/api/config` handler in
`index.html`.
- **Live Claude** — real Bedrock Guardrails redaction, then a real Claude
  call (direct Anthropic API, using the API key entered in the sidebar —
  not `AnthropicBedrock`; only the redaction step touches AWS/Bedrock).

### Data layer

- `data_loader.py` — dual-backend loader; S3 in production, local
  `applications/`/`results/` folders in dev.
- `pii_redaction.py` — `PIIRedactor` (real Bedrock Guardrails),
  `StubPIIRedactor` (zero-cost local regex fallback used when
  `ALLOW_REAL_REDACTION=false`), `RedactedApplication`, `RedactionReport`
  (carries an `engine` field: `"bedrock"` or `"stub"`), `RedactionFinding`.
- `redaction_only_orchestrator.py` — `RedactionOnlyOrchestrator` (real
  redaction + stub scoring, used by Redaction Only mode).
- `scholarship_eval/orchestrator.py` — `Orchestrator` (stage-0 redaction is
  optional via the `redactor=` param; `None` in Stub Demo, a real
  `PIIRedactor` in Live mode).
- `applications/app_001.json` … `app_010.json` — the 10 candidate
  applications (formerly `scholarship_eval/mock_data.py`, now superseded
  by these JSON files + `data_loader.py`; `mock_data.py` is left in place
  but unused).

### Request flow

```
POST /api/evaluate  → background thread → {job_id}
GET  /api/poll/<id> → drain event queue → {status, events[]}
GET  /api/results   → list result files (from S3 or local)
GET  /api/results/<filename> → load a past run
GET  /api/config     → {"live_mode_enabled": bool, "real_redaction_enabled": bool} — drives the UI's Live Claude visibility and Redaction tab labeling
GET  /dashboard      → Funnel Dashboard (Chart.js, 6 tabs)
GET  /about          → narrative project overview
```

Events are typed: `start`, `processing`, `result`, `calibration`, `saved`,
`done`, `error`. The frontend polls every ~600–800ms. This polling
architecture avoids SSE buffering issues on Railway and similar reverse
proxies.

### Frontend

- `templates/index.html` — single-page evaluator. Sidebar has Candidates +
  Run Evaluation always visible up top, a single "Configure" dropdown below
  that swaps between settings sections (Selection Policy, Confidence &
  Routing, Decision Sensitivity, Signal Hierarchy, Disagreement Controls,
  Oversight, Past Runs) one at a time, 3-way run-mode toggle, per-candidate
  audit panel with 6 tabs (Application, Redaction, Rubric, Scores, Signals,
  Audit). The Redaction tab labels each result "Simulated" or "Real Amazon
  Bedrock Guardrails call" based on `/api/config`'s `real_redaction_enabled`.
- `templates/dashboard.html` — Funnel Dashboard. 6 tabs (Funnel Overview,
  AI–Human Alignment, Routing Intelligence, Score Distribution, Risk
  Signals, Reviewer Performance), drilldown tables, Past Runs dropdown.
  Domain-agnostic JS shared in spirit with the sibling `bedrock_poc`
  project's dashboard (not a shared dependency — a parallel copy).
- `static/about.html` — narrative, storytelling-style overview of the
  pipeline, signal hierarchy, routing tiers, and presets; not a technical
  reference.

The `webapp/` folder is a legacy copy of the codebase from an earlier
iteration; the live code is the root-level `app.py` and `scholarship_eval/`.

## Key data flow types

`Application` → (optional) `RedactedApplication` → `Evidence` →
`ScoringResult` → `SignalEvaluation` → `Decision` (final record with full
audit trail, including `redacted_application` and `redaction_report` when
redaction ran). `CalibrationRecord` and `CalibrationReport` are derived
from a batch of `Decision` objects.

## Deployment

Deployed on Railway. Single worker is intentional (in-memory job store).
Results persist across deploys via the dedicated S3 bucket.
