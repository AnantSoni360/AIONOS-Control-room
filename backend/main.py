"""
main.py -- AIONOS Agentic AI Factory -- FastAPI Application Entry Point

Phase 5: Production hardening
  - Pydantic Settings config validation on startup
  - SlowAPI rate limiting middleware
  - Auth router (/api/auth/login, /api/auth/refresh, /api/auth/me)
  - All agent/supervisor routes protected via require_auth dependency
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

load_dotenv()

from config import settings               # validate env vars on import
from database.db import test_connection
from middleware.rate_limit import limiter
from routers import alerts, audit, approvals, agents, stream, supervisor, limits
from routers import auth as auth_router

app = FastAPI(
    title="AIONOS Agentic AI Factory",
    description=(
        "Multi-department agentic AI system for autonomous resolution of "
        "operational exceptions -- Finance, HR, Sales & Alliances, Operations."
    ),
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:80", "http://127.0.0.1:3000", "http://127.0.0.1:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)   # public (login/refresh)
app.include_router(alerts.router)
app.include_router(audit.router)
app.include_router(approvals.router)
app.include_router(agents.router)
app.include_router(stream.router)
app.include_router(supervisor.router)
app.include_router(limits.router)

# ── Frontend static files ─────────────────────────────────────────────────────
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/ui", StaticFiles(directory=_frontend_dir, html=True), name="frontend")

# ── Health (public) ───────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "service": "AIONOS Agentic AI Factory",
        "version": "5.0.0",
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    db_ok = test_connection()
    return {
        "status":      "healthy" if db_ok else "degraded",
        "database":    "connected" if db_ok else "unreachable",
        "departments": ["Finance", "HR", "Sales", "Operations"],
        "features":    ["auth", "rate_limiting", "agent_timeout", "sse_streaming", "supervisor"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
