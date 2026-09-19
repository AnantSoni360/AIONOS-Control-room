"""
operations_agent.py - Operations Department LangGraph Agent.

Handles: sla_breach, shipment_delay, supplier_performance
Policy : rag/documents/operations_sop.txt
"""

import uuid
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from supabase import Client

from agents.base_agent import create_agent_graph, extract_result
from rag.retriever import retrieve_policy
from tools.operations_tools import OPERATIONS_TOOLS, set_db, set_run_id

OPERATIONS_SYSTEM_PROMPT = """You are the AIONOS Operations Agent. Your job is to investigate an SLA breach alert and take exactly ONE action.

## MANDATORY WORKFLOW — follow these steps in order:

STEP 1: Call get_shipment(shipment_id=<related_record_id from alert>)
STEP 2: Read the RECOMMENDED_ACTION field in the response. It tells you exactly what to do.
STEP 3: Execute that action NOW:
  - If RECOMMENDED_ACTION starts with "ESCALATE_COO" → call calculate_and_apply_penalty() THEN call create_approval_request(risk_level="Critical")
  - If RECOMMENDED_ACTION starts with "ESCALATE_PROCUREMENT" → call calculate_and_apply_penalty() THEN call create_approval_request(risk_level="High")
  - If RECOMMENDED_ACTION starts with "AUTO_PENALTY" → call calculate_and_apply_penalty() THEN call flag_sla_breach()
STEP 4: Call write_audit_log() with the action you took and why.

## CRITICAL RULES:
- You MUST call create_approval_request() when RECOMMENDED_ACTION says ESCALATE. Never skip this.
- You MUST call write_audit_log() as your last action. Always.
- Do NOT explain what you are going to do without calling a tool. Just call the tools.
"""


def run_operations_agent(alert: dict, db: Client, provider: str = "mistral") -> dict:
    """Run the Operations Agent on a given alert.

    Args:
        alert:    Full alert record dict.
        db:       Supabase admin client.
        provider: LLM provider to use: \"mistral\" (default) or \"groq\".
    """
    set_db(db)

    policy_context = retrieve_policy(
        query=f"{alert.get('alert_type', '')} {alert.get('description', '')}",
        department="Operations",
        k=3,
    )

    run_id = str(uuid.uuid4())
    set_run_id(run_id)  # inject run_id into tools so audit_logs are linked
    # Bug #3 fixed: pass provider so the caller's selection is honoured
    graph = create_agent_graph(OPERATIONS_TOOLS, OPERATIONS_SYSTEM_PROMPT, policy_context, provider=provider)

    user_prompt = (
        f"You have been triggered to investigate the following Operations alert:\n\n"
        f"Alert ID    : {alert['id']}\n"
        f"Alert Type  : {alert['alert_type']}\n"
        f"Severity    : {alert['severity']}\n"
        f"Title       : {alert['title']}\n"
        f"Description : {alert.get('description', 'N/A')}\n"
        f"Related Record ID   : {alert.get('related_record_id', 'N/A')} (shipment_id)\n"
        f"Related Record Type : {alert.get('related_record_type', 'N/A')}\n\n"
        f"Investigate the SLA breach, calculate days delayed and cargo value, "
        f"determine breach severity per Operations SOP v2.0, execute the appropriate action, "
        f"and write a comprehensive audit log entry."
    )

    initial_state = {
        "messages": [HumanMessage(content=user_prompt)],
        "alert_id": alert["id"],
        "department": "Operations",
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
