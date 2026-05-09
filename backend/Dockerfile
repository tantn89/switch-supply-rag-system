# Multi-stage build for production-grade Python backend.
# Build context is the REPO ROOT (so we can COPY both backend/ and data/).
FROM python:3.11-slim AS builder

WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps for native packages (chromadb hnswlib needs g++)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --user -r requirements.txt

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# OS deps for runtime: tesseract for OCR, libgl for image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code AND data (data baked into image so prod has no volume dep)
COPY backend/app/ ./app/
COPY data/ ./data/

# Render assigns $PORT dynamically (default 10000); local dev uses 8000.
EXPOSE 8000

# Healthcheck for Docker / Render — uses the same $PORT the app binds.
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/health" || exit 1

# Use shell form so $PORT env var expands. Falls back to 8000 for local dev.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
