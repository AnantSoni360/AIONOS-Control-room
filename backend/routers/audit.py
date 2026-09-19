"""
audit.py — Immutable audit log router using Supabase REST.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from supabase import Client

from database.db import get_admin
from middleware.auth import require_auth

router = APIRouter(prefix="/api/audit", tags=["Audit"])


@router.get("/")
def list_audit_logs(
    alert_id:       Optional[int]  = Query(None),
    department:     Optional[str]  = Query(None),
    agent_name:     Optional[str]  = Query(None),
    is_human_action:Optional[bool] = Query(None),
    run_id:         Optional[str]  = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Client = Depends(get_admin),
    _user: dict = Depends(require_auth),   # Bug #5 fixed: JWT guard
):
    """List audit log entries with optional filters including run_id for trace lookup."""
    q = db.table("audit_logs").select("*")

    if alert_id:
        q = q.eq("alert_id", alert_id)
    if run_id:
        q = q.eq("run_id", run_id)
    if agent_name:
        q = q.eq("agent_name", agent_name)
    if is_human_action is not None:
        q = q.eq("is_human_action", is_human_action)
    if department:
        # Get alert IDs for this department first
        alert_ids = [
            a["id"] for a in
            db.table("alerts").select("id").eq("department", department).execute().data
        ]
        if alert_ids:
            q = q.in_("alert_id", alert_ids)
        else:
            return {"total": 0, "offset": offset, "limit": limit, "logs": []}

    result = q.order("timestamp", desc=True).range(offset, offset + limit - 1).execute()

    return {
        "total": len(result.data),
        "offset": offset,
        "limit": limit,
        "logs": result.data,
    }
