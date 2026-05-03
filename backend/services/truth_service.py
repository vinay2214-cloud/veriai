"""Truth verification utilities using semantic embeddings + FAISS."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple
import numpy as np
import faiss
from ..config import DB_PATH, RAG_SIMILARITY_THRESHOLD

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None

_KB_CACHE: Optional[Tuple[faiss.IndexFlatIP, List[Dict[str, str]]]] = None
_EMBEDDER = None
_EMBEDDER_LOCK = Lock()
EMBED_MODEL_NAME = os.getenv("VERIAI_EMBED_MODEL", "all-MiniLM-L6-v2")


def invalidate_cache():
    """Clear the KB cache so the next call reloads from DB."""
    global _KB_CACHE, _EMBEDDER
    _KB_CACHE = None
    # Keep the model warm by default. This env flag is useful in low-memory deploys.
    if os.getenv("VERIAI_UNLOAD_EMBEDDER", "0") == "1":
        _EMBEDDER = None


def _model_cache_dir() -> Path:
    cache_dir = Path(__file__).resolve().parent.parent / "data" / "model_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER

    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed.")

    with _EMBEDDER_LOCK:
        if _EMBEDDER is None:
            _EMBEDDER = SentenceTransformer(
                EMBED_MODEL_NAME,
                cache_folder=str(_model_cache_dir()),
                device="cpu",
            )
    return _EMBEDDER


def _encode_texts(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    model = _get_embedder()
    vectors = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    return matrix


def _load_knowledge_base():
    """Load KB rows and build a FAISS index from semantic embeddings."""
    global _KB_CACHE
    if _KB_CACHE is not None:
        return _KB_CACHE

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT title, content, source FROM knowledge_base")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()

    if not rows:
        return None, []

    records = [{"title": r[0], "content": r[1], "source": r[2]} for r in rows]
    texts = [rec["content"] for rec in records]

    matrix = _encode_texts(texts)
    index = faiss.IndexFlatIP(matrix.shape[1])  # 384-dim for MiniLM by default
    index.add(matrix)

    _KB_CACHE = (index, records)
    return _KB_CACHE


def verify_claims(claim: str, top_k: int = 3) -> Dict:
    """Verify a claim against KB using semantic nearest-neighbor retrieval."""
    try:
        result = _load_knowledge_base()
    except Exception as exc:
        return {
            "truth_score": 0.5,
            "groundedness": 0.0,
            "citations": [{
                "title": "Embedding model unavailable",
                "source": "N/A",
                "similarity": 0.0,
                "snippet": f"Failed to initialize '{EMBED_MODEL_NAME}': {exc}",
            }],
            "retrieved_context": [],
        }

    faiss_index, records = result if result and result[0] is not None else (None, [])

    if faiss_index is None or len(records) == 0:
        return {
            "truth_score": 0.5,
            "groundedness": 0.0,
            "citations": [{"title": "No knowledge base loaded", "source": "N/A",
                           "similarity": 0.0, "snippet": "Seed the knowledge base to enable RAG."}],
            "retrieved_context": [],
        }

    query_dense = _encode_texts([claim])
    D, I = faiss_index.search(query_dense, min(top_k, len(records)))

    top_sims = D[0]
    top_idxs = I[0]
    groundedness = float(np.mean(top_sims)) if len(top_sims) > 0 else 0.0
    truth_score = min(groundedness / RAG_SIMILARITY_THRESHOLD, 1.0)

    citations = []
    retrieved_context = []
    for idx, sim in zip(top_idxs, top_sims):
        if idx == -1:
            continue
        rec = records[idx]
        snippet = rec["content"][:200] + "..." if len(rec["content"]) > 200 else rec["content"]
        citation = {
            "title": rec["title"],
            "source": rec["source"],
            "similarity": round(float(sim), 4),
            "snippet": snippet,
        }
        citations.append(citation)
        retrieved_context.append({
            "title": rec["title"],
            "source": rec["source"],
            "similarity": round(float(sim), 4),
            "content": rec["content"],
        })

    return {
        "truth_score": round(truth_score, 4),
        "groundedness": round(groundedness, 4),
        "citations": citations,
        "retrieved_context": retrieved_context,
        "embedding_model": EMBED_MODEL_NAME,
    }
