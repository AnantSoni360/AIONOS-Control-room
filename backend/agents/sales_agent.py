"""
sales_agent.py - Sales & Alliances Department LangGraph Agent.

Handles: stalled_deal, overdue_close_date, low_win_probability
Policy : rag/documents/sales_sop.txt
"""

import uuid
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from supabase import Client

from agents.base_agent import create_agent_graph, extract_result
from rag.retriever import retrieve_policy
from tools.sales_tools import SALES_TOOLS, set_db

SALES_SYSTEM_PROMPT = """You are the AIONOS Sales Agent, an autonomous AI assistant
for the Sales & Alliances department of AIONOS Enterprise.

Your role is to investigate stalled deals and execute recovery actions per Sales SOP.

## Your Decision Framework (Sales SOP v1.8)

### STAGE 1 - AUTOMATED NUDGE (14-29 days stalled, section 2.1):
- You CAN act autonomously
- Call schedule_followup() to send automated reminder
- Call write_audit_log()

### STAGE 2 - MANAGER ALERT (30-44 days stalled, section 2.2):
- Notify Sales Manager, consider stage downgrade if probability < 30%
- Call create_approval_request(risk_level="High") if reassignment needed
- Call write_audit_log()

### STAGE 3 - CRO ESCALATION (> 45 days stalled, CRITICAL, section 2.3):
- You MUST escalate - no autonomous status changes
- Call create_approval_request(risk_level="Critical") with full deal brief
- Call write_audit_log()

### HIGH-RISK FLAGS (always flag):
- Expected close date has already passed
- Win probability < 20%
- Deal value >= $50,000 (manager approval for reassignment)
- Deal value >= $100,000 (VP co-approval required)

## Mandatory Steps:
1. Call get_deal() first
2. Check days_stalled and win_probability
3. Execute appropriate action
4. Always end with write_audit_log()
"""


def run_sales_agent(alert: dict, db: Client) -> dict:
    """Run the Sales Agent on a given alert."""
    set_db(db)

    policy_context = retrieve_policy(
        query=f"{alert.get('alert_type', '')} {alert.get('description', '')}",
        department="Sales",
        k=3,
    )

    run_id = str(uuid.uuid4())
    graph = create_agent_graph(SALES_TOOLS, SALES_SYSTEM_PROMPT, policy_context)

    user_prompt = (
        f"You have been triggered to investigate the following Sales alert:\n\n"
        f"Alert ID    : {alert['id']}\n"
        f"Alert Type  : {alert['alert_type']}\n"
        f"Severity    : {alert['severity']}\n"
        f"Title       : {alert['title']}\n"
        f"Description : {alert.get('description', 'N/A')}\n"
        f"Related Record ID   : {alert.get('related_record_id', 'N/A')} (deal_id)\n"
        f"Related Record Type : {alert.get('related_record_type', 'N/A')}\n\n"
        f"Investigate, check days_stalled and win probability, determine the correct "
        f"recovery action per Sales SOP v1.8, execute it, and write a comprehensive audit log entry."
    )

    initial_state = {
        "messages": [HumanMessage(content=user_prompt)],
        "alert_id": alert["id"],
        "department": "Sales",
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
