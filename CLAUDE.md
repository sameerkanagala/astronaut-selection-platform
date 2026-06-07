# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (stub mode — no API key needed)
python app.py
# Open http://localhost:5000

# Run with live Claude mode
ANTHROPIC_API_KEY=sk-ant-api03-... python app.py

# Production server (matches Railway deploy)
gunicorn app:app --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 300
```

There are no automated tests. Manual testing is done through the browser UI or by importing `scholarship_eval` modules directly.

## Architecture

This is a single-file Flask app (`app.py`) backed by a pure-Python evaluation package (`scholarship_eval/`). There is no database — all state is in-memory within a request or job.

### Evaluation pipeline (5 stages)

Every applicant passes through the same pipeline, implemented twice — once using real Claude API calls (`Orchestrator`) and once with deterministic heuristics (`StubOrchestrator`):

1. **AnalysisAgent / StubAnalysisAgent** — extracts structured `Evidence` from a raw `Application` (academic, financial, leadership, essay, key strengths/concerns).
2. **ScoringAgent / StubScoringAgent** — produces rubric scores across four 0–25 dimensions (academic, financial, leadership, essay). Scores are weighted by `quant_weight` (policy field) to shift emphasis between verifiable structured data and unverifiable qualitative signals.
3. **SignalEvaluator** — pure-logic module (no LLM). Computes three scores — confidence risk, decision sensitivity, and disagreement score — then combines them into `composite_risk` (0–1). This determines routing tier.
4. **Routing** — `SignalEvaluator._route()` maps composite risk to one of four `ReviewType` tiers: `AUTO_DECISION`, `PARALLEL_REVIEW`, `ESCALATION`, `SENIOR_ADJUDICATION`.
5. **HumanReviewLayer** — simulates human reviewers. Reviewer pool has 5 named personas with different biases and styles. Policy type and routing tier shift which reviewers are selected and how much disagreement is simulated.

Post-pipeline, `CalibrationSystem.analyse()` aggregates all decisions into a `CalibrationReport` with agreement rate, score delta stats, and actionable insights.

### Policy system

`ProgramPolicy` (in `policy.py`) externalises all routing thresholds into one dataclass. Three presets (`high_volume`, `high_dollar`, `regulatory`) demonstrate meaningfully different AI/human agreement behaviour because they alter confidence thresholds, sensitivity rules, disagreement tolerance, reviewer pool weights, and noise parameters together.

The `webapp/` folder is a legacy copy of the codebase from an earlier iteration; the live code is in the root-level `app.py` and `scholarship_eval/`.

### Request flow

```
POST /api/evaluate  → spawns background thread → returns {job_id}
GET  /api/poll/<id> → drains event queue from thread → returns {status, events[]}
```

Events are typed: `start`, `processing`, `result`, `calibration`, `done`, `error`. The frontend polls every second. This polling architecture replaced SSE specifically to avoid Railway proxy buffering.

### Frontend

Single-page app in `templates/index.html` with vanilla JS. All UI state lives in JS variables. The sidebar (accordion) groups controls into Config, Applicants, and Policy sections. Results render as card-per-applicant with tabs (Summary, Evidence, Rubric, Signals, Audit Trail). Calibration renders in a separate panel below the results grid.

## Key data flow types

`Application` → `Evidence` → `ScoringResult` → `SignalEvaluation` → `Decision` (final record with full audit trail). `CalibrationRecord` and `CalibrationReport` are derived from a batch of `Decision` objects.

## Deployment

Deployed on Railway via `railway.toml`. The Procfile and `railway.toml` both specify `gunicorn` with `--workers 1 --threads 4` — single worker is intentional because the in-memory job store (`_jobs` dict in `app.py`) is not shared across workers.
