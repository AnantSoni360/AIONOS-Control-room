"""
operations_tools.py - LangChain tools for the Operations Agent.

Policy reference: rag/documents/operations_sop.txt
SLA breach severity (from SOP section 1):
  - MINOR    : 1-3 days delayed  -> auto-notify supplier
  - MODERATE : 4-7 days delayed  -> draft penalty, Procurement Manager approval
  - MAJOR    : 8-14 days delayed -> auto-penalty + COO escalation
  - CRITICAL : > 14 days OR cargo > $100k -> AGENT MUST ESCALATE, no autonomous action
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
def get_shipment(shipment_id: int) -> str:
    """
    Fetch a single shipment record along with its supplier contract details.

    Args:
        shipment_id: Primary key of the shipment.

    Returns:
        JSON with shipment fields plus contract (sla_delivery_days, penalty_per_day, max_penalty).
    """
    ship = _db.table("shipments").select("*").eq("id", shipment_id).execute().data
    if not ship:
        return json.dumps({"error": f"Shipment {shipment_id} not found."})
    ship = ship[0]

    contract = _db.table("supplier_contracts").select("*") \
                  .eq("id", ship["contract_id"]).execute().data
    ship["contract"] = contract[0] if contract else {}
    return json.dumps(ship, default=str)


@tool
def list_sla_breaches() -> str:
    """
    Return all shipments that have breached their SLA.

    Returns:
        JSON list of shipments with has_sla_breach=True ordered by days_delayed descending.
    """
    rows = _db.table("shipments").select("*") \
              .eq("has_sla_breach", True) \
              .order("days_delayed", desc=True) \
              .execute().data
    return json.dumps(rows, default=str)


@tool
def calculate_and_apply_penalty(shipment_id: int) -> str:
    """
    Calculate the SLA penalty for a delayed shipment and persist it.
    Formula per Operations SOP section 3: min(days_delayed * penalty_per_day, max_penalty).

    Args:
        shipment_id: The shipment to calculate penalty for.

    Returns:
        JSON with calculated penalty amount and SLA breach classification.
    """
    ship = _db.table("shipments").select("*").eq("id", shipment_id).execute().data
    if not ship:
        return json.dumps({"error": f"Shipment {shipment_id} not found."})
    ship = ship[0]

    contract = _db.table("supplier_contracts").select("*") \
                  .eq("id", ship["contract_id"]).execute().data
    if not contract:
        return json.dumps({"error": "Contract not found for this shipment."})
    contract = contract[0]

    days_delayed = ship.get("days_delayed", 0)
    penalty_per_day = contract.get("penalty_per_day", 500.0)
    max_penalty = contract.get("max_penalty", 10000.0)

    penalty = min(days_delayed * penalty_per_day, max_penalty)

    # Determine severity
    if days_delayed <= 3:
        severity = "MINOR"
    elif days_delayed <= 7:
        severity = "MODERATE"
    elif days_delayed <= 14:
        severity = "MAJOR"
    else:
        severity = "CRITICAL"

    # Persist the penalty
    _db.table("shipments").update({
        "calculated_penalty": penalty,
        "has_sla_breach": True,
    }).eq("id", shipment_id).execute()

    return json.dumps({
        "shipment_id": shipment_id,
        "days_delayed": days_delayed,
        "penalty_per_day": penalty_per_day,
        "max_penalty": max_penalty,
        "calculated_penalty": penalty,
        "severity": severity,
        "cargo_value": ship.get("cargo_value", 0),
        "timestamp": _now_iso(),
    })


@tool
def flag_sla_breach(shipment_id: int, breach_reason: str, alert_id: int) -> str:
    """
    Mark a shipment as SLA-breached and update the related alert.
    Use after calculate_and_apply_penalty to formally flag the breach.

    Args:
        shipment_id: The shipment to flag.
        breach_reason: Description of the breach cause.
        alert_id: Related alert to update status.

    Returns:
        Confirmation that the breach has been flagged.
    """
    _db.table("shipments").update({
        "has_sla_breach": True,
        "status": "delayed",
    }).eq("id", shipment_id).execute()

    _db.table("alerts").update({
        "status": "In_Progress",
        "updated_at": _now_iso(),
    }).eq("id", alert_id).execute()

    return json.dumps({
        "action": "sla_breach_flagged",
        "shipment_id": shipment_id,
        "breach_reason": breach_reason,
        "timestamp": _now_iso(),
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
    Create a human approval request for Operations breach decisions.
    Required for MODERATE breaches (Procurement Manager) and MAJOR/CRITICAL
    breaches (COO) per Operations SOP sections 2.2, 2.3, 2.4.

    Args:
        alert_id: The alert this approval belongs to.
        action_requested: What action needs manager/COO approval.
        risk_level: High or Critical.
        context_summary: Full incident report for the human reviewer.
        policy_reference: Relevant SOP clause.

    Returns:
        JSON with approval request details.
    """
    row = {
        "alert_id": alert_id,
        "agent_name": "OperationsAgent",
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
        "message": "Operations approval request created. COO/Manager review required.",
    })


@tool
def write_audit_log(
    alert_id: int,
    action: str,
    details: str,
    step_index: int = 0,
) -> str:
    """
    Write an audit log entry for any Operations agent action taken.
    Required by Operations SOP section 5 - all breach events must be logged.

    Args:
        alert_id: The alert being worked on.
        action: Short action name (e.g. calculated_penalty, notified_supplier, escalated_to_coo).
        details: Description of what was done and why.
        step_index: Ordering index within this agent run.

    Returns:
        Confirmation of log written.
    """
    row = {
        "alert_id": alert_id,
        "agent_name": "OperationsAgent",
        "action": action,
        "details": details,
        "step_index": step_index,
        "timestamp": _now_iso(),
        "is_human_action": False,
    }
    _db.table("audit_logs").insert(row).execute()
    return json.dumps({"logged": True, "action": action})


OPERATIONS_TOOLS = [
    get_shipment,
    list_sla_breaches,
    calculate_and_apply_penalty,
    flag_sla_breach,
    create_approval_request,
    write_audit_log,
]
