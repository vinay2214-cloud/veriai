# VeriAI Deployment and Architecture Review

## Phase 1: Product Review

VeriAI already has the right core shape for an AI trust-auditing product: a dashboard, audit runner, reports, review queue, settings, bias analysis, truth verification, correction, and feedback. The biggest improvement areas are production reliability, clearer UI hierarchy, graceful vector-store behavior, and safer handling of user-provided text in the frontend.

High-value improvements:

- Keep the first screen focused on the audit workspace rather than a fake-feeling login flow.
- Make dashboard labels operational: trust score, risk score, review queue, FAISS state, and recent audits should be immediately scannable.
- Surface API failures in the UI instead of silently returning `null`.
- Escape API-provided text before injecting HTML to reduce XSS risk from audit inputs, report snippets, citations, and reviewer notes.
- Keep demo data available, but mark real deployment dependencies clearly: persistent disk, secrets, embedding key, and optional LLM key.

## Phase 2: Render Deployment

Recommended current deployment for this repository:

- Use Docker with Python 3.11 to match `runtime.txt`.
- Use Render `PORT` instead of hard-coding `8000`.
- Mount a persistent Render disk at `/var/data` on a paid web-service instance. Render's Free web services have an ephemeral filesystem and do not support persistent disks.
- Set `VERIAI_DB_PATH=/var/data/veriai.db` so audits, reports, knowledge-base rows, feedback, and review queue survive restarts.
- Keep `DEMO_MODE=true` for public demos unless you finish real auth and user management.
- Configure `JWT_SECRET`, `VERIAI_MASTER_KEY`, and `DB_ENCRYPTION_KEY` before private dataset routes are enabled.
- Configure `GEMINI_API_KEY` for higher-quality semantic retrieval; local TF-IDF fallback now keeps FAISS usable without it.

## Phase 3: Workflow Image

The workflow image is available at:

`docs/veriai-workflow.svg`

## Phase 4: Best Data and Vector Store Choices

Best practical stack by maturity:

- Demo / hackathon: SQLite on a Render persistent disk plus FAISS `IndexFlatIP`.
- Production app data: managed PostgreSQL for users, audits, reports, feedback, settings, and review workflow.
- Production vectors inside Postgres: `pgvector` with HNSW indexes when you want one database for app data and retrieval metadata.
- Production vectors at scale: Qdrant, Weaviate, Milvus, Pinecone, or Redis Vector when the knowledge corpus grows and retrieval needs dedicated scaling.
- Best FAISS setup for local accuracy: normalized dense embeddings plus `IndexFlatIP` for small corpora; `IndexHNSWFlat` for larger corpora; IVF/PQ only after recall testing shows it is acceptable.

Recommended accuracy workflow:

- Split knowledge and evaluation data into train, validation, and test sets.
- Track retrieval metrics: recall@k, MRR, nDCG, groundedness, citation correctness, and hallucination false-positive/false-negative rate.
- Compare embedding models with the same FAISS index settings before changing application logic.
- Use hard negative examples: similar but contradictory claims are essential for testing hallucination detection.
- Keep human-review decisions as labeled evaluation data, not just notes.

## Phase 5: UI/UX Direction

The app should feel like a trust operations console:

- Dense, calm, and professional.
- Fewer decorative effects, stronger information hierarchy.
- Clear failure states for APIs and vector store status.
- Consistent card radius and spacing.
- Safer text rendering for user-generated content.
- Dashboard language focused on work: run audit, inspect risk, review evidence, export report.
