"""VeriAI — FastAPI application entry point.
Registers all routers, initialises the database, seeds data, and
serves the frontend as static files.
"""
import os
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .routes import audit, feedback, dashboard, bias_scan, truth_check, correction, report, upload, ml, settings, review, llm_audit, demo, datasets
from .database import init_db
from .config import DATABASE_URL
from .sqlalchemy_db import init_sqlalchemy_models, close_engine
from .seed_data import seed_database
from .logging_config import configure_logging
from .security.startup import verify_security_config


configure_logging()


MAX_REQUEST_BYTES = 50 * 1024 * 1024
RATE_WINDOW_SECONDS = 60 * 60
UPLOAD_LIMIT_PER_HOUR = 10
API_LIMIT_PER_HOUR = 300
UPLOAD_PATHS = {
    "/api/datasets/upload",
    "/api/upload-csv",
    "/api/upload-csv-knowledge",
}
_RATE_BUCKETS = defaultdict(lambda: {"api": deque(), "upload": deque()})


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class SizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Payload too large (max 50MB)."},
                    )
            except ValueError:
                pass
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)

        now = time.time()
        ip = _client_ip(request)
        bucket = _RATE_BUCKETS[ip]

        # Prune old entries
        for key in ("api", "upload"):
            q = bucket[key]
            while q and now - q[0] > RATE_WINDOW_SECONDS:
                q.popleft()

        # API rate limit: 300/hour/IP
        if len(bucket["api"]) >= API_LIMIT_PER_HOUR:
            retry_after = max(1, int(RATE_WINDOW_SECONDS - (now - bucket["api"][0])))
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"detail": "Rate limit exceeded: max 300 API requests/hour per IP."},
            )

        is_upload = path in UPLOAD_PATHS
        if is_upload and len(bucket["upload"]) >= UPLOAD_LIMIT_PER_HOUR:
            retry_after = max(1, int(RATE_WINDOW_SECONDS - (now - bucket["upload"][0])))
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"detail": "Rate limit exceeded: max 10 uploads/hour per IP."},
            )

        bucket["api"].append(now)
        if is_upload:
            bucket["upload"].append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "object-src 'none'"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # --- Startup ---
    verify_security_config()
    await init_sqlalchemy_models()
    if not DATABASE_URL:
        await init_db()
        seed_database()
    yield
    # --- Shutdown ---
    await close_engine()


app = FastAPI(
    title="VeriAI AI Trust Auditor",
    version="1.0.0",
    description="Detect, score, explain, and correct bias and hallucinations in AI systems.",
    lifespan=lifespan,
)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# ----- API routers -----
app.include_router(audit.router, prefix="/api", tags=["Audit"])
app.include_router(bias_scan.router, prefix="/api", tags=["Bias"])
app.include_router(truth_check.router, prefix="/api", tags=["Truth"])
app.include_router(correction.router, prefix="/api", tags=["Correction"])
app.include_router(report.router, prefix="/api", tags=["Report"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(feedback.router, prefix="/api", tags=["Feedback"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(ml.router, prefix="/api", tags=["ML"])
app.include_router(settings.router, prefix="/api", tags=["Settings"])
app.include_router(review.router, prefix="/api", tags=["Review"])
app.include_router(llm_audit.router, prefix="/api", tags=["LLM Audit"])
app.include_router(demo.router, prefix="/api", tags=["Demo"])
app.include_router(datasets.router, prefix="/api", tags=["Datasets"])

#  HEALTH CHECK   (correct position)
@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}

# ----- Serve frontend -----
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
