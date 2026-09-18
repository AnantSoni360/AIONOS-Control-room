"""
approvals.py — Human-in-the-loop approvals router using Supabase REST.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from supabase import Client

from database.db import get_admin

router = APIRouter(prefix="/api/approvals", tags=["Approvals"])


class ApprovalDecision(BaseModel):
    decision: str           # "approved" | "rejected"
    reason: Optional[str] = None


@router.get("/")
def list_approvals(
    status: Optional[str] = "pending",
    db: Client = Depends(get_admin),
):
    """List approval requests."""
    q = db.table("approval_requests").select("*")
    if status:
        q = q.eq("status", status)
    result = q.order("created_at", desc=True).execute()
    return {"total": len(result.data), "approvals": result.data}


@router.get("/{approval_id}")
def get_approval(approval_id: int, db: Client = Depends(get_admin)):
    result = db.table("approval_requests").select("*").eq("id", approval_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return result.data[0]


@router.post("/{approval_id}/decision")
def submit_decision(
    approval_id: int,
    body: ApprovalDecision,
    db: Client = Depends(get_admin),
):
    """Submit human approve/reject decision."""
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

    check = db.table("approval_requests").select("*").eq("id", approval_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Approval request not found")

    req = check.data[0]
    if req["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {req['status']}")

    now = datetime.now(timezone.utc).isoformat()

    # Update approval record
    db.table("approval_requests").update({
        "status": body.decision,
        "decision_reason": body.reason,
        "decided_at": now,
    }).eq("id", approval_id).execute()

    # Update parent alert
    alert_status = "Resolved" if body.decision == "approved" else "Escalated"
    alert_update = {"status": alert_status, "updated_at": now}
    if body.decision == "approved":
        alert_update["resolved_at"] = now
    db.table("alerts").update(alert_update).eq("id", req["alert_id"]).execute()

    # Write to audit log
    db.table("audit_logs").insert({
        "alert_id": req["alert_id"],
        "agent_name": "HumanApprover",
        "action": f"human_{body.decision}",
        "details": f"Human decision: {body.decision.upper()}. Reason: {body.reason or 'No reason provided'}",
        "is_human_action": True,
        "timestamp": now,
    }).execute()

    updated = db.table("approval_requests").select("*").eq("id", approval_id).execute()
    return {
        "message": f"Decision '{body.decision}' recorded.",
        "approval": updated.data[0] if updated.data else {},
    }
