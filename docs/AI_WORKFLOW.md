# VeriAI — AI Workflow (AI-Native Operations)

VeriAI runs an **AI intelligence layer** on top of its trust-audit engine. It turns raw
metrics into decisions and business language, so the product behaves like an AI-operated
service rather than a dashboard of numbers.

> **Design guarantee:** every AI component has a **deterministic core** that works on the
> Render free tier with **no API key** and never fabricates numbers. When an LLM key is
> configured, the compliance report can be *polished* by an LLM — but the platform never
> depends on it. This keeps demos and pilots reliable.

## The four AI operators

| Operator | Module | What it decides | Endpoint |
|---|---|---|---|
| **AI Audit Orchestrator** | `services/ai_orchestrator.py` | audit profile, depth, compliance profile, explainability level, review priority, report detail — from dataset characteristics | `POST /api/ai/recommend-profile` |
| **AI Compliance Officer** | `services/compliance_officer.py` | executive summary, business risk, compliance mapping, recommendations, next actions, per-audit customer value | `GET /api/ai/compliance-report/{id}` (+ attached to every audit as `ai_summary`) |
| **AI Review Manager** | `services/review_manager.py` | severity, business impact, recommended reviewer, urgency, recommended action, priority order | `GET /api/ai/review-insights` |
| **Executive Insights** | `services/business_metrics.py` | trust/bias trends, high-risk volume, compliance health, estimated hours saved, business risk level | `GET /api/insights/executive` |

## End-to-end flow

```
Upload dataset
      │
      ▼
[AI Audit Orchestrator]  ── inspects columns + size ──►  recommends profile/depth/compliance
      │                                                   (one-click apply in the UI)
      ▼
Existing trust-audit pipeline  (bias ∥ truth ∥ cluster ∥ distribution → Trust Score)
      │   ← unchanged: same formula, same logic, same API
      ▼
[AI Compliance Officer]  ── reads the result ──►  ai_summary attached to the audit
      │                                            (what / why / impact / action / who)
      ▼
Trust < threshold?  ──► Review queue ──► [AI Review Manager] prioritizes + advises
      │                                   (humans approve / reject / escalate — unchanged)
      ▼
[Executive Insights]  ── aggregates all audits ──►  business KPIs for leadership
```

## How the deterministic core works (no black box)

- **Orchestrator** scans column names for sensitive-domain keywords (hiring / finance /
  healthcare) and protected attributes, and scales depth to row/column counts. The
  `compliance_profile` it returns is one of the existing `INDUSTRY_PRESETS`, so it plugs
  straight into the current weighting logic.
- **Compliance Officer** maps the audit's real `bias`/`truth` scores and `regulatory_flags`
  to named frameworks (EEOC four-fifths, ECOA, EU AI Act Art. 10, NIST AI RMF, GDPR
  Art. 22) using documented thresholds, then renders consultant-grade prose.
- **Review Manager** derives severity from the worst of trust/bias/truth, routes to a
  reviewer by dominant failure mode, and computes a priority score to order the queue.
- **Executive Insights** counts real rows in SQLite. The only derived figure — *time
  saved* — is `audits × MANUAL_AUDIT_MINUTES` (default 240 min) and is always labelled an
  estimate with its basis shown.

## Optional LLM enhancement

`GET /api/ai/compliance-report/{id}?llm_polish=true` will, **only if** `OPENAI_API_KEY` /
`GEMINI_API_KEY` / `LLM_API_KEY` is set, ask an LLM to rewrite the executive and business
summaries for extra fluency — keeping every number intact. Any failure silently falls back
to the deterministic text.
