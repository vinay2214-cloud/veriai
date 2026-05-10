# VeriAI — Architecture Reference
## For AI Coding Agent

---

## Repository Structure

```
veriai/
├── backend/
│   ├── main.py                  # FastAPI app, middleware, lifespan, routers
│   ├── routers/
│   │   ├── audit.py             # POST /api/audit (full 8-step pipeline)
│   │   ├── datasets.py          # POST /api/datasets/upload (auth required)
│   │   ├── demo.py              # GET /api/demo/* (public, no auth)
│   │   ├── reports.py           # GET /api/reports/* (public)
│   │   ├── review.py            # GET/POST /api/review/* (public for demo)
│   │   └── settings.py          # GET/POST /api/settings/*
│   ├── pipeline/
│   │   ├── auditor.py           # run_full_pipeline() — orchestrates 8 steps
│   │   ├── bias_detector.py     # Step 1: AIF360 + SHAP
│   │   ├── truth_verifier.py    # Step 2: FAISS + Gemini RAG
│   │   ├── cluster_analyzer.py  # Step 3: KMeans subpopulation fairness
│   │   ├── distribution.py      # Step 4: SciPy drift detection
│   │   ├── trust_scorer.py      # Step 5: Composite Trust Score formula
│   │   ├── auto_corrector.py    # Step 6: AIF360 Reweighing + Gemini fix
│   │   ├── explainer.py         # Step 7: SHAP coefficient method
│   │   └── review_queue.py      # Step 8: Human review routing
│   ├── security/
│   │   ├── startup.py           # verify_security_config() on app start
│   │   ├── auth.py              # JWT: make_access_token, get_current_user
│   │   ├── encryption.py        # DatasetEncryptor (AES-256-GCM)
│   │   ├── file_validator.py    # validate_upload(), scan_for_injection()
│   │   ├── storage.py           # store_dataset(), retrieve_dataset()
│   │   ├── audit_logger.py      # AuditLogger with chain hash integrity
│   │   └── retention.py         # RetentionManager, daily cleanup scheduler
│   ├── models/
│   │   ├── audit.py             # AuditRequest, AuditResult, TrustScore
│   │   ├── dataset.py           # DatasetRecord, UploadResponse
│   │   └── review.py            # ReviewItem, ReviewDecision
│   ├── demo/
│   │   └── datasets.py          # Pre-loaded demo data (public, no auth)
│   └── db/
│       ├── database.py          # aiosqlite connection pool
│       └── migrations/          # SQL migration files
├── frontend/
│   ├── index.html               # SPA entry point
│   ├── css/
│   │   ├── main.css             # Dark glassmorphism base styles
│   │   ├── dashboard.css
│   │   ├── audit.css
│   │   └── components.css
│   └── js/
│       ├── router.js            # Hash-based SPA routing (#/dashboard etc)
│       ├── app.js               # App init, global state
│       ├── pages/
│       │   ├── dashboard.js     # #/dashboard
│       │   ├── audit.js         # #/audit — pipeline trigger + results
│       │   ├── reports.js       # #/reports
│       │   ├── review.js        # #/review
│       │   └── settings.js      # #/settings
│       ├── components/
│       │   ├── trust-gauge.js   # Circular Trust Score gauge
│       │   ├── shap-chart.js    # SHAP waterfall chart (Chart.js)
│       │   ├── before-after.js  # Before/after comparison cards
│       │   └── pipeline-steps.js# Animated 8-step pipeline progress
│       └── security-utils.js    # escHtml(), session, authFetch, validateFile
├── data/
│   ├── knowledge_base/          # WHO, ECOA, EU AI Act PDFs for RAG
│   ├── faiss_index/             # Pre-built FAISS vector index
│   └── demo/                    # Synthetic demo datasets (CSV)
├── docs/
│   ├── veriai-workflow.md       # End-to-end workflow diagram
│   ├── api-reference.md         # All API endpoints documented
│   └── deployment.md            # Render.com deployment guide
├── tests/
│   ├── test_pipeline.py
│   ├── test_security.py
│   ├── test_trust_scorer.py
│   └── test_api.py
├── scripts/
│   └── generate_secrets.py      # One-time secrets generation
├── .cursorrules                 # Agent coding rules (this project)
├── .env.example                 # Env var template (commit this)
├── .env                         # Actual secrets (NEVER commit)
├── PROJECT_CONTEXT.md           # What this project is
├── ARCHITECTURE.md              # This file
├── TASKS.md                     # Current work items
├── requirements.txt
└── README.md
```

---

## Backend Flow — Request Lifecycle

```
HTTP Request
    │
    ├─► SizeLimitMiddleware    (reject > 50MB before reading body)
    ├─► RateLimitMiddleware    (10 uploads/hr, 300 API calls/hr per IP)
    ├─► SecurityHeadersMiddleware (HSTS, CSP, X-Frame-Options, etc.)
    ├─► CORSMiddleware         (allowed origins from env var only)
    │
    ▼
FastAPI Router
    │
    ├─► PUBLIC routes (no auth)
    │       GET  /api/demo/*
    │       POST /api/audit          ← demo audit, public
    │       GET  /api/reports/*
    │       GET  /api/review/*
    │
    └─► PROTECTED routes (JWT required)
            POST /api/datasets/upload   ← Depends(get_current_user)
            GET  /api/datasets          ← Depends(get_current_user)
            DELETE /api/datasets/{id}   ← Depends(get_current_user)
            GET  /api/datasets/{id}/audit-log
```

---

## The 8-Step Pipeline — Code Pattern

```python
# backend/pipeline/auditor.py

async def run_full_pipeline(df: pd.DataFrame, use_case: str) -> AuditResult:
    # Steps 1–4: CONCURRENT
    bias_result, truth_result, cluster_result, dist_result = await asyncio.gather(
        detect_bias(df),
        verify_truth(df),
        analyze_clusters(df),
        check_distribution(df),
    )

    # Steps 5–8: SEQUENTIAL
    trust_score = compute_trust_score(bias_result, truth_result, use_case)
    corrected = await auto_correct(df, trust_score, bias_result, truth_result)
    explanation = explain_with_shap(df, bias_result)
    review_item = route_to_review(trust_score, corrected)

    return AuditResult(
        trust_score=trust_score,
        bias=bias_result,
        truth=truth_result,
        clusters=cluster_result,
        distribution=dist_result,
        correction=corrected,
        explanation=explanation,
        review=review_item,
    )
```

---

## Frontend — Page Routing Pattern

```javascript
// frontend/js/router.js
// Hash-based SPA routing — NO server-side routing needed

const routes = {
  "/dashboard": () => import("./pages/dashboard.js"),
  "/audit":     () => import("./pages/audit.js"),
  "/reports":   () => import("./pages/reports.js"),
  "/review":    () => import("./pages/review.js"),
  "/settings":  () => import("./pages/settings.js"),
};

// ALL routes are PUBLIC — no auth check on navigation
// Auth is only checked inside uploadDataset() action
window.addEventListener("hashchange", () => {
  const path = window.location.hash.replace("#", "") || "/dashboard";
  const page = routes[path];
  if (page) page().then(m => m.render(document.getElementById("app")));
});
```

---

## Database Schema (SQLite via aiosqlite)

```sql
-- Audit results (demo + user audits)
CREATE TABLE audits (
    id          TEXT PRIMARY KEY,
    user_id     TEXT,                    -- NULL for demo audits
    use_case    TEXT NOT NULL,
    trust_score REAL NOT NULL,
    bias_score  REAL NOT NULL,
    truth_score REAL NOT NULL,
    confidence  REAL NOT NULL,
    status      TEXT NOT NULL,           -- trusted|acceptable|marginal|blocked
    corrected   INTEGER DEFAULT 0,       -- 0 or 1
    created_at  TEXT NOT NULL
);

-- Human review queue
CREATE TABLE review_queue (
    id          TEXT PRIMARY KEY,
    audit_id    TEXT REFERENCES audits(id),
    trust_score REAL NOT NULL,
    status      TEXT DEFAULT 'pending',  -- pending|approved|rejected|escalated
    reviewer_id TEXT,
    notes       TEXT,
    decided_at  TEXT,
    created_at  TEXT NOT NULL
);

-- User accounts (optional — demo works without)
CREATE TABLE users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- Dataset metadata (file content stored encrypted on disk)
CREATE TABLE datasets (
    id               TEXT PRIMARY KEY,
    user_id          TEXT REFERENCES users(id),
    original_name    TEXT NOT NULL,
    size_bytes       INTEGER NOT NULL,
    sha256           TEXT NOT NULL,
    row_count        INTEGER,
    column_count     INTEGER,
    uploaded_at      TEXT NOT NULL,
    retention_until  TEXT NOT NULL
);
```

---

## Environment Variables

```bash
# Security (generate with: python scripts/generate_secrets.py)
VERIAI_MASTER_KEY=          # base64(32 bytes) — AES-256 encryption
JWT_SECRET=                 # base64(64 bytes) — JWT signing
DB_ENCRYPTION_KEY=          # base64(32 bytes)

# Deployment
ALLOWED_ORIGINS=https://veriai-eyxl.onrender.com
DATASETS_DIR=/data/datasets
RETENTION_DAYS=30
MAX_FILE_SIZE_MB=50
DEMO_MODE=true              # All pages public during hackathon

# Google Cloud
GEMINI_API_KEY=
VERTEX_AI_PROJECT=
VERTEX_AI_LOCATION=
```

---

## Key Dependencies

```
# requirements.txt
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
aiosqlite>=0.20.0
pandas>=2.2.0
numpy>=1.26.0
scikit-learn>=1.4.0
aif360>=0.6.1
shap>=0.45.0
faiss-cpu>=1.8.0
scipy>=1.13.0
cryptography>=42.0.0
python-magic>=0.4.27
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
apscheduler>=3.10.4
google-generativeai>=0.5.0
```

---

## API Response Format (always this shape)

```json
{
  "success": true,
  "data": {
    "audit_id": "uuid",
    "trust_score": 89,
    "trust_level": "acceptable",
    "bias": {
      "score": 0.042,
      "metric": "demographic_parity_difference",
      "top_feature": "zip_code",
      "corrected": true
    },
    "truth": {
      "score": 0.94,
      "hallucinations_found": 0,
      "sources_cited": 2
    },
    "correction": {
      "applied": true,
      "changes_count": 3,
      "changes": [...]
    },
    "review_required": false
  },
  "error": null
}
```

---

## Design System — Colors (dark glassmorphism)

```css
/* NEVER change these — consistent across all pages */
--navy:        #0D1B3E;   /* primary dark background */
--navy-card:   #152550;   /* card backgrounds */
--teal:        #00C9A7;   /* primary accent */
--teal-dark:   #009B82;   /* hover states */
--white:       #FFFFFF;
--silver:      #B8C8E0;   /* secondary text */
--muted:       #7A90B0;   /* tertiary text */
--danger:      #FF6B6B;   /* bias/error */
--amber:       #FFD166;   /* warning/truth */
--success:     #22C55E;   /* approved/pass */
--glass-bg:    rgba(255,255,255,0.05);
--glass-border:rgba(255,255,255,0.10);
```

Pipeline step colors (fixed — never swap):
```
Step 1 Bias Detection     → #FF6B6B  (red)
Step 2 Truth Verification → #FFD166  (amber)
Step 3 Cluster Analysis   → #4ADE80  (green)
Step 4 Distribution       → #60A5FA  (blue)
Step 5 Trust Scoring      → #00C9A7  (teal)
Step 6 Auto-Correction    → #A78BFA  (purple)
Step 7 SHAP Explain       → #FB923C  (orange)
Step 8 Human Review       → #F472B6  (pink)
```