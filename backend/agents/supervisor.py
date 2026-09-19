"""
supervisor.py - AIONOS Supervisor Agent (Multi-Agent Orchestrator).

The Supervisor is a meta-agent that:
  1. Assesses the full cross-department impact of a Critical alert
  2. Delegates sub-tasks to individual department agents (Finance, HR, Sales, Ops)
  3. Synthesises the results into a combined action or cross-dept escalation
  4. Records the full orchestration tree in the agent_tasks table

Supports SSE streaming via optional event_queue (same pattern as dept agents).
"""

import uuid
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from supabase import Client

from agents.base_agent import create_agent_graph, extract_result
from rag.retriever import retrieve_policy
from tools.supervisor_tools import SUPERVISOR_TOOLS, set_db

SUPERVISOR_SYSTEM_PROMPT = """You are the AIONOS Supervisor Agent. Your job is to orchestrate department agents on a Critical alert.

## MANDATORY WORKFLOW — follow these steps in order:

STEP 1: Call get_alert_details(alert_id=<alert_id from prompt>)
STEP 2: Call get_related_alerts(record_id=<related_record_id>, record_type=<related_record_type>)
STEP 3: Based on the alert department, call the matching delegation tool:
  - Finance alert → call delegate_to_finance(alert_id=<id>, parent_run_id=<Your Supervisor Run ID>)
  - HR alert → call delegate_to_hr(alert_id=<id>, parent_run_id=<Your Supervisor Run ID>)
  - Sales alert → call delegate_to_sales(alert_id=<id>, parent_run_id=<Your Supervisor Run ID>)
  - Operations alert → call delegate_to_operations(alert_id=<id>, parent_run_id=<Your Supervisor Run ID>)
  - If related alerts exist for OTHER departments, delegate to those agents too.
STEP 4: If any sub-agent outcome mentions "approval" or "Critical":
  - Call create_cross_dept_escalation(alert_id=<id>, departments_involved=<list>, action_requested=<summary>, context_summary=<findings>, risk_level="Critical")
STEP 5: ALWAYS end by calling write_supervisor_log(alert_id=<id>, run_id=<Your Supervisor Run ID>, action="orchestration_complete", details=<full summary of all delegations and outcomes>)

## CRITICAL RULES:
- The "Your Supervisor Run ID" is provided in the prompt — use it EXACTLY as the parent_run_id.
- You MUST call at least one delegate_to_X() tool. Never skip delegation.
- You MUST call write_supervisor_log() as your final action. Always.
- Do NOT explain what you are going to do without calling a tool. Just call the tools.
"""


def run_supervisor_agent(
    alert: dict,
    db: Client,
    event_queue=None,
    provider: str = "mistral",
) -> dict:
    """
    Run the Supervisor Agent on a Critical alert.

    Args:
        alert:       The triggering alert dict.
        db:          Supabase admin client.
        event_queue: Optional queue for SSE streaming events.
        provider:    LLM provider: "mistral" (default) or "groq".

    Returns:
        Agent result dict with run_id, total_steps, final_message.
    """
    set_db(db)

    run_id = str(uuid.uuid4())

    # RAG: pull cross-department policy overview
    policy_context = retrieve_policy(
        query=f"cross department escalation {alert.get('alert_type', '')} critical",
        department=alert.get("department", "Finance"),
        k=2,
    )

    graph = create_agent_graph(
        SUPERVISOR_TOOLS,
        SUPERVISOR_SYSTEM_PROMPT,
        policy_context,
        event_queue=event_queue,
        provider=provider,
    )

    user_prompt = (
        f"You are the Supervisor Agent. A Critical multi-department alert requires "
        f"your orchestration.\n\n"
        f"Primary Alert ID    : {alert['id']}\n"
        f"Department          : {alert['department']}\n"
        f"Alert Type          : {alert['alert_type']}\n"
        f"Severity            : {alert['severity']}\n"
        f"Title               : {alert['title']}\n"
        f"Description         : {alert.get('description', 'N/A')}\n"
        f"Related Record ID   : {alert.get('related_record_id', 'N/A')}\n"
        f"Related Record Type : {alert.get('related_record_type', 'N/A')}\n"
        f"Your Supervisor Run ID: {run_id}\n\n"
        f"Begin your orchestration: assess cross-department impact, delegate to the "
        f"appropriate department agents, synthesise the results, and complete with "
        f"a supervisor audit log entry."
    )

    initial_state = {
        "messages": [HumanMessage(content=user_prompt)],
        "alert_id": alert["id"],
        "department": "Supervisor",
        "run_id": run_id,
    }

    # Mark alert In_Progress
    db.table("alerts").update({
        "status":       "In_Progress",
        "agent_run_id": run_id,
        "updated_at":   datetime.now(timezone.utc).isoformat(),
    }).eq("id", alert["id"]).execute()

    final_state = graph.invoke(initial_state)
    final_state["run_id"] = run_id
    result = extract_result(final_state)
    result["supervisor_run_id"] = run_id

    # ── Post-run: finalize alert status ────────────────────────────────────────
    # Sub-department agents may have already set Pending_Approval; only mark
    # Resolved if the status is still In_Progress (all autonomous resolution).
    current = db.table("alerts").select("status").eq("id", alert["id"]).execute()
    current_status = current.data[0]["status"] if current.data else "In_Progress"
    if current_status == "In_Progress":
        now = datetime.now(timezone.utc).isoformat()
        db.table("alerts").update({
            "status":      "Resolved",
            "resolved_at": now,
            "updated_at":  now,
        }).eq("id", alert["id"]).execute()

    return result
