# VeriAI

AI Trust and Safety Auditor Platform by SusAI.

VeriAI audits AI systems for fairness, factual reliability, and governance readiness. It combines dataset bias analysis, hallucination/truth verification, explainability, correction suggestions, and human review into one deployable FastAPI plus vanilla JavaScript application.

Live demo: https://veriai-eyxl.onrender.com

## What VeriAI Does

- Audits uploaded CSV datasets without storing raw files.
- Detects fairness risk with demographic parity and equal opportunity metrics.
- Verifies claims with a local knowledge base and RAG-style retrieval.
- Computes a Trust Score with the fixed formula:

```text
Trust = alpha * truth + beta * (1 - bias) + gamma * confidence
```

- Runs an 8-step pipeline with independent checks in parallel:

```text
1. Bias analysis
2. Truth verification
3. Cluster analysis
4. Distribution analysis
5. Trust scoring
6. Auto-correction recommendation
7. Re-evaluation
8. Human review routing
```

- Provides dashboard, reports, review queue, settings, demo scenarios, and PDF export.

## Demo Scenarios

The public demo includes three pre-loaded scenarios:

- Hiring bias demo
- Healthcare hallucination demo
- Lending fairness demo

Example:

```bash
curl -X POST https://veriai-eyxl.onrender.com/api/demo/hiring_bias_demo/run-audit \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Storage-Light Render Design

VeriAI is configured for jury demos on storage-limited Render deployments.

- Public CSV uploads are parsed in memory only.
- Raw uploaded datasets are not written to disk.
- Uploaded files are capped by size and row count.
- Persisted audit reports are compacted before saving.
- SQLite audit, feedback, review, and knowledge-base rows are pruned with configurable limits.
- Knowledge-base article content is trimmed to keep the demo database bounded.

Key environment limits:

```text
MAX_PUBLIC_UPLOAD_MB=5
MAX_PUBLIC_UPLOAD_ROWS=5000
MAX_AUDIT_RECORDS=75
MAX_REVIEW_RECORDS=100
MAX_FEEDBACK_RECORDS=200
MAX_KB_ARTICLES=75
MAX_REPORT_JSON_CHARS=18000
```

## Architecture

```text
veriai/
|-- backend/
|   |-- main.py                  # FastAPI app, middleware, lifespan
|   |-- routes/                  # API routes
|   |-- services/                # Audit pipeline and ML services
|   |-- security/                # Auth, validation, encryption, retention
|   |-- demo/                    # Pre-loaded demo scenarios
|   `-- database.py              # SQLite helpers and storage pruning
|-- frontend/
|   |-- index.html               # Static SPA shell
|   |-- src/pages/               # Dashboard, audit, reports, review, settings
|   `-- src/security-utils.js    # Client safety helpers
|-- render.yaml                  # Render deployment blueprint
|-- Dockerfile                   # Production container
|-- .env.example                 # Required deployment variables
`-- LICENSE
```

## Local Development

1. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install backend dependencies.

```bash
pip install -r backend/requirements.txt
```

3. Create local environment variables.

```bash
cp .env.example .env
python scripts/generate_secrets.py
```

Add the generated secrets to `.env`.

4. Start the app.

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

5. Open the web app.

```text
http://127.0.0.1:8000
```

API docs are available at:

```text
http://127.0.0.1:8000/docs
```

## Render Deployment

This repository includes `render.yaml` and a production `Dockerfile`.

Recommended Render setup:

- Use Docker runtime.
- Set `DEMO_MODE=true` for the public jury demo.
- Configure all secret env vars in Render, not in git.
- Keep the storage guardrail env vars from `render.yaml`.
- Use the `/health` endpoint for health checks.

Required secrets:

```text
VERIAI_MASTER_KEY
JWT_SECRET
DB_ENCRYPTION_KEY
```

Optional model/API keys:

```text
GEMINI_API_KEY
VERTEX_AI_PROJECT
VERTEX_AI_LOCATION
OPENAI_API_KEY
```

## Useful API Checks

```bash
curl https://veriai-eyxl.onrender.com/health
curl https://veriai-eyxl.onrender.com/api/demo/datasets
curl -X POST https://veriai-eyxl.onrender.com/api/audit \
  -H "Content-Type: application/json" \
  -d '{"input_text":"AI hiring tools treat all genders equally","depth":"fast"}'
```

CSV upload for in-memory dataset parsing:

```bash
curl -X POST http://127.0.0.1:8000/api/upload-csv \
  -F "file=@frontend/sample_bias_data.csv"
```

## Security Notes

- Public demo routes stay open for judges: dashboard, audit, reports, review, and demo endpoints.
- Private dataset upload routes require JWT authentication.
- Security headers, CORS allow-listing, request size limits, and API rate limits are applied by FastAPI middleware.
- Client-side validation improves UX; server-side validation remains authoritative.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
