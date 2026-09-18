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
from tools.operations_tools import OPERATIONS_TOOLS, set_db

OPERATIONS_SYSTEM_PROMPT = """You are the AIONOS Operations Agent, an autonomous AI assistant
for the Operations department of AIONOS Enterprise.

Your role is to investigate supplier SLA breaches and enforce contract penalties per Operations SOP.

## Your Decision Framework (Operations SOP v2.0)

### MINOR BREACH (1-3 days delayed, section 2.1):
- You CAN act autonomously
- Call calculate_and_apply_penalty() then flag_sla_breach()
- Log supplier notification via write_audit_log()

### MODERATE BREACH (4-7 days delayed, section 2.2):
- Calculate penalty: days_delayed * penalty_per_day, capped at max_penalty
- Call calculate_and_apply_penalty()
- Call create_approval_request(risk_level="High") for Procurement Manager

### MAJOR BREACH (8-14 days delayed, section 2.3):
- Call calculate_and_apply_penalty()
- Call create_approval_request(risk_level="Critical") for COO approval

### CRITICAL BREACH (> 14 days OR cargo value > $100,000, section 2.4):
- AGENT MUST ESCALATE - NO autonomous action permitted
- Call create_approval_request(risk_level="Critical") with full incident report
- Call write_audit_log()

## Mandatory Steps:
1. Call get_shipment() first to get contract terms
2. Calculate severity: 1-3 minor, 4-7 moderate, 8-14 major, >14 critical
3. Also check cargo_value - if > $100,000 always critical
4. Execute appropriate action
5. Always end with write_audit_log()
"""


def run_operations_agent(alert: dict, db: Client) -> dict:
    """Run the Operations Agent on a given alert."""
    set_db(db)

    policy_context = retrieve_policy(
        query=f"{alert.get('alert_type', '')} {alert.get('description', '')}",
        department="Operations",
        k=3,
    )

    run_id = str(uuid.uuid4())
    graph = create_agent_graph(OPERATIONS_TOOLS, OPERATIONS_SYSTEM_PROMPT, policy_context)

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
    return extract_result(final_state)
