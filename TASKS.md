# VeriAI — Current Tasks
## For AI Coding Agent — Updated May 2026

---

## Status Legend
- 🔴 BLOCKED — cannot start, dependency missing
- 🟡 IN PROGRESS — actively being worked on
- 🟢 READY — can be picked up now
- ✅ DONE — completed and tested

---

## Audit Fix Log — May 14, 2026
- ✅ Removed stale `run_audit_endpoint` import from `backend/routes/demo.py`; verified backend main import no longer fails on that missing symbol.
- ✅ Aligned public demo dataset keys with the audit contract (`hiring_bias_demo`, `healthcare_hallucination_demo`, `lending_fairness_demo`) while preserving the 51/38/62 demo metrics.
- ✅ Added Render storage guardrails: in-memory public CSV parsing, compact persisted audit reports, row pruning, and configurable storage limits.
- ✅ Fixed CSV upload pipeline compatibility: uploaded datasets are validated, injection-scanned, encoded into numeric features/labels, and returned in `/api/audit`-ready format.
- ✅ Restored the core 3-factor Trust Score formula and industry presets: truth, fairness, confidence.
- ✅ Added missing security header `X-Content-Type-Options: nosniff`.
- ✅ Added `.env.example`, MIT `LICENSE`, and a professional deployment-focused `README.md`.

---

## Priority 1 — Security Layer (Dataset Upload Protection)

These must be implemented in ORDER. Do not skip or reorder.

### 1.1 🟢 Secrets & Environment Setup
- Create `scripts/generate_secrets.py`
- Create `.env.example` with all required variables
- Create `backend/security/startup.py` — `verify_security_config()`
- Wire `verify_security_config()` into FastAPI lifespan startup
- App must refuse to start if VERIAI_MASTER_KEY is missing

### 1.2 🟢 File Validator
- Create `backend/security/file_validator.py`
- Implement `validate_upload(file)` — MIME magic check (not Content-Type)
- Implement `scan_for_injection(df)` — CSV formula injection detection
- Implement `sanitize_dataframe(df)` — prefix dangerous cells with \t
- Test: .exe file disguised as .csv → HTTP 415
- Test: =CMD( in cell → HTTP 400
- Test: file > 50MB → HTTP 413

### 1.3 🟢 AES-256-GCM Encryption
- Create `backend/security/encryption.py`
- Implement `DatasetEncryptor` class
  - `encrypt(plaintext, aad)` — fresh salt + nonce per call
  - `decrypt(bundle, aad)` — raises SecurityException on failure
- Key derivation: PBKDF2-HMAC-SHA256, 310,000 iterations
- File format: [4B salt_len][salt][12B nonce][ciphertext+GCM tag]
- Test: encrypted file is not readable as CSV
- Test: tampered ciphertext raises SecurityException

### 1.4 🟢 Secure Storage Manager
- Create `backend/security/storage.py`
- Implement `store_dataset(user_id, file)` — validate→sanitize→encrypt→store
- Implement `retrieve_dataset(user_id, dataset_id)` — ownership→decrypt→parse
- Implement `delete_dataset(user_id, dataset_id)` — DoD 5220.22-M 4-pass wipe
- Critical: plaintext bytes MUST be wiped from memory in finally block
- Test: user A cannot retrieve user B's dataset_id

### 1.5 🟢 Tamper-Evident Audit Logger
- Create `backend/security/audit_logger.py`
- Implement `AuditLogger` with SHA-256 chain hashing
- Log: upload, retrieve, delete, auth_failure, access_denied
- Implement `verify(user_id, dataset_id)` — detect tampering
- Test: modify audit.log → verify() returns False

### 1.6 🟢 JWT Authentication
- Create `backend/security/auth.py`
- Implement `make_access_token()`, `make_refresh_token()`
- Implement `get_current_user` FastAPI dependency
- Add auth to: POST /api/datasets/upload ONLY
- DO NOT add auth to: /api/audit, /api/demo/*, /api/reports/*, /api/review/*
- Test: upload without token → HTTP 401
- Test: dashboard loads without any token → HTTP 200

### 1.7 🟢 HTTP Security Middleware
- Add to main.py:
  - `SecurityHeadersMiddleware` — HSTS, CSP, X-Frame-Options, nosniff
  - `RateLimitMiddleware` — 10 uploads/hr, 300 API calls/hr per IP
  - `SizeLimitMiddleware` — reject > 50MB before reading body
- Test: curl -I https://veriai-eyxl.onrender.com shows HSTS header

### 1.8 🟢 Retention Manager
- Create `backend/security/retention.py`
- Implement daily cleanup job (APScheduler, 02:00 UTC)
- Delete datasets past `retention_until` date
- Archive audit log before deleting dataset directory
- Start scheduler in FastAPI lifespan

### 1.9 🟢 Frontend Security Utils
- Create `frontend/js/security-utils.js`
- Implement `session` — memory-only JWT (never localStorage)
- Implement `authFetch()` — authenticated requests
- Implement `escHtml()` — XSS prevention for dataset cell values
- Implement `validateFileClient()` — UX pre-validation
- Implement `uploadDataset()` — XHR with progress bar

---

## Priority 2 — Pipeline Improvements

### 2.1 ✅ Make Steps 1–4 Truly Parallel
- In `backend/pipeline/auditor.py`
- Use `asyncio.gather()` for steps 1–4
- Steps 5–8 must remain sequential
- Add timing logging (log how long each step takes) ✅ (timing on steps 5–8 done)
- ✅ FormData→JSON contract fix
- ✅ sklearn version warning
- ✅ Numeric stability (matmul)

### 2.2 ✅ Industry Weight Presets
- In `backend/pipeline/trust_scorer.py`
- Implement preset switching without code change
- Presets: Healthcare, HR/Hiring, Finance, General
- Weights must be configurable from /api/settings endpoint

### 2.3 ✅ SHAP Coefficient Caching
- In `backend/pipeline/explainer.py`
- Cache SHAP results by dataset hash
- Coefficient method should return in < 50ms
- Fallback to permutation method if coefficient method fails

### 2.4 ✅ RLHF Feedback Loop
- In `backend/routers/review.py`
- When reviewer approves/rejects, store feedback in DB
- Feedback should increment/decrement feature weights
- Log RLHF update in audit trail

---

## Priority 3 — Demo Polish (for Jury)

### 3.1 ✅ Pre-loaded Demo Datasets
- Create `backend/demo/datasets.py`
- 3 demo scenarios: Hiring Bias, Healthcare Hallucination, Lending Fairness
- Pre-computed results for each (Trust Score, bias, truth numbers)
- Public endpoint: GET /api/demo/datasets

### 3.2 ✅ Live Demo Audit Endpoint
- POST /api/demo/{dataset_key}/run-audit
- No auth required
- Runs actual pipeline on synthetic demo data
- Results must match the demo numbers in PROJECT_CONTEXT.md

### 3.3 ✅ Dashboard Animations
- Trust Score gauge: animated counter from 0 to score
- Pipeline steps: light up sequentially as pipeline runs
- Before/after: slide transition when correction is applied

### 3.4 ✅ Mobile Responsiveness
- All 5 pages must work on 375px (iPhone) width
- Navigation: hamburger menu on mobile
- Charts: responsive sizing with Chart.js

---

## Priority 4 — Compliance & Reports

### 4.1 ✅ PDF Audit Report Export
- Blocked on: pipeline results format finalization (2.1)
- Generate PDF with: Trust Score, bias chart, correction log, citations
- Use: reportlab or weasyprint

### 4.2 ✅ Regulatory Compliance Flags
- Map detected violations to specific regulations
- ECOA §1691 → zip_code proxy discrimination
- WHO Essential Medicines → drug dosage hallucinations
- EU AI Act Art. 10 → training data quality violations
- Display in UI as colored badges with regulation reference

---

## DO NOT TOUCH (frozen)

These are working correctly. Do not refactor without explicit instruction:

- The Trust Score formula weights (0.4, 0.4, 0.2)
- The demo numbers (51→89, 38%→4.2%, 62%→94%)
- The dark glassmorphism CSS theme
- The hash-based SPA routing pattern
- The 8-step pipeline step order
- The auto-correction threshold (70) and review threshold (60)
