# ── AIONOS Backend ────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (note: .env is gitignored, use Railway env vars)
COPY . .

# Default port fallback — Railway overrides this with its own $PORT
ENV PORT=8000

EXPOSE $PORT

# Health check so Railway knows when the app is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Use ${PORT:-8000} so the container never gets an empty --port argument
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
