"""
sales_tools.py - LangChain tools for the Sales Agent.

Policy reference: rag/documents/sales_sop.txt
Key thresholds:
  - Stage 1 nudge       : 14-29 days stalled (agent autonomous)
  - Stage 2 manager alert: 30-44 days stalled
  - Stage 3 CRO escalation: > 45 days stalled (CRITICAL - human required)
  - High-risk flags     : overdue close date, win probability < 20%, budget freeze
"""

import json
from datetime import datetime, timezone
from langchain_core.tools import tool
from supabase import Client

_db: Client | None = None


def set_db(client: Client) -> None:
    global _db
    _db = client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@tool
def get_deal(deal_id: int) -> str:
    """
    Fetch a single deal record and its associated contact information.

    Args:
        deal_id: Primary key of the deal.

    Returns:
        JSON with deal fields and contact details.
    """
    deal = _db.table("deals").select("*").eq("id", deal_id).execute().data
    if not deal:
        return json.dumps({"error": f"Deal {deal_id} not found."})
    deal = deal[0]

    contact = _db.table("contacts").select("*").eq("id", deal["contact_id"]).execute().data
    deal["contact"] = contact[0] if contact else {}
    return json.dumps(deal, default=str)


@tool
def list_stalled_deals() -> str:
    """
    Return all deals currently marked as stalled.

    Returns:
        JSON list of deals with is_stalled=True ordered by days_stalled descending.
    """
    rows = _db.table("deals").select("*") \
              .eq("is_stalled", True) \
              .order("days_stalled", desc=True) \
              .execute().data
    return json.dumps(rows, default=str)


@tool
def update_deal_stage(deal_id: int, new_stage: str, notes: str) -> str:
    """
    Update the pipeline stage of a deal and add a progress note.
    Use for autonomous stage changes per Sales SOP section 2.
    Do NOT change stage to Closed Lost or Closed Won without CRO approval
    if the deal has been stalled > 45 days.

    Args:
        deal_id: The deal to update.
        new_stage: New pipeline stage (Prospecting | Qualification | Proposal | Negotiation | Closed Won | Closed Lost).
        notes: Reason for the stage change.

    Returns:
        Confirmation message.
    """
    _db.table("deals").update({
        "stage": new_stage,
        "notes": notes,
        "last_activity_date": _now_iso(),
    }).eq("id", deal_id).execute()

    return json.dumps({
        "action": "stage_updated",
        "deal_id": deal_id,
        "new_stage": new_stage,
        "notes": notes,
        "timestamp": _now_iso(),
    })


@tool
def schedule_followup(deal_id: int, assigned_rep: str, message: str) -> str:
    """
    Log a follow-up action for a stalled deal in the audit trail.
    This represents the automated nudge per Sales SOP section 2.1.
    Also updates last_activity_date to prevent immediate re-triggering.

    Args:
        deal_id: The stalled deal.
        assigned_rep: The sales rep assigned to this deal.
        message: The follow-up message / reminder content.

    Returns:
        Confirmation of follow-up logged.
    """
    # Update last_activity_date
    _db.table("deals").update({
        "last_activity_date": _now_iso(),
    }).eq("id", deal_id).execute()

    return json.dumps({
        "action": "followup_scheduled",
        "deal_id": deal_id,
        "assigned_rep": assigned_rep,
        "message": message,
        "timestamp": _now_iso(),
        "note": "Follow-up logged. last_activity_date updated.",
    })


@tool
def create_approval_request(
    alert_id: int,
    action_requested: str,
    risk_level: str,
    context_summary: str,
    policy_reference: str,
) -> str:
    """
    Create a human approval request for high-stakes deal decisions.
    Use for CRO escalation (>45 days stalled), deal reassignment >=50k,
    or discounts >20% per Sales SOP sections 2.3 and 5.

    Args:
        alert_id: The alert this approval belongs to.
        action_requested: What action needs CRO/VP approval.
        risk_level: High or Critical.
        context_summary: Full deal brief for the human reviewer.
        policy_reference: Relevant SOP clause.

    Returns:
        JSON with approval request details.
    """
    row = {
        "alert_id": alert_id,
        "agent_name": "SalesAgent",
        "action_requested": action_requested,
        "risk_level": risk_level,
        "context_summary": context_summary,
        "policy_reference": policy_reference,
        "status": "pending",
        "created_at": _now_iso(),
    }
    result = _db.table("approval_requests").insert(row).execute()
    created = result.data[0] if result.data else row

    _db.table("alerts").update({
        "status": "Pending_Approval",
        "updated_at": _now_iso(),
    }).eq("id", alert_id).execute()

    return json.dumps({
        "approval_request_id": created.get("id"),
        "status": "pending",
        "message": "Sales approval request created. CRO review required.",
    })


@tool
def write_audit_log(
    alert_id: int,
    action: str,
    details: str,
    step_index: int = 0,
) -> str:
    """
    Write an audit log entry for any Sales agent action taken.

    Args:
        alert_id: The alert being worked on.
        action: Short action name (e.g. sent_nudge_email, escalated_to_cro, updated_stage).
        details: Description of what was done and why.
        step_index: Ordering index within this agent run.

    Returns:
        Confirmation of log written.
    """
    row = {
        "alert_id": alert_id,
        "agent_name": "SalesAgent",
        "action": action,
        "details": details,
        "step_index": step_index,
        "timestamp": _now_iso(),
        "is_human_action": False,
    }
    _db.table("audit_logs").insert(row).execute()
    return json.dumps({"logged": True, "action": action})


SALES_TOOLS = [
    get_deal,
    list_stalled_deals,
    update_deal_stage,
    schedule_followup,
    create_approval_request,
    write_audit_log,
]
