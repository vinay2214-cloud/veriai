# VeriAI — Production Readiness Report

**Date:** 2026-07-03
**Focus:** Reliability, enterprise UX, deployment quality, and Render Free optimization.
**Non-negotiables honored:** no redesign; Trust Score formula, audit pipeline, API
contracts, security model, and all Phase 1–3 + Hardening features preserved. No business
logic changed. All metrics below are **measured**, not estimated.

> All changes are **uncommitted** in the working tree for review. Nothing was committed,
> pushed, or deployed.

---

## 1. Files changed (this phase) & why

| File | Why |
|---|---|
| `backend/main.py` | **Non-blocking background ML warm-up** (Task 1) primes sklearn/scipy after startup so the first audit is fast without delaying `/health`; **CSP tightened** to `script-src 'self'` now that Chart.js is self-hosted (Task 9) |
| `backend/services/ai_orchestrator.py` | **Domain profiles expanded** to 7 (healthcare, finance, hiring, insurance, education, government, general); each maps to an existing weight preset so the **audit engine is untouched** (Task 5) |
| `frontend/index.html` | Point Chart.js to the **self-hosted** copy; **accessibility** — skip link, ARIA labels/roles, `aria-hidden` on decorative icons, `role="main"`; cache-bust → v24 (Tasks 8, 9) |
| `frontend/src/pages/audit.js` | **Honest pipeline progress** — removed the fake timer that "completed" steps on a 300 ms clock; now shows the real stages for the chosen depth + a **real elapsed timer**, with true per-stage timings rendered from the server response (Task 2) |
| `frontend/src/main.js` | **Offline fast-fail** with a clear message (Task 6); cache-bust → v24 |
| `frontend/src/style.css` | Accessibility CSS — skip link, `:focus-visible` rings, `prefers-reduced-motion` (Task 8) |
| `frontend/vendor/chart.umd.min.js` | **New** — self-hosted Chart.js 4.4.4 (205 KB), removing the jsdelivr CDN runtime dependency (Tasks 7, 9) |

Prior phases' files (logging middleware, timing, lazy imports, AI layer) were **not**
modified — they remain intact.

---

## 2. Issue → root cause → fix

### Task 1 — Render reliability
- **Cold first-audit latency (~1.6 s).** *Root cause:* Phase 2 correctly moved the ML
  import off startup, so the *first* audit paid it. *Fix:* a background warm-up task,
  scheduled after `yield` and run in a thread, primes sklearn/scipy ~3 s after boot.
  **Measured:** `/health` returns in **8.9 ms with sklearn NOT yet loaded**; after warm-up
  the first user audit runs in **~125 ms** (was ~1668 ms). Opt out via
  `VERIAI_DISABLE_WARMUP=1`.
- **`/health` verified instant** — plain dict, not under `/api` (skips timing middleware),
  no heavy imports on the path.

### Task 2 — Faked progress (UX integrity)
- *Root cause:* the audit page marked pipeline steps "complete" on a 300 ms `setInterval`,
  unrelated to real execution. *Fix:* honest indeterminate state — the real stage list for
  the selected depth + a live elapsed-seconds timer; **real** per-stage timings come from
  the server's `reasoning_steps` on completion. No fabricated progress.

### Task 9 — CSP & external CDN
- *Root cause:* Chart.js loaded from `cdn.jsdelivr.net`, requiring the CSP to allow an
  external script origin. *Fix:* self-hosted Chart.js; CSP `script-src` tightened to
  `'self'`. Removes a CDN failure point (relevant on Render Free / restricted networks)
  and hardens the policy. **Verified:** CSP header now `script-src 'self';`.

### Task 5 — Domain-agnostic profiles
- *Fix:* orchestrator detects 7 domains and returns a domain-specific `compliance_framework`
  label + wording, while `compliance_profile` always resolves to an **existing** weight
  preset (`general/healthcare/finance/hiring`). **Verified:** insurance→finance preset,
  education/government→general preset — the engine and weighting math are unchanged.

### Task 6 — Frontend stability
- Added an **offline fast-fail** (`navigator.onLine`) with an actionable message. The client
  already had AbortController timeouts, retry-with-backoff, in-flight GET dedup, and
  endpoint-aware long-audit timeouts (Hardening phase) — verified still present.

### Task 8 — Accessibility
- Added: skip-to-content link, `:focus-visible` rings on all interactive elements,
  `aria-label`s (nav, hamburger with `aria-expanded`, brand), `role="main"` + `aria-live`
  on the content root, `aria-hidden` on decorative icons/avatar, and a
  `prefers-reduced-motion` block.

---

## 3. Before vs After (measured, Python 3.11)

| Metric | Before (this phase) | After |
|---|---|---|
| Startup import (`backend.main`) | ~479 ms | **~479 ms** (warm-up doesn't block startup) |
| Startup RSS | ~107 MB | **~107 MB** |
| Heavy libs at startup | none | **none** (unchanged) |
| `/health` latency | instant | **8.9 ms**, sklearn not loaded |
| **Cold first-audit** | **~1668 ms** | **~125 ms** (background warm-up absorbs the import) |
| Warm audit | ~9–15 ms | **~9–15 ms** (unchanged) |
| Chart.js delivery | jsdelivr CDN | **self-hosted** (0 external scripts) |
| CSP `script-src` | `'self' cdn.jsdelivr.net` | **`'self'`** |
| Peak RSS during audit | ~230 MB | **~230 MB** (< Render 512 MB) |

## 4. Startup time
**~0.48 s** to import the app; port binds and `/health` answers immediately. No heavy ML
libraries load before or during startup.

## 5. Memory usage
Startup/idle **~107 MB**; peak during a live audit **~230 MB** (full ML stack resident) —
comfortably under Render Free's 512 MB. The warm-up raises RSS to the audit level a few
seconds after boot (by design), *after* health checks have passed.

## 6. Cold audit latency
**~125 ms** for the first user audit when the background warm-up is enabled (default),
versus ~1668 ms without it — a **~13× improvement** on the cold path, with **zero** impact
on startup or `/health`.

## 7. Warm audit latency
**~9–15 ms** for a repeat standard-depth audit; **~0 ms** on a cache hit (unchanged; the
audit engine was not modified).

## 8. Render compatibility confirmation
- ✅ `/health` returns immediately, no heavy init, not on the timing/import path.
- ✅ Startup lightweight (~0.48 s, ~107 MB, no ML libs); warm-up is background + opt-out.
- ✅ Single worker safe: CPU-bound stages use a thread pool; DB is async; warm-up off-loop.
- ✅ No external script CDN (self-hosted Chart.js) → resilient on restricted networks.
- ✅ Long audits not aborted client-side (180 s budget for audit/upload endpoints).
- ✅ Structured JSON logs (one object/line) suit Render log drains.
- ✅ Peak memory < 512 MB.

## 9. Final verification (Task 10)

- ✅ **Regression suite:** `backend/tests/` + `test_ml_api.py` → **5 passed**.
- ✅ **All critical workflows return HTTP 200, zero 4xx/5xx:** CSV upload, audit
  (thorough depth), Trust Score, bias, truth, report retrieval, **JSON export**,
  **PDF export** (valid `application/pdf`), AI compliance report, executive insights,
  review queue + review insights, dashboard, orchestrator recommend, settings/recent,
  health.
- ✅ **Warm-up** verified: health instant + sklearn deferred, first audit primed to ~125 ms.
- ✅ **CSP** verified `script-src 'self'`; **no jsdelivr** references in app code.
- ✅ **All frontend JS** passes `node --check`; **Chart.js** self-host validated (parses).
- ✅ **Determinism preserved:** AI operators produce output from real metrics with **no**
  API key; expanded domains never touch the audit engine (presets stay valid keys).
- ✅ **No debug artifacts:** no `print()`, banners, or `console.log` in app code.

## 10. Remaining non-blocking improvements

1. **`/docs` (Swagger UI)** loads Swagger assets from a CDN, so under the tightened CSP it
   renders degraded. Not part of the app flow (`/openapi.json` still works). Recommend
   self-hosting Swagger assets **or** `docs_url=None` in production. *(Left unchanged —
   disabling would remove an endpoint, which is out of scope.)*
2. **Enterprise report sections** are already delivered by the Phase 3 AI Compliance panel
   (Executive Summary, Overall Risk, Trust Score, Business Impact, Compliance Mapping,
   Recommended Actions, Human-Review recommendation, Next Steps). A dedicated
   "Technical Findings / Evidence" sub-block (citations count, per-metric table) would be a
   nice-to-have but was not required to make the report executive-complete.
2. **Dashboard vs. Executive Insights:** the requested KPIs (trust/bias trend, compliance
   health, high-risk, processing time, success proxy) already live on the Executive
   Insights page; consolidating or cross-linking them from the main dashboard is optional.
3. **Warm-up faiss:** the warm-up primes sklearn/scipy (dataset audits). Text-mode RAG
   (faiss/TF-IDF) is primed on first text audit; add it to the warm-up if text audits are
   the primary demo path.
4. **Server-side idempotency key** for `/api/audit` (defense-in-depth beyond the client
   button-disable) if the endpoint is called programmatically.
5. **Bundle/minify** the vanilla JS/CSS for byte savings — payload is already lean
   (~250 KB JS + 205 KB self-hosted Chart.js), so low priority.

---

## Production Readiness Score: **9.0 / 10**

Reliable cold-start and health behavior on Render Free, honest UX, hardened CSP with no
external script dependency, domain-agnostic architecture, full accessibility pass, and a
clean regression (no 4xx/5xx, tests green). The remaining items are non-blocking polish
(Swagger-under-CSP, optional report/dashboard consolidation, faiss warm-up). Nothing in
the demo or judging path is broken or degraded.
