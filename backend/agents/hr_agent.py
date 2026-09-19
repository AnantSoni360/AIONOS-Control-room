"""
hr_agent.py - HR Department LangGraph Agent.

Handles: onboarding_blocker, missing_documents, access_not_provisioned
Policy : rag/documents/hr_sop.txt
"""

import uuid
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from supabase import Client

from agents.base_agent import create_agent_graph, extract_result
from rag.retriever import retrieve_policy
from tools.hr_tools import HR_TOOLS, set_db, set_run_id

HR_SYSTEM_PROMPT = """You are the AIONOS HR Agent. Your job is to investigate an onboarding blocker alert and take exactly ONE action.

## MANDATORY WORKFLOW — follow these steps in order:

STEP 1: Call get_employee(employee_id=<related_record_id from alert>)
STEP 2: Read the RECOMMENDED_ACTION field in the response. It tells you exactly what to do.
STEP 3: Execute that action NOW:
  - If RECOMMENDED_ACTION starts with "ESCALATE_CPO" → call create_approval_request(risk_level="Critical")
  - If RECOMMENDED_ACTION starts with "ESCALATE_LEGAL" → call create_approval_request(risk_level="High")
  - If RECOMMENDED_ACTION starts with "AUTO_IT" → call unblock_task() for the blocked IT task
  - If RECOMMENDED_ACTION starts with "AUTO_ESCALATE" → call escalate_onboarding()
STEP 4: Call write_audit_log() with the action you took and why.

## CRITICAL RULES:
- You MUST call create_approval_request() when RECOMMENDED_ACTION says ESCALATE. Never skip this.
- You MUST call write_audit_log() as your last action. Always.
- Do NOT explain what you are going to do without calling a tool. Just call the tools.
"""


def run_hr_agent(alert: dict, db: Client, provider: str = "mistral") -> dict:
    """Run the HR Agent on a given alert.

    Args:
        alert:    Full alert record dict.
        db:       Supabase admin client.
        provider: LLM provider to use: \"mistral\" (default) or \"groq\".
    """
    set_db(db)

    policy_context = retrieve_policy(
        query=f"{alert.get('alert_type', '')} {alert.get('description', '')}",
        department="HR",
        k=3,
    )

    run_id = str(uuid.uuid4())
    set_run_id(run_id)  # inject run_id into tools so audit_logs are linked
    # Bug #3 fixed: pass provider so the caller's selection is honoured
    graph = create_agent_graph(HR_TOOLS, HR_SYSTEM_PROMPT, policy_context, provider=provider)

    user_prompt = (
        f"You have been triggered to investigate the following HR alert:\n\n"
        f"Alert ID    : {alert['id']}\n"
        f"Alert Type  : {alert['alert_type']}\n"
        f"Severity    : {alert['severity']}\n"
        f"Title       : {alert['title']}\n"
        f"Description : {alert.get('description', 'N/A')}\n"
        f"Related Record ID   : {alert.get('related_record_id', 'N/A')} (employee_id)\n"
        f"Related Record Type : {alert.get('related_record_type', 'N/A')}\n\n"
        f"Investigate, identify the blocker type, determine the correct action per HR SOP v3.1, "
        f"and write a comprehensive audit log entry."
    )

    initial_state = {
        "messages": [HumanMessage(content=user_prompt)],
        "alert_id": alert["id"],
        "department": "HR",
        "run_id": run_id,
    }

    db.table("alerts").update({
        "status": "In_Progress",
        "agent_run_id": run_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", alert["id"]).execute()

    final_state = graph.invoke(initial_state)
    final_state["run_id"] = run_id

    # ── Post-run: finalize alert status ────────────────────────────────────────
    current = db.table("alerts").select("status").eq("id", alert["id"]).execute()
    current_status = current.data[0]["status"] if current.data else "In_Progress"
    if current_status == "In_Progress":
        now = datetime.now(timezone.utc).isoformat()
        db.table("alerts").update({
            "status": "Resolved",
            "resolved_at": now,
            "updated_at": now,
        }).eq("id", alert["id"]).execute()

    return extract_result(final_state)
