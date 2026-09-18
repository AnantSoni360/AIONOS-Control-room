# ── Stage 1: Dependencies ─────────────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app

# Install build deps for psycopg2 / pg8000
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Application ──────────────────────────────────────────────────────
FROM python:3.12-slim AS app

WORKDIR /app

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application source
COPY . .

# Expose default port (Railway overrides with $PORT)
EXPOSE 8000

# Use shell form so $PORT env var is expanded at runtime
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
