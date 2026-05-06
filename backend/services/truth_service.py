"""Truth verification utilities using semantic embeddings + FAISS."""
from __future__ import annotations

import asyncio
import os
import sqlite3
from threading import Lock
from typing import Dict, List, Optional, Tuple
import numpy as np
import faiss
from fastapi import HTTPException, status
from sklearn.feature_extraction.text import TfidfVectorizer
from ..config import DB_PATH, RAG_SIMILARITY_THRESHOLD

try:
    from google import genai
except Exception:  # pragma: no cover
    genai = None

_KB_CACHE: Optional[Tuple[faiss.IndexFlatIP, List[Dict[str, str]], Optional[TfidfVectorizer], str]] = None
_GEMINI_LOCK = Lock()
_GEMINI_CLIENT = None
_GEMINI_CLIENT_INITIALIZED = False
EMBED_MODEL_NAME = os.getenv("VERIAI_EMBED_MODEL", "models/embedding-001")
EMBED_DIMENSION = 768
TFIDF_MAX_FEATURES = int(os.getenv("VERIAI_TFIDF_MAX_FEATURES", "4096"))
TFIDF_SIMILARITY_THRESHOLD = float(os.getenv("VERIAI_TFIDF_THRESHOLD", "0.18"))


def invalidate_cache():
    """Clear the KB cache so the next call reloads from DB."""
    global _KB_CACHE
    _KB_CACHE = None


def _gemini_api_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def embedding_service_configured() -> bool:
    """Return whether semantic embedding credentials are configured."""
    return bool(_gemini_api_key()) and genai is not None


def active_vector_mode() -> str:
    if _KB_CACHE is not None:
        return _KB_CACHE[3]
    if embedding_service_configured():
        return f"gemini:{EMBED_MODEL_NAME}"
    return "local_tfidf"


def _get_gemini_client():
    global _GEMINI_CLIENT_INITIALIZED, _GEMINI_CLIENT
    if _GEMINI_CLIENT_INITIALIZED:
        return _GEMINI_CLIENT
    with _GEMINI_LOCK:
        if _GEMINI_CLIENT_INITIALIZED:
            return _GEMINI_CLIENT
        api_key = _gemini_api_key()
        if genai is None:
            print("WARNING: google-genai is not installed. Truth-check endpoints will return 503.")
            _GEMINI_CLIENT = None
        elif not api_key:
            print("WARNING: GEMINI_API_KEY is not configured. Truth-check endpoints will return 503.")
            _GEMINI_CLIENT = None
        else:
            _GEMINI_CLIENT = genai.Client(api_key=api_key)
        _GEMINI_CLIENT_INITIALIZED = True
        return _GEMINI_CLIENT


def _extract_embedding_values(response) -> List[float] | None:
    embeddings = getattr(response, "embeddings", None)
    if embeddings:
        first = embeddings[0]
        values = getattr(first, "values", None)
        if values is not None:
            return values
    embedding = getattr(response, "embedding", None)
    if embedding is not None:
        values = getattr(embedding, "values", None)
        if values is not None:
            return values
    return None


async def get_gemini_embedding(text: str) -> np.ndarray:
    client = _get_gemini_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API Key not configured",
        )

    payload = text.strip()
    if not payload:
        return np.zeros((EMBED_DIMENSION,), dtype=np.float32)

    def _embed_call() -> np.ndarray:
        response = client.models.embed_content(
            model=EMBED_MODEL_NAME,
            contents=[payload],
        )
        values = _extract_embedding_values(response)
        if values is None:
            raise RuntimeError(f"Gemini embedding response missing embedding vector for model '{EMBED_MODEL_NAME}'.")

        vector = np.asarray(values, dtype=np.float32)
        if vector.ndim != 1:
            raise RuntimeError("Gemini embedding response is not a 1D vector.")
        if vector.shape[0] != EMBED_DIMENSION:
            raise RuntimeError(
                f"Unexpected embedding dimension {vector.shape[0]} from '{EMBED_MODEL_NAME}'. "
                f"Expected {EMBED_DIMENSION}."
            )
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector

    return await asyncio.to_thread(_embed_call)


async def _encode_texts(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, EMBED_DIMENSION), dtype=np.float32)

    vectors = []
    for text in texts:
        vectors.append(await get_gemini_embedding(text))
    return np.vstack(vectors).astype(np.float32)


def _normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


def _build_tfidf_index(texts: List[str]) -> Tuple[faiss.IndexFlatIP, TfidfVectorizer]:
    """Build a local FAISS index when external embedding credentials are absent."""
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=TFIDF_MAX_FEATURES,
    )
    sparse = vectorizer.fit_transform(texts)
    matrix = sparse.astype(np.float32).toarray()
    if matrix.shape[1] == 0:
        matrix = np.zeros((len(texts), 1), dtype=np.float32)
    matrix = _normalize_matrix(matrix)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    return index, vectorizer


async def _load_knowledge_base():
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

    if embedding_service_configured():
        matrix = await _encode_texts(texts)
        index = faiss.IndexFlatIP(EMBED_DIMENSION)
        index.add(matrix)
        _KB_CACHE = (index, records, None, f"gemini:{EMBED_MODEL_NAME}")
    else:
        index, vectorizer = _build_tfidf_index(texts)
        _KB_CACHE = (index, records, vectorizer, "local_tfidf")
    return _KB_CACHE


async def verify_claims(claim: str, top_k: int = 3) -> Dict:
    """Verify a claim against KB using semantic nearest-neighbor retrieval."""
    try:
        result = await _load_knowledge_base()
    except HTTPException:
        raise
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

    if result and result[0] is not None:
        faiss_index, records, vectorizer, vector_mode = result
    else:
        faiss_index, records, vectorizer, vector_mode = None, [], None, active_vector_mode()

    if faiss_index is None or len(records) == 0:
        return {
            "truth_score": 0.5,
            "groundedness": 0.0,
            "citations": [{"title": "No knowledge base loaded", "source": "N/A",
                           "similarity": 0.0, "snippet": "Seed the knowledge base to enable RAG."}],
            "retrieved_context": [],
        }

    if vectorizer is None:
        query_dense = await _encode_texts([claim])
        threshold = RAG_SIMILARITY_THRESHOLD
    else:
        query_dense = vectorizer.transform([claim]).astype(np.float32).toarray()
        if query_dense.shape[1] == 0:
            query_dense = np.zeros((1, faiss_index.d), dtype=np.float32)
        query_dense = _normalize_matrix(query_dense)
        threshold = TFIDF_SIMILARITY_THRESHOLD
    D, I = faiss_index.search(query_dense, min(top_k, len(records)))

    top_sims = D[0]
    top_idxs = I[0]
    groundedness = float(np.mean(top_sims)) if len(top_sims) > 0 else 0.0
    truth_score = min(groundedness / threshold, 1.0)

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
        "embedding_model": vector_mode,
    }
