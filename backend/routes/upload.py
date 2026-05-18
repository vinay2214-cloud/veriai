"""CSV Upload endpoint.
Accepts a CSV file, parses it, and returns JSON or passes it to the audit engine.
Also handles knowledge base article uploads for the FAISS vector store.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List
import pandas as pd
import io
import sqlite3
from ..config import DB_PATH, MAX_KB_ARTICLES, MAX_PUBLIC_UPLOAD_MB, MAX_PUBLIC_UPLOAD_ROWS, PUBLIC_UPLOAD_PREVIEW_ROWS
from ..services.truth_service import invalidate_cache
from ..services.csv_mapping_service import build_mapped_dataset
from ..security.file_validator import sanitize_dataframe, scan_for_injection, validate_upload

router = APIRouter()


class KBArticle(BaseModel):
    title: str
    content: str
    source: str = "user-uploaded"


class KBBulkUpload(BaseModel):
    articles: List[KBArticle]


PROTECTED_NAME_HINTS = (
    "gender",
    "sex",
    "race",
    "ethnicity",
    "disability",
    "veteran",
    "marital",
)


def _is_binary_like(series: pd.Series) -> bool:
    cleaned = series.astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return 0 < cleaned.dropna().nunique() <= 2


def _infer_audit_mapping(df: pd.DataFrame) -> dict:
    columns = df.columns.tolist()
    if len(columns) < 2:
        raise ValueError("CSV must have at least one feature column and one target column.")

    target_col = columns[-1]
    if not _is_binary_like(df[target_col]):
        binary_candidates = [col for col in reversed(columns) if _is_binary_like(df[col])]
        if not binary_candidates:
            raise ValueError("Could not infer a binary target column. Use a CSV with a yes/no or 0/1 target column.")
        target_col = binary_candidates[0]

    protected_col = None
    for col in columns:
        lowered = str(col).lower()
        if col == target_col:
            continue
        if any(hint in lowered for hint in PROTECTED_NAME_HINTS) and _is_binary_like(df[col]):
            protected_col = col
            break

    if protected_col is None:
        for col in columns:
            if col != target_col and _is_binary_like(df[col]):
                protected_col = col
                break

    roles = {col: "feature" for col in columns}
    roles[target_col] = "target"
    if protected_col:
        roles[protected_col] = "protected_attribute"
    return {"roles": roles}


async def _read_public_csv(file: UploadFile) -> pd.DataFrame:
    upload_meta = await validate_upload(file)
    if upload_meta.size_bytes > MAX_PUBLIC_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"CSV exceeds {MAX_PUBLIC_UPLOAD_MB}MB public demo limit.")

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content), nrows=MAX_PUBLIC_UPLOAD_ROWS + 1)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}") from exc

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    if len(df) > MAX_PUBLIC_UPLOAD_ROWS:
        df = df.iloc[:MAX_PUBLIC_UPLOAD_ROWS].copy()

    scan_for_injection(df)
    return sanitize_dataframe(df)


@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload and parse a CSV file for bias scanning.

    Public demo uploads are intentionally in-memory only. The endpoint returns
    a compact numeric dataset payload that can be pasted/run through /api/audit;
    it does not store raw uploaded files on Render.
    """
    try:
        df = await _read_public_csv(file)
        mapping = _infer_audit_mapping(df)
        dataset_json, normalized_mapping = build_mapped_dataset(df, mapping)
        target_col = normalized_mapping["target_column"]

        return {
            "status": "success",
            "filename": file.filename,
            "rows": len(df),
            "columns": df.columns.tolist(),
            "num_features": len(dataset_json["feature_names"]),
            "label_column": target_col,
            "protected_attribute": normalized_mapping.get("protected_attribute"),
            "label_distribution": {str(k): int(v) for k, v in df[target_col].value_counts().to_dict().items()},
            "preview": df.head(PUBLIC_UPLOAD_PREVIEW_ROWS).to_dict(orient="records"),
            "mapping": normalized_mapping,
            "dataset": dataset_json,
            "storage_policy": "processed_in_memory_raw_file_not_stored",
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to prepare audit dataset: {e}")


@router.post("/upload-csv-knowledge")
async def upload_csv_knowledge(file: UploadFile = File(...)):
    """Upload a CSV file to populate the FAISS knowledge base.
    CSV should have columns: title, content, source (source is optional).
    """
    try:
        df = await _read_public_csv(file)
        columns = [c.lower().strip() for c in df.columns.tolist()]
        df.columns = columns
        
        # Validate required columns
        if 'content' not in columns:
            # Try to find a content-like column
            text_cols = [c for c in columns if c in ('text', 'body', 'article', 'document', 'passage')]
            if text_cols:
                df = df.rename(columns={text_cols[0]: 'content'})
            else:
                return {"error": "CSV must have a 'content' (or 'text', 'body') column with the knowledge text."}
        
        if 'title' not in columns:
            df['title'] = [f"Article {i+1}" for i in range(len(df))]
        
        if 'source' not in columns:
            df['source'] = 'csv-upload'
        
        # Insert into knowledge base
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        inserted = 0
        
        for _, row in df.iterrows():
            title = str(row.get('title', ''))
            text = str(row.get('content', ''))
            source = str(row.get('source', 'csv-upload'))
            
            if not text or len(text.strip()) < 10:
                continue
            
            # Check for duplicates
            cursor.execute("SELECT COUNT(*) FROM knowledge_base WHERE title = ?", (title,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO knowledge_base (title, content, source) VALUES (?, ?, ?)",
                    (title, text[:2500], source[:300])
                )
                inserted += 1

        cursor.execute(
            "DELETE FROM knowledge_base WHERE id NOT IN (SELECT id FROM knowledge_base ORDER BY id DESC LIMIT ?)",
            (MAX_KB_ARTICLES,),
        )
        
        conn.commit()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM knowledge_base")
        total = cursor.fetchone()[0]
        conn.close()
        
        # Invalidate the FAISS cache so it rebuilds with new data
        invalidate_cache()
        
        return {
            "status": "success",
            "filename": file.filename,
            "articles_inserted": inserted,
            "total_articles": total,
            "skipped_duplicates": len(df) - inserted
        }
        
    except Exception as e:
        return {"error": f"Failed to parse knowledge CSV: {str(e)}"}


@router.post("/knowledge-base/add")
async def add_knowledge_article(article: KBArticle):
    """Add a single article to the FAISS knowledge base."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check duplicate
    cursor.execute("SELECT COUNT(*) FROM knowledge_base WHERE title = ?", (article.title,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return {"status": "duplicate", "message": f"Article '{article.title}' already exists."}
    
    cursor.execute(
        "INSERT INTO knowledge_base (title, content, source) VALUES (?, ?, ?)",
        (article.title, article.content[:2500], article.source[:300])
    )
    cursor.execute(
        "DELETE FROM knowledge_base WHERE id NOT IN (SELECT id FROM knowledge_base ORDER BY id DESC LIMIT ?)",
        (MAX_KB_ARTICLES,),
    )
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM knowledge_base")
    total = cursor.fetchone()[0]
    conn.close()
    
    # Invalidate FAISS cache
    invalidate_cache()
    
    return {"status": "success", "total_articles": total}


@router.post("/knowledge-base/bulk")
async def add_knowledge_bulk(data: KBBulkUpload):
    """Add multiple articles to the FAISS knowledge base."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0
    
    for article in data.articles:
        cursor.execute("SELECT COUNT(*) FROM knowledge_base WHERE title = ?", (article.title,))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO knowledge_base (title, content, source) VALUES (?, ?, ?)",
                (article.title, article.content[:2500], article.source[:300])
            )
            inserted += 1
    cursor.execute(
        "DELETE FROM knowledge_base WHERE id NOT IN (SELECT id FROM knowledge_base ORDER BY id DESC LIMIT ?)",
        (MAX_KB_ARTICLES,),
    )
    
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM knowledge_base")
    total = cursor.fetchone()[0]
    conn.close()
    
    invalidate_cache()
    
    return {"status": "success", "articles_inserted": inserted, "total_articles": total}


@router.get("/knowledge-base/stats")
async def knowledge_base_stats():
    """Get knowledge base statistics for the FAISS vector store."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM knowledge_base")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT title, source FROM knowledge_base ORDER BY id DESC LIMIT 5")
    recent = [{"title": r[0], "source": r[1]} for r in cursor.fetchall()]
    
    # Build the FAISS cache lazily so the Settings page reflects the real
    # indexed state after startup, before the first truth-check request.
    from ..services import truth_service
    index_error = None
    if total > 0 and truth_service._KB_CACHE is None:
        try:
            await truth_service._load_knowledge_base()
        except Exception as exc:
            index_error = str(exc)
    faiss_status = "connected" if truth_service._KB_CACHE is not None else ("empty" if total == 0 else "degraded")
    
    conn.close()
    
    return {
        "total_articles": total,
        "recent_articles": recent,
        "faiss_status": faiss_status,
        "index_type": "FAISS IndexFlatIP (Cosine Similarity)",
        "vectorizer": truth_service.active_vector_mode(),
        "embedding_configured": truth_service.embedding_service_configured(),
        "index_error": index_error,
    }


@router.post("/knowledge-base/rebuild")
async def rebuild_faiss_index():
    """Force rebuild the FAISS index from the current knowledge base."""
    invalidate_cache()
    
    # Trigger a rebuild by calling verify_claims with a dummy query.
    # This uses Gemini embeddings when configured and local TF-IDF otherwise.
    from ..services.truth_service import verify_claims
    try:
        await verify_claims("test rebuild query")
    except Exception as exc:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM knowledge_base")
        total = cursor.fetchone()[0]
        conn.close()
        return {
            "status": "failed",
            "total_articles": total,
            "index_dimensions": 0,
            "message": f"FAISS index rebuild failed: {exc}",
        }
    
    from ..services.truth_service import _KB_CACHE
    status = "connected" if _KB_CACHE is not None else "failed"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM knowledge_base")
    total = cursor.fetchone()[0]
    conn.close()
    
    return {
        "status": status,
        "total_articles": total,
        "index_dimensions": _KB_CACHE[0].d if _KB_CACHE and _KB_CACHE[0] else 0,
        "message": f"FAISS index rebuilt with {total} articles."
    }
