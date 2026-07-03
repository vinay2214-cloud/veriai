# Stage 1: Build Python dependencies
FROM python:3.11-slim AS builder

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final Image
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Phase 2 — runtime apt libs trimmed. The Cairo/Pango/gdk-pixbuf stack was a
# leftover from an earlier HTML/SVG-to-PDF path; PDF export now uses reportlab
# (pure Python), and no module imports cairo, pango, or gdk-pixbuf. libffi-dev
# is a build-time headers package, not a runtime dependency. Removing them
# shrinks the image and speeds the apt layer. libmagic1 is kept for MIME
# sniffing in the upload validators.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI (which also serves the frontend statics). Render provides PORT.
CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
