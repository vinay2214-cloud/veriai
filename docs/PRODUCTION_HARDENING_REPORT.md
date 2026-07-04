# VeriAI — Production Hardening & Render Optimization Report

**Date:** 2026-07-03
**Scope:** Reliability, observability, and Render Free Tier robustness for the `/api/audit`
path and critical workflows. **No new features.** All API contracts, the Trust Score
formula, the deterministic audit pipeline, the security model, and the optional-LLM
architecture are preserved.

> All changes are **uncommitted** in the working tree for review. Nothing was committed,
> pushed, or deployed.

---

## Files changed (5, all additive/internal)

| File | Change |
|---|---|
| `backend/routes/audit.py` | Structured per-stage timing on `/audit` and `/audit/run-mapped`; removed the `=== AUDIT ROUTE ENTERED ===` debug banner |
| `backend/main.py` | `RequestTimingMiddleware` — one structured log per API request (duration + RSS) |
| `backend/logging_config.py` | `JsonFormatter` now merges `extra={...}` context → true structured logging app-wide |
| `backend/services/compliance_officer.py` | `litellm` import made lazy (was module-top) → off the startup path |
| `frontend/src/main.js` | Endpoint-aware request timeouts so long audits aren't aborted; clearer timeout messages |

---

## Issues found → root cause → fix

### 1. Long audits could be aborted client-side (reliability, high)
- **Symptom:** a cold first audit (pays the one-time lazy ML import) or a thorough audit on
  Render Free can exceed 30s. The client applied a blanket `AbortSignal.timeout(30000)` to
  **every** request, including the audit `POST`.
- **Root cause:** `withRequestTimeout()` used a single `DEFAULT_REQUEST_TIMEOUT_MS = 30000`
  for all endpoints. On abort, `request()` returns `null`, so the UI showed "Audit failed"
  even though the server completed the audit — a false failure.
- **Fix:** endpoint-aware timeouts. Audit/upload/demo endpoints get `180000 ms`; everything
  else keeps `30000 ms`. Abort messaging is now endpoint-aware and actionable
  ("…timed out. Try again, or use a lighter audit depth.").

### 2. `litellm` imported at startup (Render startup/memory regression)
- **Symptom:** `compliance_officer.py` did `from litellm import completion` at module top.
  The audit router imports this module at startup, so if `litellm` were installed it would
  load at process start — undoing Phase 2's lightweight-startup guarantee.
- **Root cause:** eager optional-dependency import.
- **Fix:** the import is now lazy, inside `_maybe_llm_polish` (only reached when an LLM key
  is configured). Verified: `import backend.main` loads **no** heavy libs
  (`sklearn/scipy/faiss/shap/litellm/aif360`) at startup.

### 3. No production observability on the hot path
- **Symptom:** no way to see where `/api/audit` spends time or how much RAM a request uses.
- **Root cause:** timings existed only inside the pipeline (`reasoning_steps`); the route
  stages (validation, compliance, persistence, serialization) and per-request metrics were
  unmeasured. The JSON logger also dropped any `extra` context.
- **Fix:** (a) `JsonFormatter` now merges structured `extra`; (b) each audit emits one
  `audit_timing` line with per-stage latency + response size; (c) `RequestTimingMiddleware`
  emits one `request` line per API call with `duration_ms` and `rss_mb`.

### 4. Debug artifact in the request path
- **Root cause:** `logger.info("=== AUDIT ROUTE ENTERED ===")` on every audit.
- **Fix:** removed; replaced by the structured `audit_timing` line. Scans confirm **no**
  `print()`, debug banners, or `console.log` remain in `backend/` or `frontend/src/`.

---

## Instrumentation (what you can now see in logs)

Per audit (`event: "audit_timing"`):
```json
{"event":"audit_timing","audit_id":"…","depth":"standard","from_cache":false,
 "stages_ms":{"validation":0.01,"audit_execution":1666.66,"compliance_summary":0.04,
 "persistence":2.01,"serialization":0.05},"total_ms":1668.77,"response_bytes":7129}
```
Per API request (`event: "request"`):
```json
{"event":"request","method":"POST","path":"/api/audit","status":200,
 "duration_ms":1672.66,"rss_mb":230.6}
```

**What the data proves:** `audit_execution` dominates the *first* audit (one-time lazy ML
import); `compliance_summary` (the Phase 3 AI layer) costs **0.04 ms**, persistence ~2 ms,
serialization ~0.05 ms — i.e. the added AI-native layer imposes no meaningful latency.

---

## Performance improvements

| Metric | Before | After |
|---|---|---|
| First audit (cold, pays lazy import) | ~1.67 s | ~1.67 s (unchanged — one-time) |
| **Warm audit (repeat)** | ~15 ms | ~15 ms (confirmed) |
| Cache-hit audit | ~0 ms | ~0 ms |
| Compliance/AI-summary overhead per audit | — | **0.04 ms** (measured) |
| `/api/audit` bottleneck | unknown | **now attributed** to first-call ML import |

The audit compute path was **not** altered (same formula, same pipeline). The win is
*visibility* plus the removal of the client-side false-failure on long audits.

## Memory improvements

- **Startup RSS unchanged and clean:** `import backend.main` pulls **no** heavy ML libs
  (re-verified after adding the AI layer + middleware); startup import ≈ **382 ms**.
- **`litellm` no longer loads at startup** (lazy) — avoids a multi-MB import on any
  environment where it is installed.
- Peak RSS during an audit (full ML stack resident) observed at ~**230 MB**, well under
  Render Free's 512 MB.

## Render-specific optimizations

- Health check (`/health`) stays off the timing middleware and off the heavy-import path,
  so Render's health probe is instant.
- Long-audit client timeout (180 s) tolerates Render Free cold starts and single-worker
  queuing without dropping valid results.
- Structured JSON logs are Render-log-drain friendly (one object per line, no multiline).
- Non-blocking hot path preserved: CPU-bound stages run in a thread pool
  (`run_in_executor`); DB is async (`aiosqlite`); the AI summary is µs-level sync.

---

## Verification / regression pass

- ✅ **13 critical workflows** via FastAPI `TestClient`, all **HTTP 200, zero 4xx/5xx**:
  CSV upload, audit (cold + warm), Trust Score, bias, truth, report retrieval,
  **JSON export**, **PDF export** (valid `application/pdf`, 4.6 KB), AI compliance report,
  executive insights, review queue + review insights, dashboard stats, orchestrator
  recommend, health.
- ✅ **Unit/regression suite:** `backend/tests/` + `test_ml_api.py` → **5 passed**.
- ✅ **Startup cleanliness:** no `sklearn/scipy/faiss/shap/litellm/aif360` at import.
- ✅ **Determinism preserved:** all AI operators run with **no API key** and produce output
  from real audit metrics; no fabricated scores/evidence.
- ✅ **Contracts unchanged:** existing endpoints return their original shapes; only additive
  behavior (structured logs, longer client timeout, one additive `ai_summary` key from
  Phase 3) was introduced.
- ✅ **No debug artifacts:** confirmed no `print()`, debug banners, or `console.log`.
- ✅ Frontend `node --check` passes.

---

## Remaining non-blocking recommendations

1. **Post-startup ML warm-up** (background task after `/health` is green) to erase the
   ~1.6 s first-audit latency — the only material item the timing data flags.
2. **Sampling for `request` logs** if request volume grows (log 100% of audits, sample
   cheap GETs) to control log spend.
3. **Server-side idempotency key** for `/api/audit` (defense-in-depth beyond the client
   button-disable) if the endpoint is ever called programmatically at scale.
4. **`prune_storage()` off the per-insert path** (already noted in the Phase 2 report) —
   persistence measured ~2 ms today, so this is low priority.
5. **Expose `avg_audit_duration_seconds`** on the Executive Insights UI now that per-stage
   timing is captured, for an ops-facing latency widget.
