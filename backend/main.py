"""VeriAI — FastAPI application entry point.
Registers all routers, initialises the database, seeds data, and
serves the frontend as static files.
"""
import warnings
import os
# Silence sklearn's InconsistentVersionWarning by message so we don't import
# sklearn at process startup just to reference the warning class.
warnings.filterwarnings("ignore", message=".*InconsistentVersionWarning.*")
warnings.filterwarnings("ignore", message=".*Trying to unpickle estimator.*")

import time
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from collections import defaultdict, deque

try:  # POSIX-only; present on Render (Linux) and macOS. Guarded for portability.
    import resource as _resource
except Exception:  # pragma: no cover
    _resource = None
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .routes import audit, feedback, dashboard, bias_scan, truth_check, correction, report, upload, ml, settings, review, llm_audit, datasets, demo_routes, intelligence
from .database import init_db
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
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        # Chart.js is now self-hosted (frontend/vendor/), so script-src is tightened to
        # 'self' — no external script CDN, which removes a runtime dependency + failure
        # point and hardens the CSP. Fonts remain from Google Fonts (styles/fonts only).
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "object-src 'none'"
        )
        return response


_access_logger = logging.getLogger("veriai.access")


def _rss_mb():
    """Resident set size in MB. Linux (Render) reports ru_maxrss in KB; macOS in bytes."""
    if _resource is None:
        return None
    raw = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return round(raw / divisor, 1)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Production observability — one structured log line per API request with
    duration and process RSS. Static-file and health requests are skipped to keep
    the log signal clean. Adds only a perf_counter + getrusage on API paths."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _access_logger.info(
                "request",
                extra={
                    "event": "request",
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "duration_ms": duration_ms,
                    "rss_mb": _rss_mb(),
                },
            )


def _warm_ml_stack() -> None:
    """Prime the lazily-imported ML stack (sklearn/scipy/faiss) on a tiny in-memory
    dataset so the FIRST real audit doesn't pay the one-time import cost. Runs in a
    thread, off the event loop and AFTER startup, so /health and cold-start memory are
    unaffected. Fully guarded — any failure is logged and ignored."""
    try:
        import numpy as np
        from .services.bias_service import compute_bias_score
        from .services.cluster_service import cluster_bias_analysis
        from .services.distribution_service import compute_distribution_report

        X = np.array([[1.0, 0.2], [0.0, 0.9], [1.0, 0.4], [0.0, 0.7]])
        y = np.array([1, 0, 1, 0])
        compute_bias_score(X, y, 0, ["protected", "score"])   # primes sklearn
        cluster_bias_analysis(X, y, 0, 2)                       # primes KMeans
        compute_distribution_report(y)                          # primes scipy
        logging.getLogger("veriai.warmup").info(
            "ml_warmup_complete", extra={"event": "ml_warmup_complete"}
        )
    except Exception as exc:  # pragma: no cover
        logging.getLogger("veriai.warmup").warning("ML warm-up skipped: %s", exc)


async def _background_initialization(app: FastAPI) -> None:
    """Run database connection, migration, seeding, model loading and embedding priming
    in the background off the event loop/startup sequence.
    This lets uvicorn bind immediately to the port and respond to health checks.
    """
    logger = logging.getLogger("veriai.startup")
    logger.info("Starting server...")
    
    # 1. Database Connection & Migration
    logger.info("Connecting database...")
    try:
        await init_sqlalchemy_models()
        await init_db()
        seed_database()
    except Exception as exc:
        logger.exception("Database initialization failed: %s", exc)
        return

    # 2. Loading AI Models
    logger.info("Loading AI models...")
    import sys
    if os.getenv("VERIAI_DISABLE_WARMUP", "").strip() not in ("1", "true", "True") and "pytest" not in sys.modules:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _warm_ml_stack)
        except Exception as exc:
            logger.warning("ML stack warm-up skipped: %s", exc)

    # 3. Loading Embeddings
    logger.info("Loading embeddings...")
    if "pytest" not in sys.modules:
        try:
            from .services import truth_service
            await truth_service._load_knowledge_base()
        except Exception as exc:
            logger.warning("Embeddings priming skipped: %s", exc)

    # 4. Ready
    app.state.initialized = True
    logger.info("Application ready.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # --- Startup ---
    verify_security_config()
    app.state.initialized = False

    # Schedule the entire database initialization, seeding, and model priming
    # to run concurrently/asynchronously, allowing uvicorn to bind immediately.
    app.state.init_task = asyncio.create_task(_background_initialization(app))

    yield
    # --- Shutdown ---
    task = getattr(app.state, "init_task", None)
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await close_engine()


app = FastAPI(
    title="VeriAI AI Trust Auditor",
    version="1.0.0",
    description="Detect, score, explain, and correct bias and hallucinations in AI systems.",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.add_middleware(SizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
# Added last → outermost, so it measures the full in-process request duration.
app.add_middleware(RequestTimingMiddleware)

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
app.include_router(demo_routes.router, tags=["Demo"])
app.include_router(datasets.router, prefix="/api", tags=["Datasets"])
# Phase 3 — additive AI intelligence layer (orchestrator / compliance officer /
# review manager / executive insights). New paths only; no existing route changed.
app.include_router(intelligence.router, prefix="/api", tags=["AI Intelligence"])

# ----- Health Check endpoints -----
@app.get("/health", include_in_schema=False)
@app.get("/liveness", include_in_schema=False)
def health_check():
    """Liveness probe: reports server process availability immediately."""
    return {"status": "ok"}


@app.get("/readiness", include_in_schema=False)
def readiness_check(request: Request, response: Response):
    """Readiness probe: reports when background initialization has completed."""
    if getattr(request.app.state, "initialized", False):
        return {"status": "ready"}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "initializing"}

# ----- Serve frontend -----
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
