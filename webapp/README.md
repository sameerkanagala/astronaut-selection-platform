# Scholarship Eval Platform

Agentic AI Decision Platform for Scholarship Evaluation — Flask web app with live SSE streaming, configurable confidence thresholds, and a full audit trail dashboard.

## Local Development

```bash
# 1. Clone your repo and enter the folder
git clone https://github.com/YOUR_USERNAME/scholarship-eval-platform.git
cd scholarship-eval-platform

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run (stub mode needs no API key)
python app.py

# 4. Open http://localhost:5000
```

For live Claude mode, set your API key first:
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
python app.py
```

## Push to GitHub

```bash
# Inside the webapp/ folder:
git init
git add .
git commit -m "Initial commit — Scholarship Eval Platform"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/scholarship-eval-platform.git
git push -u origin main
```

## Deploy on Railway

1. Go to [railway.com](https://railway.com) → **New Project** → **Deploy from GitHub repo**
2. Select your `scholarship-eval-platform` repo
3. Railway auto-detects `railway.toml` and uses `gunicorn` — no extra config needed
4. To enable live Claude mode: go to your service → **Variables** → add:
   ```
   ANTHROPIC_API_KEY = sk-ant-api03-...
   ```
5. Railway will redeploy automatically — your app will be live at `https://your-app.railway.app`

> **Note:** Stub/demo mode works with zero configuration — no API key needed.

## Configurable Settings (in the UI)

| Setting | Description | Default |
|---|---|---|
| Run Mode | Stub (no API) or Live (Claude) | Stub |
| API Key | Anthropic API key for live mode | — |
| Model | Haiku / Sonnet / Opus | Haiku |
| High Threshold | Confidence ≥ this → AI-only decision | 0.78 |
| Low Threshold | Confidence < this → human-led decision | 0.50 |
| Applicants | Select any subset of the 10 mock applicants | All |

## Project Structure

```
├── app.py                    # Flask app + SSE streaming
├── requirements.txt
├── railway.toml              # Railway deployment config
├── Procfile                  # Gunicorn start command
├── templates/
│   └── index.html            # Full dashboard UI
└── scholarship_eval/
    ├── models.py             # Data models
    ├── mock_data.py          # 10 simulated applicants
    ├── analysis_agent.py     # Evidence extraction (Claude)
    ├── scoring_agent.py      # Rubric scoring (Claude)
    ├── orchestrator.py       # Pipeline coordinator
    ├── human_review.py       # Simulated human reviewers
    ├── calibration.py        # AI–human agreement analysis
    └── stub_agents.py        # Offline demo mode
```
