"""
supervisor_tools.py - Meta-tools for the AIONOS Supervisor Agent.

These tools allow the Supervisor to:
  - Query cross-department context (related alerts, entity history)
  - Delegate to any department agent as a sub-task
  - Create cross-department approval escalations
  - Write supervisor-level audit entries
"""

import uuid
from datetime import datetime, timezone
from langchain_core.tools import tool
from supabase import Client

_db: Client = None


def set_db(db: Client):
    global _db
    _db = db


# ---------------------------------------------------------------------------
# Context tools
# ---------------------------------------------------------------------------

@tool
def get_related_alerts(record_id: int, record_type: str) -> str:
    """
    Find all open alerts linked to the same business entity (e.g. same supplier,
    employee, or deal). Used to detect cross-department impact before delegating.

    Args:
        record_id:   The related_record_id of the originating alert.
        record_type: e.g. 'invoice', 'employee', 'deal', 'shipment'.

    Returns:
        JSON string listing related open alerts across all departments.
    """
    try:
        result = _db.table("alerts").select(
            "id, department, alert_type, severity, status, title"
        ).eq("related_record_id", record_id).neq("status", "Resolved").execute()

        alerts = result.data or []
        if not alerts:
            return f"No related open alerts found for {record_type} #{record_id}."

        lines = [f"Related open alerts for {record_type} #{record_id}:"]
        for a in alerts:
            lines.append(
                f"  Alert #{a['id']} [{a['department']}] {a['alert_type']} "
                f"- {a['severity']} - {a['status']} - {a['title']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error querying related alerts: {e}"


@tool
def get_alert_details(alert_id: int) -> str:
    """
    Fetch full details of any alert by ID.

    Args:
        alert_id: The alert ID to look up.
    """
    try:
        result = _db.table("alerts").select("*").eq("id", alert_id).execute()
        if not result.data:
            return f"Alert #{alert_id} not found."
        a = result.data[0]
        return (
            f"Alert #{a['id']} | {a['department']} | {a['alert_type']} | "
            f"{a['severity']} | {a['status']}\n"
            f"Title: {a['title']}\n"
            f"Description: {a.get('description', 'N/A')}\n"
            f"Related: {a.get('related_record_type', '')} #{a.get('related_record_id', '')}"
        )
    except Exception as e:
        return f"Error fetching alert: {e}"


# ---------------------------------------------------------------------------
# Delegation tools
# ---------------------------------------------------------------------------

def _delegate(dept: str, alert_id: int, parent_run_id: str) -> str:
    """Internal: run a department agent and record the task row."""
    from agents.finance_agent    import run_finance_agent
    from agents.hr_agent         import run_hr_agent
    from agents.sales_agent      import run_sales_agent
    from agents.operations_agent import run_operations_agent

    runners = {
        "Finance":    run_finance_agent,
        "HR":         run_hr_agent,
        "Sales":      run_sales_agent,
        "Operations": run_operations_agent,
    }
    runner = runners.get(dept)
    if not runner:
        return f"Unknown department: {dept}"

    # Fetch alert
    res = _db.table("alerts").select("*").eq("id", alert_id).execute()
    if not res.data:
        return f"Alert #{alert_id} not found."
    alert = res.data[0]

    # Create task row — include all required fields (parent_dept is required by schema)
    task_id_row = _db.table("agent_tasks").insert({
        "parent_run_id": parent_run_id,
        "parent_dept":   "Supervisor",
        "child_dept":    dept,
        "alert_id":      alert_id,
        "status":        "running",
        "triggered_at":  datetime.now(timezone.utc).isoformat(),
    }).execute()

    task_db_id = task_id_row.data[0]["id"] if task_id_row.data else None

    try:
        result = runner(alert, _db)
        child_run_id = result.get("run_id", "") or ""
        summary = result.get("final_message", "")[:300]

        if task_db_id:
            update_payload = {
                "status":         "done",
                "completed_at":   datetime.now(timezone.utc).isoformat(),
                "result_summary": summary,
            }
            # child_run_id is a UUID column — only set if it looks like a UUID
            if child_run_id and len(child_run_id) == 36:
                update_payload["child_run_id"] = child_run_id
            _db.table("agent_tasks").update(update_payload).eq("id", task_db_id).execute()

        short_run = child_run_id[:8] + "..." if len(child_run_id) >= 8 else child_run_id
        return (
            f"{dept}Agent completed for Alert #{alert_id}.\n"
            f"Steps: {result.get('total_steps', 0)} | Run ID: {short_run}\n"
            f"Outcome: {summary}"
        )
    except Exception as e:
        if task_db_id:
            _db.table("agent_tasks").update({
                "status":        "failed",
                "completed_at":  datetime.now(timezone.utc).isoformat(),
                "error_message": str(e)[:300],
            }).eq("id", task_db_id).execute()
        return f"{dept}Agent failed for Alert #{alert_id}: {e}"


@tool
def delegate_to_finance(alert_id: int, parent_run_id: str) -> str:
    """
    Delegate Alert investigation to the Finance Agent.

    Args:
        alert_id:      ID of the Finance alert to investigate.
        parent_run_id: The Supervisor's run_id (for delegation tree tracking).
    """
    return _delegate("Finance", alert_id, parent_run_id)


@tool
def delegate_to_hr(alert_id: int, parent_run_id: str) -> str:
    """
    Delegate Alert investigation to the HR Agent.

    Args:
        alert_id:      ID of the HR alert to investigate.
        parent_run_id: The Supervisor's run_id.
    """
    return _delegate("HR", alert_id, parent_run_id)


@tool
def delegate_to_sales(alert_id: int, parent_run_id: str) -> str:
    """
    Delegate Alert investigation to the Sales Agent.

    Args:
        alert_id:      ID of the Sales alert to investigate.
        parent_run_id: The Supervisor's run_id.
    """
    return _delegate("Sales", alert_id, parent_run_id)


@tool
def delegate_to_operations(alert_id: int, parent_run_id: str) -> str:
    """
    Delegate Alert investigation to the Operations Agent.

    Args:
        alert_id:      ID of the Operations alert to investigate.
        parent_run_id: The Supervisor's run_id.
    """
    return _delegate("Operations", alert_id, parent_run_id)


# ---------------------------------------------------------------------------
# Escalation & Audit tools
# ---------------------------------------------------------------------------

@tool
def create_cross_dept_escalation(
    alert_id: int,
    departments_involved: str,
    action_requested: str,
    context_summary: str,
    risk_level: str,
    policy_reference: str = "",
) -> str:
    """
    Create a cross-department approval request requiring executive sign-off.
    Use this when the combined impact of multiple department issues is Critical.

    Args:
        alert_id:              Primary alert ID.
        departments_involved:  Comma-separated list, e.g. "Finance, Operations".
        action_requested:      What the Supervisor recommends.
        context_summary:       Brief of all sub-agent findings.
        risk_level:            "High" or "Critical".
        policy_reference:      Relevant SOP section (optional).
    """
    try:
        _db.table("approval_requests").insert({
            "alert_id":          alert_id,
            "agent_name":        "SupervisorAgent",
            "action_requested":  action_requested,
            "context_summary":   f"[Cross-Dept: {departments_involved}]\n{context_summary}",
            "risk_level":        risk_level,
            "policy_reference":  policy_reference,
            "status":            "pending",
            "created_at":        datetime.now(timezone.utc).isoformat(),
        }).execute()
        return (
            f"Cross-department escalation created for Alert #{alert_id}.\n"
            f"Departments: {departments_involved} | Risk: {risk_level}\n"
            f"Action: {action_requested}"
        )
    except Exception as e:
        return f"Error creating escalation: {e}"


@tool
def write_supervisor_log(
    alert_id: int,
    run_id: str,
    action: str,
    details: str,
) -> str:
    """
    Write an immutable supervisor-level audit log entry.

    Args:
        alert_id: Primary alert ID being orchestrated.
        run_id:   Supervisor's run_id UUID.
        action:   Short action name, e.g. "orchestration_plan", "delegation_complete".
        details:  Detailed description of what the supervisor decided and why.
    """
    try:
        _db.table("audit_logs").insert({
            "alert_id":       alert_id,
            "agent_name":     "SupervisorAgent",
            "action":         action,
            "details":        details,
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "is_human_action": False,
            "run_id":         run_id,
        }).execute()
        return f"Supervisor audit log written: {action}"
    except Exception as e:
        return f"Error writing supervisor log: {e}"


SUPERVISOR_TOOLS = [
    get_related_alerts,
    get_alert_details,
    delegate_to_finance,
    delegate_to_hr,
    delegate_to_sales,
    delegate_to_operations,
    create_cross_dept_escalation,
    write_supervisor_log,
]
