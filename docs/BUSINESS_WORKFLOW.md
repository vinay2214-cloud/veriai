# VeriAI — Business Workflow & Enterprise Use Cases

VeriAI is an **AI Trust & Governance platform**: it lets an organization prove its AI
systems are fair and factually grounded *before* they ship, and keeps evidence for
regulators and customers.

## Who uses it, and what they get

| Role | Uses VeriAI to… | Where in the product |
|---|---|---|
| **Compliance / Risk lead** | Get a defensible, framework-mapped assessment of an AI system | AI Compliance report on every audit |
| **ML / Data engineer** | See exactly which metric failed and what to fix | Trust breakdown + recommendations |
| **Product owner** | Decide go / no-go with a clear business-impact statement | Per-audit "What this means for you" |
| **Executive / leadership** | Track AI governance health and ROI across the org | Executive Insights dashboard |
| **Human reviewer** | Focus on the highest-risk items first | AI-prioritized Review Queue |

## The customer journey

1. **Onboard** — the *Get Started* flow explains what VeriAI does and what to do next.
2. **Upload** — drop a CSV of model decisions or a text output (processed in memory).
3. **AI configures the audit** — the Orchestrator recommends profile/depth/compliance.
4. **Audit runs** — fairness, truth and confidence are scored into one Trust Score.
5. **AI writes the report** — executive summary, business risk, framework mapping,
   recommendations, next actions, and a plain-English "what to do next".
6. **Human review** — low-trust results are queued, prioritized and annotated by AI; a
   human approves, rejects, or escalates (feeding the RLHF loop).
7. **Track impact** — Executive Insights rolls everything up into business KPIs.

## Enterprise use cases

- **Hiring / HR (EEOC):** audit a screening or ranking model for disparate impact under
  the four-fifths rule before it touches candidates.
- **Lending / Finance (ECOA):** demonstrate fair-lending diligence on a credit model,
  including proxy-discrimination signals (e.g. ZIP code).
- **Healthcare (clinical safety):** verify factual grounding of clinical-support outputs
  so unsupported claims are caught before display.
- **General AI governance (EU AI Act / NIST AI RMF):** produce data-governance and
  risk-measurement evidence for high-risk AI systems.

## Business value

- **Time saved:** each automated audit replaces hours of manual analyst work
  (default estimate: 4 hours/audit, configurable) — surfaced transparently on the
  Executive Insights page.
- **Risk reduced:** disparate-impact and hallucination risks are caught pre-deployment,
  with a documented paper trail.
- **Trust earned:** consistent, framework-referenced reporting that a regulator, customer,
  or board can read.

## Pricing model (illustrative, for the business narrative)

VeriAI is positioned as per-seat + usage SaaS (audits/month tiers) with an enterprise tier
for SSO, custom compliance profiles, and org branding. Billing is **not** implemented in
this build — see the Phase 3 report's "remaining work" for the launch checklist.
