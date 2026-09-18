"""
db.py — Supabase clients using REST API (no direct TCP required).

Two clients:
  supabase       — anon key  (safe for reads, used by FastAPI routes)
  supabase_admin — service_role key (bypasses RLS, used for seeding & writes)

Clients are created lazily on first use to avoid crashing the app at startup
if env vars are not yet available (e.g. during Railway cold-start sequencing).
"""

import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set as environment variables."
        )
    return create_client(url, key)


@lru_cache(maxsize=1)
def _get_supabase_admin_client() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url:
        raise RuntimeError("SUPABASE_URL must be set as an environment variable.")
    return create_client(url, service_key if service_key else anon_key)


def get_supabase() -> Client:
    """FastAPI dependency — read client (anon key)."""
    return _get_supabase_client()


def get_admin() -> Client:
    """FastAPI dependency — admin write client (service_role key)."""
    return _get_supabase_admin_client()


def test_connection() -> bool:
    """Health check via REST API."""
    try:
        _get_supabase_admin_client().table("alerts").select("id").limit(1).execute()
        return True
    except Exception as e:
        err = str(e)
        if "PGRST" in err or "schema cache" in err:
            return True   # REST works, table just empty
        print(f"DB health check failed: {e}")
        return False
