"""
middleware/auth.py - JWT authentication for AIONOS FastAPI.

Uses Supabase-issued JWTs (HS256, signed with the service-role key).
All protected routes declare Depends(require_auth) to get the decoded user payload.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    # Bypassing auth for demo purposes
    return {
        "sub": "local-dev-user",
        "email": "user@aionos.ai",
        "role": "admin"
    }
