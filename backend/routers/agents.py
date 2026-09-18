"""
agents.py — Agent execution router.

POST /api/agents/run   — triggers the department-specific LangGraph agent
GET  /api/agents/trace/{run_id} — retrieve audit logs for a completed run
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from database.db import get_admin
from agents import run_agent

router = APIRouter(prefix="/api/agents", tags=["Agents"])


class AgentRunRequest(BaseModel):
    alert_id: int


@router.post("/run")
def trigger_agent(body: AgentRunRequest, db: Client = Depends(get_admin)):
    """
    Trigger the appropriate department LangGraph agent on an alert.

    The agent will:
    1. Set alert status to In_Progress
    2. Reason over the alert using department-specific tools
    3. Execute autonomous actions (approve, reject, unblock, flag) or escalate
    4. Write immutable audit log entries for every action
    5. Return the full agent trace with all steps taken
    """
    # Fetch the alert
    result = db.table("alerts").select("*").eq("id", body.alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert = result.data[0]

    # Guard: don't re-run already resolved/escalated alerts
    if alert["status"] in ("Resolved", "Escalated"):
        raise HTTPException(
            status_code=400,
            detail=f"Alert is already '{alert['status']}'. Cannot re-run agent.",
        )

    try:
        agent_result = run_agent(alert, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # Log the failure to audit trail
        db.table("audit_logs").insert({
            "alert_id": body.alert_id,
            "agent_name": f"{alert.get('department', 'Unknown')}Agent",
            "action": "agent_error",
            "details": f"Agent execution failed: {exc}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_human_action": False,
        }).execute()
        raise HTTPException(status_code=500, detail=f"Agent execution error: {exc}")

    return {
        "message": "Agent run completed.",
        "alert_id": body.alert_id,
        "department": alert["department"],
        "alert_type": alert["alert_type"],
        **agent_result,
    }


@router.get("/trace/{run_id}")
def get_trace(run_id: str, db: Client = Depends(get_admin)):
    """
    Retrieve all audit log entries for a specific agent run.

    Args:
        run_id: UUID returned by POST /api/agents/run
    """
    logs = db.table("audit_logs").select("*") \
             .eq("run_id", run_id) \
             .order("timestamp") \
             .execute().data

    return {
        "run_id": run_id,
        "total_steps": len(logs),
        "steps": logs,
    }
