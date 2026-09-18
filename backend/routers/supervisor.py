"""
supervisor.py -- Supervisor Agent router for AIONOS.

POST /api/supervisor/run            -- trigger supervisor (blocking)
GET  /api/supervisor/stream/{id}    -- SSE-stream supervisor run
GET  /api/supervisor/tree/{run_id}  -- orchestration delegation tree
GET  /api/supervisor/history        -- last N supervisor runs
"""

import json
import queue
import threading
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import Client

from database.db import get_admin
from agents.supervisor import run_supervisor_agent
from routers.stream import _run_streaming, _sse, _ping, KEEPALIVE_INTERVAL

router = APIRouter(prefix="/api/supervisor", tags=["Supervisor"])


class SupervisorRunRequest(BaseModel):
    alert_id: int


# ── Blocking run ──────────────────────────────────────────────────────────────

@router.post("/run")
def trigger_supervisor(body: SupervisorRunRequest, db: Client = Depends(get_admin)):
    """
    Trigger the Supervisor Agent on a Critical alert (blocking).
    For streaming, use GET /api/supervisor/stream/{alert_id}.
    """
    result = db.table("alerts").select("*").eq("id", body.alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert = result.data[0]
    if alert["status"] in ("Resolved", "Escalated"):
        raise HTTPException(
            status_code=400,
            detail=f"Alert is already '{alert['status']}'. Cannot re-run.",
        )

    try:
        agent_result = run_supervisor_agent(alert, db)
    except Exception as exc:
        db.table("audit_logs").insert({
            "alert_id":       body.alert_id,
            "agent_name":     "SupervisorAgent",
            "action":         "supervisor_error",
            "details":        f"Supervisor failed: {exc}",
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "is_human_action": False,
        }).execute()
        raise HTTPException(status_code=500, detail=f"Supervisor error: {exc}")

    return {
        "message":    "Supervisor run completed.",
        "alert_id":   body.alert_id,
        "department": alert["department"],
        **agent_result,
    }


# ── SSE streaming run ─────────────────────────────────────────────────────────

def _run_supervisor_streaming(alert: dict, db: Client, event_q: queue.Queue, provider: str = "mistral") -> None:
    """Run supervisor in a background thread, push events to queue."""
    try:
        event_q.put({"type": "supervisor_start", "alert_id": alert["id"]})
        result = run_supervisor_agent(alert, db, event_queue=event_q, provider=provider)

        updated = db.table("alerts").select("status").eq("id", alert["id"]).execute()
        final_status = updated.data[0]["status"] if updated.data else "Unknown"

        event_q.put({
            "type":          "done",
            "run_id":        result.get("supervisor_run_id", ""),
            "steps":         result.get("total_steps", 0),
            "final_status":  final_status,
            "final_message": (result.get("final_message") or "")[:300],
        })
    except Exception as exc:
        event_q.put({"type": "error", "message": str(exc)[:400]})
    finally:
        event_q.put(None)


async def _supervisor_event_generator(alert: dict, db: Client, provider: str = "mistral") -> AsyncGenerator[str, None]:
    event_q: queue.Queue = queue.Queue()
    thread = threading.Thread(
        target=_run_supervisor_streaming,
        args=(alert, db, event_q, provider),
        daemon=True,
    )
    thread.start()
    yield _sse({"type": "start", "alert_id": alert["id"], "department": "Supervisor", "provider": provider})
    import asyncio
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


@router.get("/stream/{alert_id}")
async def stream_supervisor(alert_id: int, provider: str = "mistral", db: Client = Depends(get_admin)):
    """SSE stream for live Supervisor Agent orchestration.

    Query params:
        provider: "mistral" (default) | "groq"
    """
    result = db.table("alerts").select("*").eq("id", alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert = result.data[0]
    if alert["status"] in ("Resolved", "Escalated"):
        raise HTTPException(status_code=400, detail=f"Alert already '{alert['status']}'.")
    valid_providers = {"mistral", "groq"}
    if provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Invalid provider '{provider}'. Choose from: {valid_providers}")
    return StreamingResponse(
        _supervisor_event_generator(alert, db, provider),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── Delegation tree ───────────────────────────────────────────────────────────

@router.get("/tree/{run_id}")
def get_orchestration_tree(run_id: str, db: Client = Depends(get_admin)):
    """
    Returns the full delegation tree for a supervisor run.
    Includes all sub-agent tasks with their status and outcome.
    """
    tasks = db.table("agent_tasks").select("*")                .eq("parent_run_id", run_id)                .order("triggered_at")                .execute().data or []

    supervisor_logs = db.table("audit_logs").select("*")                         .eq("run_id", run_id)                         .eq("agent_name", "SupervisorAgent")                         .order("timestamp")                         .execute().data or []

    return {
        "run_id":          run_id,
        "total_tasks":     len(tasks),
        "tasks":           tasks,
        "supervisor_logs": supervisor_logs,
    }


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history")
def get_supervisor_history(limit: int = 20, db: Client = Depends(get_admin)):
    """
    Returns the last N supervisor runs (distinct parent_run_ids) with task counts.
    """
    logs = db.table("audit_logs").select(
        "run_id, alert_id, action, details, timestamp"
    ).eq("agent_name", "SupervisorAgent")      .eq("action", "orchestration_complete")      .order("timestamp", desc=True)      .limit(limit)      .execute().data or []

    return {
        "history": logs,
        "total":   len(logs),
    }
