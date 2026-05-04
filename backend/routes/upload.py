"""CSV Upload endpoint.
Accepts a CSV file, parses it, and returns JSON or passes it to the audit engine.
Also handles knowledge base article uploads for the FAISS vector store.
"""
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import io
import sqlite3
from ..config import DB_PATH
from ..services.truth_service import invalidate_cache

router = APIRouter()


class KBArticle(BaseModel):
    title: str
    content: str
    source: str = "user-uploaded"


class KBBulkUpload(BaseModel):
    articles: List[KBArticle]


@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload and parse a CSV file for bias scanning."""
    content = await file.read()
    
    try:
        # Read the CSV 
        df = pd.read_csv(io.BytesIO(content))
        
        columns = df.columns.tolist()
        if len(columns) < 2:
            return {"error": "CSV must have at least 2 columns"}
            
        labels = df[columns[-1]].values.tolist()
        features = df[columns[:-1]].values.tolist()
        
        # Return parsed dataset structure
        dataset_json = {
            "features": features,
            "labels": labels,
            "feature_names": columns[:-1],
            "protected_index": 0
        }
        
        return {
            "status": "success",
            "filename": file.filename,
            "rows": len(df),
            "columns": columns,
            "num_features": len(columns) - 1,
            "label_column": columns[-1],
            "label_distribution": df[columns[-1]].value_counts().to_dict(),
            "preview": df.head(5).to_dict(orient="records"),
            "dataset": dataset_json
        }
        
    except Exception as e:
        return {"error": f"Failed to parse CSV: {str(e)}"}


@router.post("/upload-csv-knowledge")
async def upload_csv_knowledge(file: UploadFile = File(...)):
    """Upload a CSV file to populate the FAISS knowledge base.
    CSV should have columns: title, content, source (source is optional).
    """
    content = await file.read()
    
    try:
        df = pd.read_csv(io.BytesIO(content))
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
                    (title, text, source)
                )
                inserted += 1
        
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
        (article.title, article.content, article.source)
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
                (article.title, article.content, article.source)
            )
            inserted += 1
    
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
    if total > 0 and truth_service._KB_CACHE is None:
        await truth_service._load_knowledge_base()
    faiss_status = "connected" if truth_service._KB_CACHE is not None else "disconnected"
    
    conn.close()
    
    return {
        "total_articles": total,
        "recent_articles": recent,
        "faiss_status": faiss_status,
        "index_type": "FAISS IndexFlatIP (Cosine Similarity)",
        "vectorizer": "Gemini models/embedding-001 (768-dim)"
    }


@router.post("/knowledge-base/rebuild")
async def rebuild_faiss_index():
    """Force rebuild the FAISS index from the current knowledge base."""
    invalidate_cache()
    
    # Trigger a rebuild by calling verify_claims with a dummy query
    from ..services.truth_service import verify_claims
    result = await verify_claims("test rebuild query")
    
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
