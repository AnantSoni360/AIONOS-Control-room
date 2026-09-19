"""
finance_tools.py - LangChain tools for the Finance Agent.

Policy reference: rag/documents/finance_sop.txt
Thresholds (from SOP 2):
  - Auto-approve : mismatch <= 2% of PO AND <= $500 absolute
  - Senior AP    : mismatch > 2% but <= 10%  OR  $500-$5000
  - CFO approval : mismatch > 10%  OR  > $5000  OR  duplicate  OR  missing PO
  - Auto-reject  : invoice > 90 days old | supplier not on list | exceeds credit limit
"""

import json
from datetime import datetime, timezone
from langchain_core.tools import tool
from supabase import Client

# ---------------------------------------------------------------------------
# Module-level Supabase client - injected at agent startup via set_db()
# ---------------------------------------------------------------------------
_db: Client | None = None
_run_id: str | None = None  # current run's ID, set by agent runner


def set_run_id(run_id: str) -> None:
    """Called by the agent runner to inject the current run_id before tool use."""
    global _run_id
    _run_id = run_id


def set_db(client: Client) -> None:
    """Called by the agent runner to inject the DB client before tool use."""
    global _db
    _db = client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def get_invoice(invoice_id: int) -> str:
    """
    Fetch a single invoice record together with its supplier information.
    Pre-computes the mismatch percentage and recommends an action tier.

    Args:
        invoice_id: Primary key of the invoice to retrieve.

    Returns:
        JSON string with invoice details, supplier info, pre-computed mismatch %,
        and a RECOMMENDED_ACTION field telling you exactly what to do next.
    """
    inv = _db.table("invoices").select("*").eq("id", invoice_id).execute().data
    if not inv:
        return json.dumps({"error": f"Invoice {invoice_id} not found."})
    inv = inv[0]

    sup = _db.table("suppliers").select("name,contact_email,credit_limit,payment_terms") \
             .eq("id", inv["supplier_id"]).execute().data
    inv["supplier"] = sup[0] if sup else {}

    # Pre-compute mismatch so the LLM doesn't have to do math
    invoice_amount = float(inv.get("amount") or 0)
    po_amount = float(inv.get("po_amount") or 1)
    mismatch_amount = float(inv.get("mismatch_amount") or abs(invoice_amount - po_amount))
    mismatch_pct = (mismatch_amount / po_amount * 100) if po_amount else 0

    inv["computed_invoice_amount"] = invoice_amount
    inv["computed_mismatch_pct"] = round(mismatch_pct, 2)
    inv["computed_mismatch_abs"] = round(mismatch_amount, 2)

    # Determine recommended action tier based on Finance SOP v2.4
    mismatch_reason = (inv.get("mismatch_reason") or "").lower()
    if "currency" in mismatch_reason or "duplicate" in mismatch_reason or "missing po" in mismatch_reason:
        inv["RECOMMENDED_ACTION"] = "ESCALATE_CFO: Call create_approval_request(risk_level='Critical')"
    elif mismatch_pct > 10 or mismatch_amount > 5000:
        inv["RECOMMENDED_ACTION"] = "ESCALATE_CFO: Call create_approval_request(risk_level='Critical')"
    elif mismatch_pct > 2 or mismatch_amount > 500:
        inv["RECOMMENDED_ACTION"] = "ESCALATE_SENIOR_AP: Call create_approval_request(risk_level='High')"
    elif invoice_amount == 0:
        inv["RECOMMENDED_ACTION"] = "ESCALATE_CFO: Invoice amount missing - Call create_approval_request(risk_level='Critical')"
    else:
        inv["RECOMMENDED_ACTION"] = "AUTO_APPROVE: Call approve_invoice() - mismatch within threshold"

    return json.dumps(inv, default=str)


@tool
def list_mismatched_invoices() -> str:
    """
    Return all pending invoices that have a PO/invoice amount mismatch.

    Returns:
        JSON list of invoices with has_mismatch=True and status='pending'.
    """
    rows = _db.table("invoices").select("*") \
              .eq("has_mismatch", True) \
              .eq("status", "pending") \
              .order("created_at", desc=True) \
              .execute().data
    return json.dumps(rows, default=str)


@tool
def approve_invoice(invoice_id: int, reason: str) -> str:
    """
    Approve an invoice - sets status to approved.
    Only call this when the mismatch is within the auto-approve threshold
    (<=2% of PO value AND <=500 absolute per Finance SOP section 2.1).

    Args:
        invoice_id: The invoice to approve.
        reason: Policy justification for the auto-approval.

    Returns:
        Confirmation message.
    """
    _db.table("invoices").update({"status": "approved"}).eq("id", invoice_id).execute()
    return json.dumps({
        "action": "approved",
        "invoice_id": invoice_id,
        "reason": reason,
        "timestamp": _now_iso(),
    })


@tool
def reject_invoice(invoice_id: int, reason: str) -> str:
    """
    Reject an invoice - sets status to rejected.
    Use only when the invoice meets auto-reject criteria per Finance SOP section 2.4.

    Args:
        invoice_id: The invoice to reject.
        reason: Specific policy-grounded rejection reason.

    Returns:
        Confirmation message.
    """
    _db.table("invoices").update({"status": "rejected"}).eq("id", invoice_id).execute()
    return json.dumps({
        "action": "rejected",
        "invoice_id": invoice_id,
        "reason": reason,
        "timestamp": _now_iso(),
    })


@tool
def create_approval_request(
    alert_id: int,
    action_requested: str,
    risk_level: str,
    context_summary: str,
    policy_reference: str,
) -> str:
    """
    Escalate an invoice decision to a human approver by creating an approval request.
    Use when mismatch exceeds auto-approve threshold or meets CFO-level escalation
    criteria per Finance SOP sections 2.2 and 2.3.

    Args:
        alert_id: The alert this approval belongs to.
        action_requested: What the agent wants to do.
        risk_level: High or Critical.
        context_summary: Agent findings summary for the human reviewer.
        policy_reference: Relevant SOP clauses cited.

    Returns:
        JSON with created approval_request id and status.
    """
    row = {
        "alert_id": alert_id,
        "agent_name": "FinanceAgent",
        "action_requested": action_requested,
        "risk_level": risk_level,
        "context_summary": context_summary,
        "policy_reference": policy_reference,
        "status": "pending",
        "created_at": _now_iso(),
    }
    result = _db.table("approval_requests").insert(row).execute()
    created = result.data[0] if result.data else row

    # Update the parent alert status to Pending_Approval
    _db.table("alerts").update({
        "status": "Pending_Approval",
        "updated_at": _now_iso(),
    }).eq("id", alert_id).execute()

    return json.dumps({
        "approval_request_id": created.get("id"),
        "status": "pending",
        "message": "Approval request created. Human review required.",
    })


@tool
def write_audit_log(
    alert_id: int,
    action: str,
    details: str,
    step_index: int = 0,
) -> str:
    """
    Write an immutable audit log entry for any agent action taken.
    Call this after every significant action per Finance SOP section 6.

    Args:
        alert_id: The alert being worked on.
        action: Short action name (e.g. queried_invoice, auto_approved, escalated_to_cfo).
        details: Human-readable description of what was done and why.
        step_index: Ordering index within this agent run.

    Returns:
        Confirmation of log written.
    """
    row = {
        "alert_id": alert_id,
        "agent_name": "FinanceAgent",
        "action": action,
        "details": details,
        "step_index": step_index,
        "timestamp": _now_iso(),
        "is_human_action": False,
        "run_id": _run_id,  # link log entries to the run for Observatory traces
    }
    _db.table("audit_logs").insert(row).execute()
    return json.dumps({"logged": True, "action": action})


FINANCE_TOOLS = [
    get_invoice,
    list_mismatched_invoices,
    approve_invoice,
    reject_invoice,
    create_approval_request,
    write_audit_log,
]
