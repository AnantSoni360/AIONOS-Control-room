"""
seed_data.py
────────────
Seeds all 4 departments into Supabase via REST API (no direct TCP needed).
Run AFTER executing schema.sql in Supabase SQL Editor.
"""

import random
from datetime import datetime, timedelta, timezone
from faker import Faker
from database.db import get_admin

supabase = get_admin()
fake = Faker()
random.seed(42)
Faker.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ts(dt: datetime) -> str:
    """Convert datetime to ISO string for Supabase REST."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def rand_date(days_back_min: int, days_back_max: int) -> datetime:
    delta = random.randint(days_back_min, days_back_max)
    return datetime.now(timezone.utc) - timedelta(days=delta)


def future_date(days_fwd_min: int, days_fwd_max: int) -> datetime:
    delta = random.randint(days_fwd_min, days_fwd_max)
    return datetime.now(timezone.utc) + timedelta(days=delta)


def insert(table: str, rows: list[dict]) -> list[dict]:
    """Insert rows and return inserted records with IDs."""
    if not rows:
        return []
    result = supabase.table(table).insert(rows).execute()
    return result.data


def clear_table(table: str):
    """Delete all rows from a table."""
    # Supabase REST: delete with a filter that matches all rows (id > 0)
    try:
        supabase.table(table).delete().gt("id", 0).execute()
    except Exception:
        pass  # Table might be empty already


# ─────────────────────────────────────────────────────────────────────────────
# Finance — Suppliers & Invoices
# ─────────────────────────────────────────────────────────────────────────────

SUPPLIER_CATEGORIES = ["IT Hardware", "Software Licenses", "Logistics", "Raw Materials",
                       "Professional Services", "Facilities", "Marketing", "Cloud Services"]

MISMATCH_REASONS = [
    "Invoice amount exceeds PO by more than 10% — requires approval",
    "Duplicate invoice detected — same PO number previously processed",
    "PO number missing on invoice — cannot match to approved purchase",
    "Currency mismatch — invoice in EUR but PO approved in USD",
    "Invoice submitted before PO approval date — procurement policy violation",
    "VAT calculation error — tax amount does not match jurisdiction rate",
    "Item description mismatch — invoice line items differ from PO",
    "Invoice total does not match sum of line items — arithmetic error",
]

SUPPLIER_NAMES = [
    "Apex Technologies Ltd", "GlobalTech Solutions", "NovaStar Logistics",
    "Vertex Cloud Services", "Quantum Raw Materials", "BluePeak IT Hardware",
    "Nexus Professional Services", "SkyBridge Marketing", "CoreFacilities Inc",
    "DataStream Software", "Prime Logistics Partners", "AlphaEdge Consulting",
    "TechWave Systems", "IronClad Manufacturing", "SwiftDeliver Co",
    "CloudFirst Solutions", "BrightPath Services", "OmegaSupply Corp",
    "ClearView Analytics", "FusionTech International"
]


def seed_suppliers() -> list[dict]:
    print("  -> Suppliers")
    rows = []
    for i, name in enumerate(SUPPLIER_NAMES):
        rows.append({
            "name": name,
            "contact_email": f"accounts@{name.lower().replace(' ', '').replace(',', '')[:12]}.com",
            "payment_terms": random.choice([15, 30, 45, 60]),
            "credit_limit": float(random.choice([50000, 100000, 150000, 200000, 500000])),
            "country": random.choice(["USA", "UK", "Germany", "India", "Singapore", "Canada"]),
            "category": SUPPLIER_CATEGORIES[i % len(SUPPLIER_CATEGORIES)],
        })
    return insert("suppliers", rows)


def seed_invoices(suppliers: list[dict]) -> list[dict]:
    print("  -> Invoices")
    rows = []
    for i in range(1, 51):
        supplier = random.choice(suppliers)
        po_amount = round(random.uniform(2000, 80000), 2)
        has_mismatch = i <= 15

        if has_mismatch:
            variance = random.choice([-1, 1]) * round(random.uniform(500, 8000), 2)
            amount = round(po_amount + variance, 2)
            mismatch_reason = random.choice(MISMATCH_REASONS)
            mismatch_amount = round(abs(variance), 2)
        else:
            amount = po_amount
            mismatch_reason = None
            mismatch_amount = 0.0

        rows.append({
            "invoice_number": f"INV-2026-{str(i).zfill(4)}",
            "supplier_id": supplier["id"],
            "amount": amount,
            "po_amount": po_amount,
            "po_number": f"PO-{random.randint(10000, 99999)}",
            "currency": random.choice(["USD", "USD", "USD", "EUR", "GBP"]),
            "status": "pending" if has_mismatch else random.choice(["pending", "pending", "approved", "rejected"]),
            "due_date": ts(future_date(5, 60)),
            "has_mismatch": has_mismatch,
            "mismatch_reason": mismatch_reason,
            "mismatch_amount": mismatch_amount,
            "created_at": ts(rand_date(1, 30)),
        })
    return insert("invoices", rows)


# ─────────────────────────────────────────────────────────────────────────────
# HR — Employees & Onboarding Tasks
# ─────────────────────────────────────────────────────────────────────────────

DEPARTMENTS_HR = ["Engineering", "Product", "Marketing", "Finance", "Legal",
                  "Sales", "HR", "Operations", "Data Science", "Customer Success"]

ROLES = {
    "Engineering": ["Senior Software Engineer", "Backend Engineer", "DevOps Engineer"],
    "Product": ["Product Manager", "Senior PM", "Associate PM"],
    "Marketing": ["Marketing Manager", "Content Strategist", "Growth Manager"],
    "Finance": ["Financial Analyst", "Senior Accountant", "FP&A Manager"],
    "Legal": ["Legal Counsel", "Compliance Officer", "Paralegal"],
    "Sales": ["Account Executive", "Sales Development Rep", "Regional Sales Manager"],
    "HR": ["HR Business Partner", "Talent Acquisition Specialist", "HR Coordinator"],
    "Operations": ["Operations Manager", "Supply Chain Analyst", "Ops Coordinator"],
    "Data Science": ["Data Scientist", "ML Engineer", "Data Analyst"],
    "Customer Success": ["Customer Success Manager", "Support Engineer", "Account Manager"],
}

ONBOARDING_TASKS_POOL = [
    ("Laptop provisioning & setup", "IT"),
    ("Email account creation", "IT"),
    ("VPN access configuration", "IT"),
    ("Software license assignment (Slack, Jira, Confluence)", "IT"),
    ("Security awareness training completion", "IT"),
    ("NDA signing and submission", "Legal"),
    ("Employment contract countersignature", "Legal"),
    ("Background check clearance", "Legal"),
    ("HR portal registration", "HR"),
    ("Benefits enrollment", "HR"),
    ("Payroll setup (bank details submission)", "HR"),
    ("Building access card issuance", "Facilities"),
    ("Desk assignment confirmation", "Facilities"),
]

BLOCKER_REASONS = [
    "Manager approval pending — manager out of office",
    "Background check vendor delay — result not received within SLA",
    "IT system outage — provisioning portal unavailable",
    "HR portal technical error — employee unable to complete enrollment",
    "Payroll vendor API failure — bank details not submitted",
    "Legal document not signed — employee did not receive DocuSign link",
    "Access card printer offline — Facilities unable to issue badge",
    "VPN license quota exceeded — IT procurement order pending",
]

MANAGERS = [
    ("Sarah Johnson", "s.johnson@company.com"),
    ("Michael Chen", "m.chen@company.com"),
    ("Priya Patel", "p.patel@company.com"),
    ("David Wilson", "d.wilson@company.com"),
    ("Lisa Torres", "l.torres@company.com"),
]


def seed_employees() -> list[dict]:
    print("  -> Employees")
    rows = []
    for i in range(1, 31):
        dept = random.choice(DEPARTMENTS_HR)
        role = random.choice(ROLES[dept])
        manager = random.choice(MANAGERS)
        is_blocked = i <= 10
        rows.append({
            "name": fake.name(),
            "email": f"{fake.first_name().lower()}.{fake.last_name().lower()}{i}@company.com",
            "department": dept,
            "role": role,
            "start_date": ts(rand_date(1, 45)),
            "onboarding_status": "blocked" if is_blocked else random.choice(["in_progress", "completed"]),
            "manager_name": manager[0],
            "manager_email": manager[1],
            "location": random.choice(["New York", "San Francisco", "London", "Bangalore", "Singapore"]),
        })
    return insert("employees", rows)


def seed_onboarding_tasks(employees: list[dict]):
    print("  -> Onboarding Tasks")
    rows = []
    for emp in employees:
        selected = random.sample(ONBOARDING_TASKS_POOL, k=random.randint(4, 7))
        is_blocked_emp = emp["onboarding_status"] == "blocked"
        for j, (task_name, category) in enumerate(selected):
            is_blocked_task = is_blocked_emp and j < 2
            rows.append({
                "employee_id": emp["id"],
                "task_name": task_name,
                "category": category,
                "status": "blocked" if is_blocked_task else random.choice(["pending", "in_progress", "completed"]),
                "blocker_reason": random.choice(BLOCKER_REASONS) if is_blocked_task else None,
                "assigned_to": random.choice(["IT Helpdesk", "HR Team", "Legal Team", "Facilities Team"]),
                "due_date": ts(future_date(1, 14)),
            })
    insert("onboarding_tasks", rows)


# ─────────────────────────────────────────────────────────────────────────────
# Sales — Contacts & Deals
# ─────────────────────────────────────────────────────────────────────────────

STALL_REASONS = [
    "No response from prospect for 30+ days — ghosted after proposal",
    "Budget freeze announced by prospect — deal paused until Q1",
    "Champion left the company — deal lost internal sponsor",
    "Competitor evaluation ongoing — prospect comparing 3 vendors",
    "Legal review stalled — prospect legal team backlogged",
    "Technical evaluation incomplete — POC not started",
    "No follow-up activity logged by sales rep in 35 days",
    "Contract redlining stalled — 5+ revision cycles with no conclusion",
]

REP_NAMES = ["Alex Rivera", "Jordan Lee", "Morgan Davis", "Taylor Smith",
             "Casey Brown", "Riley Wilson", "Drew Martinez", "Quinn Johnson"]

INDUSTRIES = ["FinTech", "Healthcare", "Retail", "Manufacturing", "SaaS",
              "Education", "Logistics", "Energy", "Media", "Government"]

DEAL_STAGES = ["Prospecting", "Qualification", "Proposal", "Negotiation"]


def seed_contacts() -> list[dict]:
    print("  -> Contacts")
    rows = [{"name": fake.name(), "company": fake.company(),
              "email": fake.email(), "phone": fake.phone_number()[:20],
              "industry": random.choice(INDUSTRIES)} for _ in range(30)]
    return insert("contacts", rows)


def seed_deals(contacts: list[dict]) -> list[dict]:
    print("  -> Deals")
    rows = []
    for i in range(1, 26):
        contact = random.choice(contacts)
        stage = random.choice(DEAL_STAGES)
        is_stalled = i <= 8
        days_stalled = random.randint(30, 65) if is_stalled else 0
        last_activity = datetime.now(timezone.utc) - timedelta(days=days_stalled if is_stalled else random.randint(1, 15))
        rows.append({
            "deal_name": f"{contact['company']} - {random.choice(['Enterprise License', 'Platform Subscription', 'Annual Contract'])}",
            "contact_id": contact["id"],
            "value": round(random.uniform(15000, 500000), 2),
            "stage": stage,
            "last_activity_date": ts(last_activity),
            "expected_close_date": ts(future_date(5, 90)),
            "assigned_rep": random.choice(REP_NAMES),
            "is_stalled": is_stalled,
            "days_stalled": days_stalled,
            "stall_reason": random.choice(STALL_REASONS) if is_stalled else None,
            "probability": round(random.uniform(20, 80), 1),
            "notes": fake.paragraph(nb_sentences=2) if random.random() > 0.5 else None,
        })
    return insert("deals", rows)


# ─────────────────────────────────────────────────────────────────────────────
# Operations — Supplier Contracts & Shipments
# ─────────────────────────────────────────────────────────────────────────────

ORIGINS = ["Shanghai, CN", "Mumbai, IN", "Hamburg, DE", "Los Angeles, US",
           "Singapore, SG", "Dubai, UAE", "Rotterdam, NL", "Tokyo, JP"]

DESTINATIONS = ["New York, US", "Chicago, US", "London, UK", "Frankfurt, DE",
                "Sydney, AU", "Toronto, CA", "Paris, FR", "Dallas, US"]

CARGO_TYPES = ["Electronic Components", "Industrial Machinery", "Pharmaceutical Supplies",
               "Automotive Parts", "Consumer Electronics", "Chemical Raw Materials",
               "Food & Beverage Stock", "Medical Devices"]


def seed_contracts(suppliers: list[dict]) -> list[dict]:
    print("  -> Supplier Contracts")
    selected = random.sample(suppliers, min(20, len(suppliers)))
    rows = []
    for i, supplier in enumerate(selected):
        rows.append({
            "supplier_id": supplier["id"],
            "contract_number": f"CTR-2026-{str(i+1).zfill(3)}",
            "sla_delivery_days": random.choice([5, 7, 10, 14]),
            "penalty_per_day": float(random.choice([250, 500, 750, 1000])),
            "max_penalty": float(random.choice([5000, 10000, 15000, 25000])),
            "start_date": ts(rand_date(180, 365)),
            "end_date": ts(future_date(60, 365)),
            "is_active": True,
        })
    return insert("supplier_contracts", rows)


def seed_shipments(contracts: list[dict]) -> list[dict]:
    print("  -> Shipments")
    rows = []
    for i in range(1, 41):
        contract = random.choice(contracts)
        has_breach = i <= 12
        penalty_per_day = contract.get("penalty_per_day", 500)
        max_penalty = contract.get("max_penalty", 10000)
        days_delayed = random.randint(2, 15) if has_breach else 0
        promised = rand_date(20, 60)
        penalty = min(days_delayed * penalty_per_day, max_penalty) if has_breach else 0.0
        rows.append({
            "tracking_number": f"SHIP-{random.randint(100000, 999999)}",
            "contract_id": contract["id"],
            "origin": random.choice(ORIGINS),
            "destination": random.choice(DESTINATIONS),
            "cargo_description": random.choice(CARGO_TYPES),
            "cargo_value": round(random.uniform(10000, 250000), 2),
            "promised_delivery_date": ts(promised),
            "actual_delivery_date": None if has_breach else ts(promised - timedelta(days=random.randint(0, 2))),
            "status": "delayed" if has_breach else random.choice(["in_transit", "delivered"]),
            "has_sla_breach": has_breach,
            "days_delayed": days_delayed,
            "calculated_penalty": round(penalty, 2),
            "created_at": ts(rand_date(30, 60)),
        })
    return insert("shipments", rows)


# ─────────────────────────────────────────────────────────────────────────────
# Alerts — Auto-generated from all exceptions
# ─────────────────────────────────────────────────────────────────────────────

def seed_alerts(invoices, employees, deals, shipments):
    print("  -> Alerts")
    rows = []

    for inv in invoices:
        if inv.get("has_mismatch"):
            mismatch_amount = inv.get("mismatch_amount", 0) or 0
            rows.append({
                "department": "Finance",
                "alert_type": "invoice_mismatch",
                "severity": "Critical" if mismatch_amount > 5000 else "High",
                "status": "Open",
                "title": f"Invoice Mismatch: {inv['invoice_number']}",
                "description": (
                    f"Invoice {inv['invoice_number']} from supplier #{inv['supplier_id']} "
                    f"shows a discrepancy of ${mismatch_amount:,.2f}. "
                    f"Reason: {inv.get('mismatch_reason', 'Unknown')}. "
                    f"Invoice: ${inv['amount']:,.2f} | PO: ${inv['po_amount']:,.2f}."
                ),
                "related_record_id": inv["id"],
                "related_record_type": "invoice",
                "created_at": inv.get("created_at") or ts(rand_date(1, 30)),
            })

    for emp in employees:
        if emp.get("onboarding_status") == "blocked":
            rows.append({
                "department": "HR",
                "alert_type": "onboarding_blocker",
                "severity": "High",
                "status": "Open",
                "title": f"Onboarding Blocked: {emp['name']}",
                "description": (
                    f"New hire {emp['name']} ({emp['role']} in {emp['department']}) "
                    f"is blocked since {str(emp.get('start_date', ''))[:10]}. "
                    f"Manager: {emp.get('manager_name', 'N/A')}. Location: {emp.get('location', 'N/A')}."
                ),
                "related_record_id": emp["id"],
                "related_record_type": "employee",
                "created_at": emp.get("start_date") or ts(rand_date(1, 30)),
            })

    for deal in deals:
        if deal.get("is_stalled"):
            days = deal.get("days_stalled", 30)
            rows.append({
                "department": "Sales",
                "alert_type": "stalled_deal",
                "severity": "Critical" if days > 45 else "High",
                "status": "Open",
                "title": f"Stalled Deal: {deal['deal_name'][:60]}",
                "description": (
                    f"Deal worth ${deal.get('value', 0):,.2f} assigned to {deal.get('assigned_rep', 'N/A')} "
                    f"has had no activity for {days} days. "
                    f"Stage: {deal.get('stage', 'N/A')}. "
                    f"Reason: {deal.get('stall_reason', 'Unknown')}."
                ),
                "related_record_id": deal["id"],
                "related_record_type": "deal",
                "created_at": deal.get("last_activity_date") or ts(rand_date(1, 60)),
            })

    for ship in shipments:
        if ship.get("has_sla_breach"):
            days_del = ship.get("days_delayed", 0)
            rows.append({
                "department": "Operations",
                "alert_type": "sla_breach",
                "severity": "Critical" if days_del > 7 else "High",
                "status": "Open",
                "title": f"SLA Breach: Shipment {ship['tracking_number']}",
                "description": (
                    f"Shipment {ship['tracking_number']} from {ship.get('origin')} to {ship.get('destination')} "
                    f"is {days_del} days past SLA. "
                    f"Cargo: {ship.get('cargo_description')} (${ship.get('cargo_value', 0):,.2f}). "
                    f"Penalty: ${ship.get('calculated_penalty', 0):,.2f}."
                ),
                "related_record_id": ship["id"],
                "related_record_type": "shipment",
                "created_at": ship.get("created_at") or ts(rand_date(1, 30)),
            })

    return insert("alerts", rows)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_seed():
    print("\nAIONOS Agentic AI Factory -- Database Seeder")
    print("=" * 50)

    # Clear tables in reverse dependency order
    print("\n>> Clearing existing data...")
    for table in ["audit_logs", "approval_requests", "alerts",
                  "shipments", "supplier_contracts",
                  "deals", "contacts",
                  "onboarding_tasks", "employees",
                  "invoices", "suppliers"]:
        clear_table(table)
    print("OK Data cleared\n")

    print("Seeding data...")
    suppliers  = seed_suppliers()
    invoices   = seed_invoices(suppliers)
    employees  = seed_employees()
    seed_onboarding_tasks(employees)
    contacts   = seed_contacts()
    deals      = seed_deals(contacts)
    contracts  = seed_contracts(suppliers)
    shipments  = seed_shipments(contracts)

    # Re-fetch employees with updated status for alert generation
    emp_data = supabase.table("employees").select("*").execute().data
    alerts    = seed_alerts(invoices, emp_data, deals, shipments)

    print("\n" + "=" * 50)
    print("SEEDING COMPLETE!")
    print(f"  Suppliers:        {len(suppliers)}")
    print(f"  Invoices:         {len(invoices)} ({sum(1 for i in invoices if i.get('has_mismatch'))} mismatches)")
    print(f"  Employees:        {len(employees)} ({sum(1 for e in emp_data if e.get('onboarding_status')=='blocked')} blocked)")
    print(f"  Deals:            {len(deals)} ({sum(1 for d in deals if d.get('is_stalled'))} stalled)")
    print(f"  Shipments:        {len(shipments)} ({sum(1 for s in shipments if s.get('has_sla_breach'))} SLA breaches)")
    print(f"  Alerts generated: {len(alerts)}")
    print("=" * 50)


if __name__ == "__main__":
    run_seed()
