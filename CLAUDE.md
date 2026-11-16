# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (no AWS or Anthropic credentials needed)
python app.py
# Open http://localhost:5000

# This is a demo-only app: there is no mode that calls a real LLM, no
# Anthropic API key is ever accepted from a visitor, and PII redaction is
# a local regex-based pass with no third-party call.

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
| `AWS_REGION` | Region for S3 (default `us-east-1`) |

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

Use the `/api/results` endpoint or the Past Runs dropdown on `/dashboard`.

### Caching (S3 mode)

`data_loader.py` keeps an in-memory applications cache (5-min TTL; a miss
lists `applications/` and fetches all objects concurrently) and caches the
`list_results()` output. `save_results` writes `applicant-count`, `run-id`
and `timestamp` as S3 object metadata so listing needs only a HeadObject per
file (cached per key+ETag), not a body download; older files without that
metadata fall back to a one-time body read. `save_results` clears the
results-list cache. Note application ids (`IEA-001`) differ from their
object keys (`applications/app_001.json`).

## Architecture

Every candidate now passes through a redaction stage before anything else,
then the same 5-stage evaluation pipeline as before:

0. **StubPIIRedactor** (`pii_redaction.py`) — local, zero-cost regex-based
   redaction. Masks PII in `personal_statement`, `psychological_profile`,
   `specializations`, and `awards` before any simulated reviewer sees
   them. Produces a `RedactedApplication` + `RedactionReport` (entities
   masked, blocked fields).
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

The UI has no mode toggle — every visitor runs the same fixed pipeline
(`redaction_only`). `app.py`'s `/api/evaluate` still accepts a `mode` field
and supports two backend modes (used if called directly, e.g. from a
script), but the frontend always sends `redaction_only`. This is a
demo-only app — there is no mode that calls a real LLM, and no Anthropic
API key is ever accepted from a visitor:

- **Stub Demo** — pure heuristic simulation, no redaction stage at all.
  Not exposed in the UI; only reachable by calling `/api/evaluate` directly.
- **Redaction Only** — `StubPIIRedactor` redacts every candidate (provable
  in the per-candidate Redaction tab, labeled "Simulated"), then scoring
  uses the same free heuristic logic. No Claude call, no model cost, no
  AWS call beyond S3 storage.

### Data layer

- `data_loader.py` — dual-backend loader; S3 in production, local
  `applications/`/`results/` folders in dev.
- `pii_redaction.py` — `StubPIIRedactor` (zero-cost local regex-based
  redaction, the only redactor this app has), `RedactedApplication`,
  `RedactionReport` (carries an `engine` field, always `"stub"`, kept for
  compatibility with older saved result files), `RedactionFinding`.
- `redaction_only_orchestrator.py` — `RedactionOnlyOrchestrator` (stub
  redaction + stub scoring, used by Redaction Only mode).
- `scholarship_eval/orchestrator.py` — `Orchestrator` (a real-Claude-calling
  orchestrator originally used by the now-removed Live Claude mode). No
  longer imported anywhere in `app.py`; kept only as reference code. Safe
  to delete along with `analysis_agent.py`/`scoring_agent.py` (the
  Claude-calling agents it used) if you want the repo fully lean.
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
GET  /dashboard      → Funnel Dashboard (Chart.js, 6 tabs)
GET  /about          → narrative project overview
```

Events are typed: `start`, `processing`, `result`, `calibration`, `saved`,
`done`, `error`. The frontend polls every ~600–800ms. This polling
architecture avoids SSE buffering issues on Railway and similar reverse
proxies.

### Frontend

- `templates/index.html` — single-page evaluator. Sidebar has Candidates +
  Run Evaluation always visible up top, then the Preset field (with its
  description), then a single "Configure" dropdown that swaps between
  settings sections (Confidence & Routing — the default, Decision
  Sensitivity, Signal Hierarchy, Disagreement Controls, Oversight) one at a
  time, no run-mode toggle (fixed demo mode), per-candidate
  audit panel with 6 tabs (Application, Redaction, Rubric, Scores, Signals,
  Audit). The Redaction tab always labels results "Simulated" (local
  pattern matching, no AWS call).
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
