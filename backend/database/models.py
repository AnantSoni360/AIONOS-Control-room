from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class AlertSeverity(str, enum.Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class AlertStatus(str, enum.Enum):
    OPEN = "Open"
    IN_PROGRESS = "In_Progress"
    RESOLVED = "Resolved"
    ESCALATED = "Escalated"
    PENDING_APPROVAL = "Pending_Approval"


class Department(str, enum.Enum):
    FINANCE = "Finance"
    HR = "HR"
    SALES = "Sales"
    OPERATIONS = "Operations"


# ─────────────────────────────────────────────
# Finance
# ─────────────────────────────────────────────

class Supplier(Base):
    __tablename__ = "suppliers"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(200), nullable=False)
    contact_email  = Column(String(200))
    payment_terms  = Column(Integer, default=30)   # days
    credit_limit   = Column(Float, default=100000.0)
    country        = Column(String(100))
    category       = Column(String(100))           # e.g. IT, Logistics, Raw Materials

    invoices       = relationship("Invoice", back_populates="supplier")
    contracts      = relationship("SupplierContract", back_populates="supplier")


class Invoice(Base):
    __tablename__ = "invoices"

    id               = Column(Integer, primary_key=True, index=True)
    invoice_number   = Column(String(50), unique=True, nullable=False)
    supplier_id      = Column(Integer, ForeignKey("suppliers.id"))
    amount           = Column(Float, nullable=False)        # Invoice amount
    po_amount        = Column(Float, nullable=False)        # Approved PO amount
    po_number        = Column(String(50))
    currency         = Column(String(10), default="USD")
    status           = Column(String(50), default="pending")  # pending, approved, rejected, paid
    due_date         = Column(DateTime)
    has_mismatch     = Column(Boolean, default=False)
    mismatch_reason  = Column(String(500))
    mismatch_amount  = Column(Float, default=0.0)           # abs difference
    created_at       = Column(DateTime, default=datetime.utcnow)

    supplier         = relationship("Supplier", back_populates="invoices")


# ─────────────────────────────────────────────
# HR
# ─────────────────────────────────────────────

class Employee(Base):
    __tablename__ = "employees"

    id                 = Column(Integer, primary_key=True, index=True)
    name               = Column(String(200), nullable=False)
    email              = Column(String(200), unique=True)
    department         = Column(String(100))
    role               = Column(String(200))
    start_date         = Column(DateTime)
    onboarding_status  = Column(String(50), default="in_progress")  # in_progress, completed, blocked
    manager_name       = Column(String(200))
    manager_email      = Column(String(200))
    location           = Column(String(100))

    tasks              = relationship("OnboardingTask", back_populates="employee")


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id              = Column(Integer, primary_key=True, index=True)
    employee_id     = Column(Integer, ForeignKey("employees.id"))
    task_name       = Column(String(300), nullable=False)
    category        = Column(String(100))   # IT, Legal, HR, Facilities
    status          = Column(String(50), default="pending")  # pending, in_progress, completed, blocked
    blocker_reason  = Column(String(500))
    assigned_to     = Column(String(200))
    due_date        = Column(DateTime)

    employee        = relationship("Employee", back_populates="tasks")


# ─────────────────────────────────────────────
# Sales
# ─────────────────────────────────────────────

class Contact(Base):
    __tablename__ = "contacts"

    id       = Column(Integer, primary_key=True, index=True)
    name     = Column(String(200), nullable=False)
    company  = Column(String(200))
    email    = Column(String(200))
    phone    = Column(String(50))
    industry = Column(String(100))

    deals    = relationship("Deal", back_populates="contact")


class Deal(Base):
    __tablename__ = "deals"

    id                  = Column(Integer, primary_key=True, index=True)
    deal_name           = Column(String(300), nullable=False)
    contact_id          = Column(Integer, ForeignKey("contacts.id"))
    value               = Column(Float)                    # Deal value in USD
    stage               = Column(String(100))              # Prospecting, Qualification, Proposal, Negotiation, Closed Won, Closed Lost
    last_activity_date  = Column(DateTime)
    expected_close_date = Column(DateTime)
    assigned_rep        = Column(String(200))
    is_stalled          = Column(Boolean, default=False)
    days_stalled        = Column(Integer, default=0)
    stall_reason        = Column(String(500))
    probability         = Column(Float, default=50.0)      # win probability %
    notes               = Column(Text)

    contact             = relationship("Contact", back_populates="deals")


# ─────────────────────────────────────────────
# Operations
# ─────────────────────────────────────────────

class SupplierContract(Base):
    __tablename__ = "supplier_contracts"

    id                 = Column(Integer, primary_key=True, index=True)
    supplier_id        = Column(Integer, ForeignKey("suppliers.id"))
    contract_number    = Column(String(50), unique=True, nullable=False)
    sla_delivery_days  = Column(Integer, default=7)          # Max allowed delivery days
    penalty_per_day    = Column(Float, default=500.0)        # USD per day delay
    max_penalty        = Column(Float, default=10000.0)
    start_date         = Column(DateTime)
    end_date           = Column(DateTime)
    is_active          = Column(Boolean, default=True)

    supplier           = relationship("Supplier", back_populates="contracts")
    shipments          = relationship("Shipment", back_populates="contract")


class Shipment(Base):
    __tablename__ = "shipments"

    id                     = Column(Integer, primary_key=True, index=True)
    tracking_number        = Column(String(50), unique=True, nullable=False)
    contract_id            = Column(Integer, ForeignKey("supplier_contracts.id"))
    origin                 = Column(String(200))
    destination            = Column(String(200))
    cargo_description      = Column(String(300))
    cargo_value            = Column(Float)
    promised_delivery_date = Column(DateTime)
    actual_delivery_date   = Column(DateTime)
    status                 = Column(String(50), default="in_transit")  # in_transit, delivered, delayed, lost
    has_sla_breach         = Column(Boolean, default=False)
    days_delayed           = Column(Integer, default=0)
    calculated_penalty     = Column(Float, default=0.0)
    created_at             = Column(DateTime, default=datetime.utcnow)

    contract               = relationship("SupplierContract", back_populates="shipments")


# ─────────────────────────────────────────────
# Core Agent Tables
# ─────────────────────────────────────────────

class Alert(Base):
    """Central alert queue — one record per detected exception."""
    __tablename__ = "alerts"

    id                  = Column(Integer, primary_key=True, index=True)
    department          = Column(String(50), nullable=False)    # Finance | HR | Sales | Operations
    alert_type          = Column(String(100), nullable=False)   # e.g. "invoice_mismatch"
    severity            = Column(String(20), default="High")    # Critical | High | Medium | Low
    status              = Column(String(30), default="Open")    # Open | In_Progress | Resolved | Escalated | Pending_Approval
    title               = Column(String(300), nullable=False)
    description         = Column(Text)
    related_record_id   = Column(Integer)                       # FK to the actual broken record
    related_record_type = Column(String(100))                   # "invoice" | "employee" | "deal" | "shipment"
    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow)
    resolved_at         = Column(DateTime)
    agent_run_id        = Column(String(100))                   # LangGraph run ID when agent is triggered

    audit_logs          = relationship("AuditLog", back_populates="alert")
    approvals           = relationship("ApprovalRequest", back_populates="alert")


class AuditLog(Base):
    """Immutable log of every agent action and human decision."""
    __tablename__ = "audit_logs"

    id              = Column(Integer, primary_key=True, index=True)
    alert_id        = Column(Integer, ForeignKey("alerts.id"))
    agent_name      = Column(String(100))                   # e.g. "FinanceAgent" | "HumanApprover"
    action          = Column(String(200), nullable=False)   # e.g. "queried_invoice", "sent_approval_request"
    details         = Column(Text)                          # JSON or human-readable detail
    step_index      = Column(Integer, default=0)            # ordering within a run
    timestamp       = Column(DateTime, default=datetime.utcnow)
    is_human_action = Column(Boolean, default=False)
    run_id          = Column(String(100))

    alert           = relationship("Alert", back_populates="audit_logs")


class ApprovalRequest(Base):
    """Human-in-the-loop escalation records."""
    __tablename__ = "approval_requests"

    id                = Column(Integer, primary_key=True, index=True)
    alert_id          = Column(Integer, ForeignKey("alerts.id"))
    agent_name        = Column(String(100))
    action_requested  = Column(String(300))    # What the agent wants to do
    risk_level        = Column(String(20))     # High | Critical
    context_summary   = Column(Text)           # Agent's findings summary
    policy_reference  = Column(Text)           # RAG-retrieved policy snippet
    status            = Column(String(20), default="pending")  # pending | approved | rejected
    decision_reason   = Column(Text)
    created_at        = Column(DateTime, default=datetime.utcnow)
    decided_at        = Column(DateTime)

    alert             = relationship("Alert", back_populates="approvals")
