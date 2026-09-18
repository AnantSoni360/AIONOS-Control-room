"""
finance_agent.py - Finance Department LangGraph Agent.

Handles: invoice_mismatch, duplicate_invoice, missing_po, credit_limit_breach
Policy : rag/documents/finance_sop.txt
"""

import uuid
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from supabase import Client

from agents.base_agent import create_agent_graph, extract_result
from rag.retriever import retrieve_policy
from tools.finance_tools import FINANCE_TOOLS, set_db

FINANCE_SYSTEM_PROMPT = """You are the AIONOS Finance Agent, an autonomous AI assistant
for the Finance department of AIONOS Enterprise.

Your role is to investigate and resolve invoice exceptions according to the Finance SOP.

## Your Decision Framework (Finance SOP v2.4)

### AUTO-APPROVE (no human needed):
- Mismatch <= 2% of PO value AND <= $500 absolute difference
- Call: approve_invoice() then write_audit_log()

### SENIOR AP ANALYST APPROVAL REQUIRED:
- Mismatch > 2% but <= 10% of PO value  OR  $500-$5,000 absolute
- Call: create_approval_request(risk_level="High") then write_audit_log()

### CFO APPROVAL REQUIRED (Critical escalation):
- Mismatch > 10% of PO OR > $5,000 absolute
- Duplicate invoice detected
- Missing PO reference
- Currency mismatch
- Call: create_approval_request(risk_level="Critical") then write_audit_log()

### AUTO-REJECT:
- Invoice submitted > 90 days after delivery
- Supplier not on approved vendor list
- Invoice exceeds supplier credit limit
- VAT arithmetic error > 0.01%
- Call: reject_invoice() then write_audit_log()

## Mandatory Steps for Every Resolution:
1. Always call get_invoice() first to gather full context
2. Calculate mismatch percentage: abs(invoice_amount - po_amount) / po_amount * 100
3. Determine the correct action tier from the framework above
4. Execute the action (approve / reject / escalate)
5. Always end with write_audit_log() documenting your decision and policy reference
"""


def run_finance_agent(alert: dict, db: Client) -> dict:
    """Run the Finance Agent on a given alert."""
    set_db(db)

    policy_context = retrieve_policy(
        query=f"{alert.get('alert_type', '')} {alert.get('description', '')}",
        department="Finance",
        k=3,
    )

    run_id = str(uuid.uuid4())
    graph = create_agent_graph(FINANCE_TOOLS, FINANCE_SYSTEM_PROMPT, policy_context)

    user_prompt = (
        f"You have been triggered to investigate the following Finance alert:\n\n"
        f"Alert ID    : {alert['id']}\n"
        f"Alert Type  : {alert['alert_type']}\n"
        f"Severity    : {alert['severity']}\n"
        f"Title       : {alert['title']}\n"
        f"Description : {alert.get('description', 'N/A')}\n"
        f"Related Record ID   : {alert.get('related_record_id', 'N/A')}\n"
        f"Related Record Type : {alert.get('related_record_type', 'N/A')}\n\n"
        f"Investigate, determine the action per Finance SOP v2.4, execute it, "
        f"and write a comprehensive audit log entry."
    )

    initial_state = {
        "messages": [HumanMessage(content=user_prompt)],
        "alert_id": alert["id"],
        "department": "Finance",
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
