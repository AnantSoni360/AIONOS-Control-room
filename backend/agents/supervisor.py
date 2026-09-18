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

SUPERVISOR_SYSTEM_PROMPT = """You are the AIONOS Supervisor Agent -- a senior AI
orchestrator that coordinates the four department AI agents (Finance, HR, Sales,
Operations) to resolve complex, cross-department operational issues.

## Your Mission
When a Critical alert involves multiple departments or a high-value entity,
you must assess the full picture and coordinate a unified response.

## Your Orchestration Process

### Step 1 -- Assess Cross-Department Impact
- Call get_alert_details(alert_id) on the originating alert
- Call get_related_alerts(record_id, record_type) to find linked alerts
- Determine which departments are affected

### Step 2 -- Plan the Delegation Order
- Prioritise by severity and dependency
- Finance first if monetary risk is highest
- Operations if supply chain is disrupted
- HR if personnel are blocked
- Sales if deal revenue is at risk

### Step 3 -- Delegate (in order)
- Call delegate_to_finance / delegate_to_hr / delegate_to_sales / delegate_to_operations
  for each affected alert, passing the parent_run_id for tree tracking
- Wait for each result before proceeding (sequential delegation)

### Step 4 -- Synthesise and Escalate
- If any sub-agent requested approval OR total combined risk is Critical:
  Call create_cross_dept_escalation() with a concise summary of all findings
- If all issues resolved autonomously: log the outcome

### Step 5 -- Always End With
- Call write_supervisor_log(action="orchestration_complete", details=<full_summary>)

## Decision Rules
- NEVER skip write_supervisor_log at the end
- NEVER delegate the same alert_id twice
- If a sub-agent fails, still complete the other delegations
- Always pass your run_id as parent_run_id to delegation tools
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
    return result
