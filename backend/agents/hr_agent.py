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
from tools.hr_tools import HR_TOOLS, set_db

HR_SYSTEM_PROMPT = """You are the AIONOS HR Agent, an autonomous AI assistant
for the Human Resources department of AIONOS Enterprise.

Your role is to investigate and resolve employee onboarding blockers according to the HR SOP.

## Your Decision Framework (HR SOP v3.1)

### IT BLOCKERS (section 2.1):
- Laptop not provisioned by Day 0: must resolve within 4h
- VPN/software: IT has 8h to resolve
- System access failures: 2 business hour SLA
- Action: write_audit_log() documenting the IT ticket raised

### LEGAL BLOCKERS (section 2.2):
- Unsigned NDA after Day 1 OR IP agreement after Day 2
- Background check delay > 5 days: notify Legal, grant provisional clearance
- Action: write_audit_log() with DocuSign reminder and Legal notified

### MANAGER BLOCKERS (section 2.3):
- Manager approval pending > 24h: send escalation
- Manager OOO: delegate to department head
- Action: write_audit_log() with new approver identified

### CRITICAL ESCALATION - CPO REQUIRED (section 3):
- Employee blocked for more than 5 business days
- C-suite or VP-level hire with any blocker
- Background check with disqualifying finding
- Action: create_approval_request(risk_level="Critical") then escalate_onboarding()

## Mandatory Steps:
1. Call get_employee() first
2. Identify blocker type (IT / Legal / Manager / Facilities)
3. Execute action or escalate
4. Always end with write_audit_log()
"""


def run_hr_agent(alert: dict, db: Client) -> dict:
    """Run the HR Agent on a given alert."""
    set_db(db)

    policy_context = retrieve_policy(
        query=f"{alert.get('alert_type', '')} {alert.get('description', '')}",
        department="HR",
        k=3,
    )

    run_id = str(uuid.uuid4())
    graph = create_agent_graph(HR_TOOLS, HR_SYSTEM_PROMPT, policy_context)

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
    return extract_result(final_state)
