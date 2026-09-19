"""
agents package - Department-specific and Supervisor LangGraph agents for AIONOS.

Public API:
    run_agent(alert, db)            -> dict   department dispatcher
    run_supervisor_agent(alert, db) -> dict   multi-agent orchestrator
"""

from supabase import Client

from agents.finance_agent    import run_finance_agent
from agents.hr_agent         import run_hr_agent
from agents.sales_agent      import run_sales_agent
from agents.operations_agent import run_operations_agent
from agents.supervisor       import run_supervisor_agent  # noqa: F401

_DISPATCH = {
    "Finance":    run_finance_agent,
    "HR":         run_hr_agent,
    "Sales":      run_sales_agent,
    "Operations": run_operations_agent,
}


def run_agent(alert: dict, db: Client, provider: str = "mistral") -> dict:
    """
    Dispatch the correct department agent for an alert.

    Args:
        alert:    Full alert record dict (must include 'department' key).
        db:       Supabase admin client.
        provider: LLM provider: \"mistral\" (default) or \"groq\".

    Returns:
        Agent result dict: {run_id, alert_id, department, final_message, steps, total_steps}

    Raises:
        ValueError: If the alert department is not supported.
    """
    department = alert.get("department", "")
    runner = _DISPATCH.get(department)
    if not runner:
        raise ValueError(
            f"No agent registered for department '{department}'. "
            f"Supported: {list(_DISPATCH.keys())}"
        )
    # Bug #3 fixed: pass provider through so it reaches create_agent_graph()
    return runner(alert, db, provider=provider)


__all__ = ["run_agent", "run_supervisor_agent"]
