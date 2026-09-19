"""
hr_tools.py - LangChain tools for the HR Agent.

Policy reference: rag/documents/hr_sop.txt
Key thresholds:
  - IT blockers  : resolve within 4h (laptop) / 8h (VPN) / 2h (system access)
  - Legal blockers: follow-up by Day 1 (NDA), Day 2 (IP agreement)
  - CPO escalation: blocked > 5 business days, C-suite hire, safety concern
"""

import json
from datetime import datetime, timezone
from langchain_core.tools import tool
from supabase import Client

_db: Client | None = None
_run_id: str | None = None  # current run's ID, set by agent runner


def set_run_id(run_id: str) -> None:
    """Called by the agent runner to inject the current run_id before tool use."""
    global _run_id
    _run_id = run_id


def set_db(client: Client) -> None:
    global _db
    _db = client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@tool
def get_employee(employee_id: int) -> str:
    """
    Fetch a single employee record and all their onboarding tasks.
    Pre-classifies the blocker type and recommends the correct SOP action.

    Args:
        employee_id: Primary key of the employee.

    Returns:
        JSON with employee fields, onboarding_tasks, and RECOMMENDED_ACTION field.
    """
    emp = _db.table("employees").select("*").eq("id", employee_id).execute().data
    if not emp:
        return json.dumps({"error": f"Employee {employee_id} not found."})
    emp = emp[0]

    tasks = _db.table("onboarding_tasks").select("*").eq("employee_id", employee_id) \
               .order("due_date").execute().data
    emp["onboarding_tasks"] = tasks

    # Pre-classify blocker type and determine action tier
    blocked_tasks = [t for t in tasks if t.get("status") == "blocked"]
    categories = {t.get("category", "").lower() for t in blocked_tasks}

    start_date_str = emp.get("start_date", "")
    role = (emp.get("role") or "").lower()
    is_cxo = any(x in role for x in ["vp", "cxo", "cto", "cfo", "coo", "cpo", "director", "c-suite"])

    if is_cxo or len(blocked_tasks) >= 3:
        emp["RECOMMENDED_ACTION"] = "ESCALATE_CPO: Call create_approval_request(risk_level='Critical') — C-suite hire or multiple blockers"
    elif "legal" in categories or "background" in categories:
        emp["RECOMMENDED_ACTION"] = "ESCALATE_LEGAL: Call create_approval_request(risk_level='High') — Legal/background check blocker"
    elif "it" in categories or "access" in categories:
        emp["RECOMMENDED_ACTION"] = "AUTO_IT: Call unblock_task() to raise IT ticket — IT provisioning blocker, autonomous action allowed"
    elif blocked_tasks:
        emp["RECOMMENDED_ACTION"] = "AUTO_ESCALATE: Call escalate_onboarding() to notify manager — general onboarding blocker"
    else:
        emp["RECOMMENDED_ACTION"] = "MONITOR: No blocked tasks found"

    emp["computed_blocked_task_count"] = len(blocked_tasks)
    emp["computed_blocker_categories"] = list(categories)

    return json.dumps(emp, default=str)


@tool
def list_blocked_onboarding() -> str:
    """
    Return all employees who have at least one blocked onboarding task.

    Returns:
        JSON list of employees with onboarding_status not completed
        and at least one task in status=blocked.
    """
    # Get all blocked tasks
    blocked_tasks = _db.table("onboarding_tasks").select("*") \
                       .eq("status", "blocked").execute().data

    if not blocked_tasks:
        return json.dumps([])

    emp_ids = list({t["employee_id"] for t in blocked_tasks})
    employees = _db.table("employees").select("*").in_("id", emp_ids).execute().data

    # Attach tasks to each employee
    result = []
    for emp in employees:
        emp["blocked_tasks"] = [t for t in blocked_tasks if t["employee_id"] == emp["id"]]
        result.append(emp)

    return json.dumps(result, default=str)


@tool
def unblock_task(task_id: int, resolution: str) -> str:
    """
    Mark an onboarding task as resolved (status=completed).
    Use after the agent has taken action to resolve the blocker.

    Args:
        task_id: Primary key of the onboarding task.
        resolution: What was done to resolve the blocker.

    Returns:
        Confirmation message.
    """
    _db.table("onboarding_tasks").update({
        "status": "completed",
        "blocker_reason": None,
    }).eq("id", task_id).execute()

    return json.dumps({
        "action": "task_unblocked",
        "task_id": task_id,
        "resolution": resolution,
        "timestamp": _now_iso(),
    })


@tool
def escalate_onboarding(employee_id: int, reason: str, alert_id: int) -> str:
    """
    Escalate an onboarding blocker to CPO level.
    Use when employee has been blocked for more than 5 business days,
    or when the hire is C-suite / VP level, per HR SOP section 3.

    Args:
        employee_id: The employee being onboarded.
        reason: Specific reason for CPO escalation.
        alert_id: The alert to update status on.

    Returns:
        Confirmation message.
    """
    # Update employee onboarding status
    _db.table("employees").update({
        "onboarding_status": "blocked",
    }).eq("id", employee_id).execute()

    # Update alert to Escalated
    _db.table("alerts").update({
        "status": "Escalated",
        "updated_at": _now_iso(),
    }).eq("id", alert_id).execute()

    return json.dumps({
        "action": "escalated_to_cpo",
        "employee_id": employee_id,
        "reason": reason,
        "timestamp": _now_iso(),
        "next_step": "CPO notified. Manual review required within 4 business hours.",
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
    Create a human-in-the-loop approval request for HR onboarding decisions.
    Use for C-suite hires, background check issues, or blocked > 5 days per HR SOP section 3.

    Args:
        alert_id: The alert this approval belongs to.
        action_requested: What action needs human approval.
        risk_level: High or Critical.
        context_summary: Summary of the onboarding situation.
        policy_reference: Relevant SOP clause.

    Returns:
        JSON with approval request details.
    """
    row = {
        "alert_id": alert_id,
        "agent_name": "HRAgent",
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
        "message": "HR approval request created. CPO review required.",
    })


@tool
def write_audit_log(
    alert_id: int,
    action: str,
    details: str,
    step_index: int = 0,
) -> str:
    """
    Write an audit log entry for any HR agent action taken.
    Required by HR SOP section 4 - all actions must be logged in HRIS audit trail.

    Args:
        alert_id: The alert being worked on.
        action: Short action name (e.g. notified_it_helpdesk, sent_docusign, escalated_to_cpo).
        details: Human-readable description of what was done.
        step_index: Ordering index within this agent run.

    Returns:
        Confirmation of log written.
    """
    row = {
        "alert_id": alert_id,
        "agent_name": "HRAgent",
        "action": action,
        "details": details,
        "step_index": step_index,
        "timestamp": _now_iso(),
        "is_human_action": False,
        "run_id": _run_id,  # link log entries to the run for Observatory traces
    }
    _db.table("audit_logs").insert(row).execute()
    return json.dumps({"logged": True, "action": action})


HR_TOOLS = [
    get_employee,
    list_blocked_onboarding,
    unblock_task,
    escalate_onboarding,
    create_approval_request,
    write_audit_log,
]
