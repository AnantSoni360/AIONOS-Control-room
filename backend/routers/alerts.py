"""
alerts.py — Alert queue router using Supabase REST client.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone
from supabase import Client

from database.db import get_supabase, get_admin
from middleware.auth import require_auth

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("/")
def list_alerts(
    department: Optional[str] = Query(None),
    severity:   Optional[str] = Query(None),
    status:     Optional[str] = Query(None),
    limit: int  = Query(50, le=200),
    offset: int = Query(0),
    db: Client  = Depends(get_admin),
    _user: dict = Depends(require_auth),   # Bug #5 fixed: JWT guard
):
    """Paginated alert list with optional filters."""
    q = db.table("alerts").select("*")
    if department:
        q = q.eq("department", department)
    if severity:
        q = q.eq("severity", severity)
    if status:
        q = q.eq("status", status)

    result = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    # Get total count
    count_q = db.table("alerts").select("id", count="exact")
    if department:
        count_q = count_q.eq("department", department)
    if severity:
        count_q = count_q.eq("severity", severity)
    if status:
        count_q = count_q.eq("status", status)
    count_result = count_q.execute()

    return {
        "total": count_result.count,
        "offset": offset,
        "limit": limit,
        "alerts": result.data,
    }


@router.get("/summary")
def alerts_summary(
    db: Client = Depends(get_admin),
    _user: dict = Depends(require_auth),   # Bug #5 fixed: JWT guard
):
    """KPI counts per department and overall."""
    departments = ["Finance", "HR", "Sales", "Operations"]
    statuses    = ["Open", "In_Progress", "Resolved", "Escalated", "Pending_Approval"]

    all_alerts = db.table("alerts").select("department,severity,status").execute().data

    def count(items, **filters):
        return sum(1 for a in items if all(a.get(k) == v for k, v in filters.items()))

    summary = {}
    for dept in departments:
        dept_alerts = [a for a in all_alerts if a["department"] == dept]
        summary[dept] = {
            "total":    len(dept_alerts),
            "open":     count(dept_alerts, status="Open"),
            "resolved": count(dept_alerts, status="Resolved"),
            "critical": count(dept_alerts, severity="Critical"),
            "high":     count(dept_alerts, severity="High"),
        }

    summary["overall"] = {
        "total":           len(all_alerts),
        "open":            count(all_alerts, status="Open"),
        "in_progress":     count(all_alerts, status="In_Progress"),
        "resolved":        count(all_alerts, status="Resolved"),
        "escalated":       count(all_alerts, status="Escalated"),
        "pending_approval":count(all_alerts, status="Pending_Approval"),
        "critical":        count(all_alerts, severity="Critical"),
    }

    return summary


@router.get("/{alert_id}")
def get_alert(
    alert_id: int,
    db: Client = Depends(get_admin),
    _user: dict = Depends(require_auth),   # Bug #5 fixed: JWT guard
):
    """Single alert with its audit trail."""
    result = db.table("alerts").select("*").eq("id", alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert = result.data[0]
    logs = db.table("audit_logs").select("*").eq("alert_id", alert_id).order("timestamp").execute().data

    return {**alert, "audit_trail": logs}


@router.patch("/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    status: str,
    db: Client = Depends(get_admin),
    _user: dict = Depends(require_auth),   # Bug #5 fixed: JWT guard
):
    """Manually update alert status."""
    valid = ["Open", "In_Progress", "Resolved", "Escalated", "Pending_Approval"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid}")

    check = db.table("alerts").select("id").eq("id", alert_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    update_payload = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if status == "Resolved":
        update_payload["resolved_at"] = datetime.now(timezone.utc).isoformat()

    result = db.table("alerts").update(update_payload).eq("id", alert_id).execute()
    return result.data[0] if result.data else {"id": alert_id, "status": status}
