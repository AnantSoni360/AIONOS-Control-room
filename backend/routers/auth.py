"""
auth.py - AIONOS Authentication router.

POST /api/auth/login    -- exchange email+password for a Supabase JWT
POST /api/auth/refresh  -- refresh an expiring session token
POST /api/auth/logout   -- server-side logout (invalidates refresh token)
GET  /api/auth/me       -- return decoded user info from the current token
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from middleware.auth import require_auth

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login")
def login(body: LoginRequest):
    """
    Authenticate with email + password via Supabase Auth.
    Returns access_token, refresh_token, and user info.
    """
    from supabase import create_client
    from config import settings

    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    try:
        resp = client.auth.sign_in_with_password({
            "email":    body.email,
            "password": body.password,
        })
        if not resp.session:
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        return {
            "access_token":  resp.session.access_token,
            "refresh_token": resp.session.refresh_token,
            "token_type":    "bearer",
            "expires_in":    resp.session.expires_in,
            "user": {
                "id":    str(resp.user.id),
                "email": resp.user.email,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        err_str = str(e).lower()
        if "invalid" in err_str or "credentials" in err_str or "password" in err_str:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        raise HTTPException(status_code=500, detail=f"Auth error: {e}")


@router.post("/refresh")
def refresh_token(body: RefreshRequest):
    """
    Refresh an expiring Supabase session using the refresh token.
    """
    from supabase import create_client
    from config import settings

    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    try:
        resp = client.auth.refresh_session(body.refresh_token)
        if not resp.session:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
        return {
            "access_token":  resp.session.access_token,
            "refresh_token": resp.session.refresh_token,
            "token_type":    "bearer",
            "expires_in":    resp.session.expires_in,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Refresh failed: {e}")


@router.get("/me")
def get_me(user: dict = Depends(require_auth)):
    """Return the decoded user payload from the current JWT."""
    return {
        "user_id": user.get("sub"),
        "email":   user.get("email"),
        "role":    user.get("role"),
        "exp":     user.get("exp"),
    }
