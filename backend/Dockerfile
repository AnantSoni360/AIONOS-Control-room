# ── Stage 1: Dependencies ─────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway injects $PORT at runtime - use shell form so it expands
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
