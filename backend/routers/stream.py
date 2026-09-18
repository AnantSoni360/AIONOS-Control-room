"""
stream.py -- Real-time SSE streaming for AIONOS agent execution.

GET  /api/agents/stream/{alert_id}  -- opens an SSE stream, runs the agent in a
     background thread, and pushes each reasoning step as it happens.
GET  /api/agents/active             -- returns all alerts currently In_Progress.
"""

import json
import queue
import asyncio
import threading
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from supabase import Client

from database.db import get_admin
from agents.base_agent import create_agent_graph, extract_result
from rag.retriever import retrieve_policy

router = APIRouter(prefix="/api/agents", tags=["Streaming"])

KEEPALIVE_INTERVAL = 5   # seconds between SSE keepalive pings


# ---- SSE helpers ------------------------------------------------------------

def _sse(data: dict, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _ping() -> str:
    return ": ping\n\n"


# ---- Background agent runner ------------------------------------------------

def _run_streaming(alert: dict, db: Client, event_q: queue.Queue) -> None:
    """
    Runs the department agent synchronously in a background thread.
    Pushes typed event dicts to event_q; puts None sentinel when done.
    """
    dept = alert.get("department", "")
    run_id = None

    try:
        if dept == "Finance":
            from agents.finance_agent import FINANCE_SYSTEM_PROMPT
            from tools.finance_tools import FINANCE_TOOLS, set_db
            set_db(db)
            tools, system_prompt = FINANCE_TOOLS, FINANCE_SYSTEM_PROMPT

        elif dept == "HR":
            from agents.hr_agent import HR_SYSTEM_PROMPT
            from tools.hr_tools import HR_TOOLS, set_db
            set_db(db)
            tools, system_prompt = HR_TOOLS, HR_SYSTEM_PROMPT

        elif dept == "Sales":
            from agents.sales_agent import SALES_SYSTEM_PROMPT
            from tools.sales_tools import SALES_TOOLS, set_db
            set_db(db)
            tools, system_prompt = SALES_TOOLS, SALES_SYSTEM_PROMPT

        elif dept == "Operations":
            from agents.operations_agent import OPERATIONS_SYSTEM_PROMPT
            from tools.operations_tools import OPERATIONS_TOOLS, set_db
            set_db(db)
            tools, system_prompt = OPERATIONS_TOOLS, OPERATIONS_SYSTEM_PROMPT

        else:
            event_q.put({"type": "error", "message": f"Unknown department: {dept}"})
            return

        import uuid
        from langchain_core.messages import HumanMessage

        run_id = str(uuid.uuid4())

        # RAG retrieval
        event_q.put({"type": "rag_fetch", "department": dept})
        policy_context = retrieve_policy(
            query=f"{alert.get('alert_type', '')} {alert.get('description', '')}",
            department=dept, k=3,
        )
        if policy_context:
            event_q.put({"type": "rag_ready", "chunks": policy_context.count("###")})

        # Build streaming graph
        graph = create_agent_graph(tools, system_prompt, policy_context, event_queue=event_q)

        user_prompt = (
            f"You have been triggered to investigate the following {dept} alert:\n\n"
            f"Alert ID    : {alert['id']}\n"
            f"Alert Type  : {alert['alert_type']}\n"
            f"Severity    : {alert['severity']}\n"
            f"Title       : {alert['title']}\n"
            f"Description : {alert.get('description', 'N/A')}\n"
            f"Related Record ID   : {alert.get('related_record_id', 'N/A')}\n"
            f"Related Record Type : {alert.get('related_record_type', 'N/A')}\n\n"
            f"Investigate, determine the correct action per {dept} SOP, execute it, "
            f"and write a comprehensive audit log entry."
        )

        initial_state = {
            "messages": [HumanMessage(content=user_prompt)],
            "alert_id": alert["id"],
            "department": dept,
            "run_id": run_id,
        }

        # Mark In_Progress
        db.table("alerts").update({
            "status": "In_Progress",
            "agent_run_id": run_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", alert["id"]).execute()

        final_state = graph.invoke(initial_state)
        final_state["run_id"] = run_id
        result = extract_result(final_state)

        updated = db.table("alerts").select("status").eq("id", alert["id"]).execute()
        final_status = updated.data[0]["status"] if updated.data else "Unknown"

        event_q.put({
            "type": "done",
            "run_id": run_id,
            "steps": result["total_steps"],
            "final_status": final_status,
            "final_message": (result.get("final_message") or "")[:300],
        })

    except Exception as exc:
        event_q.put({"type": "error", "message": str(exc)[:400]})
        try:
            db.table("audit_logs").insert({
                "alert_id": alert["id"],
                "agent_name": f"{dept}Agent",
                "action": "agent_error",
                "details": f"Streaming agent failed: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_human_action": False,
                "run_id": run_id,
            }).execute()
        except Exception:
            pass
    finally:
        event_q.put(None)   # sentinel


# ---- Async SSE generator ----------------------------------------------------

async def _event_generator(alert: dict, db: Client) -> AsyncGenerator[str, None]:
    event_q: queue.Queue = queue.Queue()

    thread = threading.Thread(
        target=_run_streaming, args=(alert, db, event_q), daemon=True
    )
    thread.start()

    yield _sse({"type": "start", "alert_id": alert["id"], "department": alert["department"]})

    while True:
        try:
            try:
                event = event_q.get(timeout=KEEPALIVE_INTERVAL)
            except queue.Empty:
                yield _ping()
                continue

            if event is None:
                yield _sse({"type": "close"}, event="close")
                break

            yield _sse(event)

        except asyncio.CancelledError:
            break
        except Exception:
            break


# ---- Routes -----------------------------------------------------------------

@router.get("/stream/{alert_id}")
async def stream_agent(alert_id: int, db: Client = Depends(get_admin)):
    """
    SSE endpoint -- streams real-time agent reasoning steps.

    Connect with: new EventSource('/api/agents/stream/{alert_id}')

    Event types: start | rag_fetch | rag_ready | thinking |
                 tool_call | tool_result | done | error | close
    """
    result = db.table("alerts").select("*").eq("id", alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert = result.data[0]
    if alert["status"] in ("Resolved", "Escalated"):
        raise HTTPException(
            status_code=400,
            detail=f"Alert is already '{alert['status']}'. Cannot re-run agent.",
        )

    return StreamingResponse(
        _event_generator(alert, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/active")
def get_active_runs(db: Client = Depends(get_admin)):
    """Returns all alerts currently being processed (status=In_Progress)."""
    result = db.table("alerts").select(
        "id, title, department, severity, alert_type, agent_run_id, updated_at"
    ).eq("status", "In_Progress").order("updated_at", desc=True).execute()

    return {
        "active_runs": result.data or [],
        "count": len(result.data or []),
    }
