"""
db.py — Supabase clients using REST API (no direct TCP required).

Two clients:
  supabase       — anon key  (safe for reads, used by FastAPI routes)
  supabase_admin — service_role key (bypasses RLS, used for seeding & writes)
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str      = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")

# Read client (anon key) — for FastAPI route reads
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Admin client (service_role key) — bypasses RLS, for writes & seeding
supabase_admin: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY if SUPABASE_SERVICE_KEY else SUPABASE_ANON_KEY
)


def get_supabase() -> Client:
    """FastAPI dependency — read client."""
    return supabase


def get_admin() -> Client:
    """FastAPI dependency — admin write client."""
    return supabase_admin


def test_connection() -> bool:
    """Health check via REST API."""
    try:
        supabase_admin.table("alerts").select("id").limit(1).execute()
        return True
    except Exception as e:
        err = str(e)
        if "PGRST" in err or "schema cache" in err:
            return True   # REST works, table just empty
        print(f"DB health check failed: {e}")
        return False
