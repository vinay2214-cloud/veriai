# VeriAI — Phase 1: Production Stability Report

_Date: 2026-07-02 · Scope: reliability & correctness only (no new features, no architecture changes, no business-logic changes)._

## Summary

A full end-to-end audit of the backend routes, services/audit pipeline, frontend,
dependencies, and deployment config was performed. **21 files changed**
(+293 / −185), covering exception-handling hardening, one determinism fix,
frontend request-path fixes, dead/duplicate file removal, and dependency
correctness. All changed Python files pass `py_compile` and the full backend
package compiles cleanly; all changed JS files pass `node --check`.

**Key correction to initial triage:** the Gemini (`google-genai`) and LLM
(`litellm`) imports are wrapped in `try/except → None`, so the app already
degrades gracefully to the local TF-IDF path instead of crashing. These features
are simply *inactive* in production (their packages aren't installed), not
broken. Adding those packages was therefore **rejected** as a stability change —
it would activate an unguarded `json.loads` + external call path.

## Bugs fixed

### 500-risk / lost-data hardening (backend)
1. **`report.py`** — the inline `json.loads(row[10])` (column_mapping) was
   unguarded while the sibling `report_json` parse was guarded; a corrupt/legacy
   row returned **500 and blocked report retrieval entirely**. Now guarded.
2. **`report.py`** — PDF export called `step.get('status').upper()` and
   `review.get('status').upper()` on possibly-`None` values (`AttributeError`
   → 500) and the entire `reportlab` build was unguarded. Both fixed; build
   wrapped to return a clean 500 detail.
3. **`audit.py` `/audit/run-mapped`** — `run_audit` was completely unguarded
   (a user data/mapping `ValueError` returned **500 instead of 400**). Now
   wrapped like `/audit`.
4. **`audit.py` + `llm_audit.py`** — `db.insert_audit` / `insert_review` ran
   unguarded *after* an expensive completed audit; a DB hiccup turned a finished
   audit into a 500 and discarded the result. Persistence is now wrapped so the
   result is still returned.
5. **`upload.py` knowledge-base `add`/`bulk`/`stats`** — raw `sqlite3.connect`
   with no error handling **leaked connections** and 500'd on any DB lock/error.
   Rewritten with `try/except sqlite3.Error → 503` + `finally: conn.close()`.
   Removed a now-double `conn.close()`.
6. **`bias_scan.py`, `dashboard.py` (`compare_models`), `ml.py` (`generate_shap_explanation`)**
   — each had a single unguarded service call that bypassed otherwise-careful
   error handling. All wrapped.
7. **`review.py`** — approve/reject/escalate wrote to the DB unguarded and
   **silently "succeeded" on non-existent audit IDs**. Added a 404 existence
   check and wrapped writes (→ 503 on failure).
8. **`feedback.py`, `truth_check.py`** — service calls guarded; `truth-check`
   `claim` now has a `max_length=8000` cap (timeout/hang protection) and
   external failures return 502 instead of 500.
9. **`scoring_service.py`** — trust weights read via `.get(k, default)` so a
   partial `CUSTOM_WEIGHTS` can no longer `KeyError` inside every audit.

### Determinism
10. **`reasoning_chain._cache_key`** — the audit cache keyed on input only, so
    after a weight change (Settings page or the RLHF review loop) the same input
    returned a **stale cached trust score**. Active weights are now folded into
    the cache key → "same input + same weights → same score", and a weight
    change correctly invalidates the cache. This is the single most important
    correctness fix for an auditing product.

### Frontend
11. **`audit.js`** — the primary "Run Full Audit" call used a raw
    `fetch('/api/audit')` that bypassed the resolved API base (404'd in dev and
    on any split-origin deploy). Switched to `api.post('/audit')`, matching the
    sibling LLM-audit call and inheriting retry/timeout/error handling.
12. **`reports.js`** — PDF/JSON export links hardcoded `/api/...`; now built
    from the resolved API base (exposed via `window.__VERIAI_API_BASE__` in
    `main.js` to avoid a circular/duplicate-module import). Null-guarded
    `audit_id.substring`.
13. **`feedback.js`** — null-guarded `audit_id.substring` and the post-submit
    history refresh (`null.slice()` on a failed refetch).

### Cleanup (dead / duplicate / junk)
14. Removed 10 untracked macOS `* 2.*` copy-artifacts (incl. `bias_service 2.py`,
    6 `security/* 2.py`, 3 requirements/env dupes) and their stale `.pyc` twins;
    removed untracked `debug.log` and a committed local `veriai.db`.
15. `git rm` of committed junk (`test_layout.html`, `test_title.js`) and dead
    source: `backend/services/vector_service.py` (imported by nobody; also had a
    wrong `dimension=1536`), `backend/routes/demo.py` (unregistered dead route
    that conflicted with `demo_routes.py`), `frontend/js/security-utils.js`
    (dead re-export shim).

### Dependencies & startup latency
16. Removed `google-generativeai` from both requirements files — it is the
    **wrong SDK** (code uses `from google import genai`, i.e. `google-genai`) and
    is never imported; it only bloated the image.
17. Moved `pytest`/`httpx` out of the production image into a new
    `backend/requirements-dev.txt` (the Dockerfile installs
    `backend/requirements.txt` only).
18. Lazy-loaded heavy libs off the startup path: `faiss` + `TfidfVectorizer`
    (now imported inside the two functions that use them in `truth_service.py`),
    `reportlab` (now imported inside the PDF-export branch of `report.py`), and
    dropped the `from sklearn.exceptions import ...` at the top of `main.py`
    (replaced with a message-based warning filter) so sklearn is no longer
    imported on the very first line of process startup.

## Files modified (21)

Backend: `main.py`, `requirements.txt`, `routes/{audit,bias_scan,dashboard,feedback,llm_audit,ml,report,review,truth_check,upload}.py`, `services/{reasoning_chain,scoring_service,truth_service}.py`.
Frontend: `src/main.js`, `src/pages/{audit,reports,feedback}.js`.
Root: `requirements.txt`. New: `backend/requirements-dev.txt`.
Deleted: `backend/routes/demo.py`, `backend/services/vector_service.py`, `frontend/js/security-utils.js`, `test_layout.html`, `test_title.js`, plus untracked dupes/junk.

## Verification performed
- `py_compile` on all 14 changed backend files → OK.
- `compileall` on the full backend package → OK; no dangling refs to deleted modules.
- `node --check` on all 4 changed JS files → OK.
- Manual confirmation that all `faiss`/`TfidfVectorizer`/`reportlab` symbols are
  used only after their new lazy-import sites (or in deferred annotations).

> Not run: full runtime/integration test. The only local interpreters are stale
> **python 3.9** venvs (deploy target is 3.11) and importing faiss there hangs.
> A representative smoke test should run in a 3.11 container (see Next steps).

## Remaining issues (deferred — need logic changes/tests, out of a stability pass)

| Issue | Location | Risk |
|---|---|---|
| Global `APP_STATE` race: `simulate/mitigate-bias` mutate shared state + run blocking `train_model()` in-request while bias/cluster read it from threads | `bias_service.py`, `training_service.py` | Med (concurrency) |
| `preprocess_data` returns cached `X/feature_names` ignoring its `df` arg → shape/skew mismatch after a df swap | `training_service.py:57` | Med (correctness) |
| Unbounded `_SHAP_CACHE`; SHAP background sampling unseeded (non-deterministic explanations) | `explainability_service.py` | Low–Med |
| Threshold gap: decision cutoff `0.70` vs review flag `0.60` — scores in [0.60,0.70) never queued for review | `reasoning_chain.py` vs `config.py` | Low (logic) |
| Endpoints return `{"error":...}` at HTTP **200** (frontend depends on this) | `correction.py`, `demo_routes.py`, `upload.py` | Low (contract; intentionally left) |
| `render.yaml` uses paid `plan: starter` + persistent disk (not free-tier compatible) | `render.yaml` | Deploy/cost — Phase 2 |
| `DEMO_MODE` env var set but never read in code | `render.yaml` | Cosmetic |

## Risk level

**Low.** Changes are additive guard rails (try/except, null checks, input caps),
pure-caching determinism, request-path corrections, and removal of files proven
unused. No business logic, formulas, schemas, or response contracts were changed.
The 200-with-`error` contracts the frontend relies on were deliberately left
intact. Highest-touch file (`upload.py`) was restructured only around
connection lifecycle.

## Recommended next steps
1. Build the 3.11 Docker image and run a smoke test hitting `/health`, `/api/audit`
   (text + dataset), `/api/upload-csv`, `/api/report/{id}` JSON+PDF, and the
   review approve/reject flow — confirm no 500s.
2. Pin dependency versions in `backend/requirements.txt` (currently floating
   `>=`, a drift risk against aif360/sklearn) — Phase 2.
3. Proceed to **Phase 2 (Performance)**: measure cold-start before/after the
   lazy-import changes; address the deferred concurrency/cache items above.
4. Address the `render.yaml` free-tier/cost decision (keep paid disk vs. migrate
   SQLite → Postgres).
