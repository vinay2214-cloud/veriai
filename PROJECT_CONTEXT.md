# VeriAI — AI Trust Auditor Platform
## PROJECT CONTEXT for AI Coding Agent

---

## What This Project Is

VeriAI is an end-to-end AI governance and trust auditing platform.
It evaluates model outputs and datasets for fairness risk and
factual reliability BEFORE they reach end users.

It combines:
- Bias detection (demographic fairness across protected groups)
- Hallucination/truth verification (RAG-based fact checking)
- Explainability (SHAP feature attribution)
- A composite Trust Score (single 0–100 metric)
- Auto-correction (fixes bias + hallucinations automatically)
- Human review queue (human-in-the-loop for low-trust outputs)

Built for high-impact domains: hiring, healthcare, finance,
public services.

---

## Who Uses It

- Data scientists auditing their ML models before deployment
- Compliance officers checking AI outputs against regulations
- Hackathon judges evaluating the live demo (NO LOGIN REQUIRED)
- Developers integrating VeriAI into their MLOps pipeline

---

## Team

- Team: SusAI
- Leader: Janyavula Vinay
- Hackathon: PromptWars Solution Challenge 2026
- Track: Unbiased AI Decision
- Live URL: https://veriai-eyxl.onrender.com
- GitHub: https://github.com/vinay2214-cloud/veriai

---

## The Core Formula (NEVER CHANGE)

Trust Score = 0.4 × Truth + 0.4 × (1 − Bias) + 0.2 × Confidence

- Truth ∈ [0,1]: RAG triad score (Context Relevance + Groundedness + Answer Relevance)
- Bias ∈ [0,1]: AIF360 Demographic Parity Difference (0 = fair, 1 = max bias)
- Confidence ∈ [0,1]: Calibrated model confidence

Industry weight presets (configurable, no code change):
- Healthcare:  Truth=0.45, Bias=0.35, Confidence=0.20
- HR/Hiring:   Truth=0.35, Bias=0.45, Confidence=0.20
- Finance:     Truth=0.38, Bias=0.42, Confidence=0.20
- General:     Truth=0.40, Bias=0.40, Confidence=0.20

Score thresholds:
- 90–100 → Trusted (pass through)
- 70–89  → Acceptable (pass with note)
- 50–69  → Marginal (AUTO-CORRECT triggered)
- 0–49   → Blocked (HUMAN REVIEW required)

---

## The Demo Numbers (NEVER CHANGE THESE)

These appear everywhere — slides, form, demo script. All must match.

BEFORE auto-correction:
  Trust Score: 51/100
  Bias (DPD):  38% — women 38% less likely shortlisted
  Truth Score: 62% — 3 hallucinated legal citations
  Top feature: zip_code (correlation 0.73 with protected attr)
  Reg flag:    ECOA §1691 violation

AFTER auto-correction (1 click):
  Trust Score: 89/100
  Bias (DPD):  4.2%
  Truth Score: 94%
  Changes:     3 (all logged with reason + regulation)

---

## The 8-Step Pipeline

Steps 1–4 run CONCURRENTLY (asyncio.gather) → ~60% faster
Steps 5–8 run SEQUENTIALLY (each depends on prior)

1. Bias Detection     → AIF360 + SHAP
2. Truth Verification → FAISS + TF-IDF + Gemini 1.5 Pro RAG
3. Cluster Analysis   → KMeans (fairness per subpopulation)
4. Distribution Check → SciPy (data drift, label imbalance)
5. Trust Scoring      → Weighted composite formula above
6. Auto-Correction    → Rule-based + AIF360 Reweighing
7. SHAP Explainability→ Coefficient method (0ms), cached
8. Human Review Queue → Auto-queued if score < 60

---

## Critical Rules for the Agent

1. NEVER change the Trust Score formula weights
2. NEVER change the demo numbers (51→89, 38%→4.2%, 62%→94%)
3. NEVER add auth/login gates to dashboard, audit, reports, review pages
   — these MUST stay public for jury access during hackathon
4. Auth is ONLY required for: /api/datasets/upload and manage endpoints
5. The pipeline step order is fixed. Steps 1–4 parallel, 5–8 sequential
6. Auto-correct threshold = 70. Human review threshold = 60. Not the same.
7. Always use bytearray (not bytes) for sensitive data so it can be wiped
8. All security code goes in backend/security/ — do not scatter it
9. The frontend uses Vanilla JS only — no React, no Vue, no bundler
10. Dark glassmorphism theme must be preserved in all UI changes

---

## What "Good Code" Means for This Project

- FastAPI async patterns (async def, await, Depends())
- aiosqlite for all database operations
- asyncio.gather() for parallel pipeline steps
- Pydantic models for all API request/response schemas
- Type hints on every function signature
- No print() in production — use logging module
- Environment variables for ALL secrets — never hardcode
- Tests in tests/ directory — write a test for every security function