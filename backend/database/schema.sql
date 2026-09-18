-- ============================================================
-- AIONOS Agentic AI Factory — Database Schema
-- Run this in Supabase SQL Editor:
-- Dashboard → SQL Editor → New query → paste → Run
-- ============================================================

-- Enable UUID extension (optional, we use integer PKs)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────
-- Finance
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS suppliers (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(200) NOT NULL,
    contact_email    VARCHAR(200),
    payment_terms    INTEGER DEFAULT 30,
    credit_limit     FLOAT DEFAULT 100000,
    country          VARCHAR(100),
    category         VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS invoices (
    id               SERIAL PRIMARY KEY,
    invoice_number   VARCHAR(50) UNIQUE NOT NULL,
    supplier_id      INTEGER REFERENCES suppliers(id),
    amount           FLOAT NOT NULL,
    po_amount        FLOAT NOT NULL,
    po_number        VARCHAR(50),
    currency         VARCHAR(10) DEFAULT 'USD',
    status           VARCHAR(50) DEFAULT 'pending',
    due_date         TIMESTAMPTZ,
    has_mismatch     BOOLEAN DEFAULT FALSE,
    mismatch_reason  VARCHAR(500),
    mismatch_amount  FLOAT DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- HR
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS employees (
    id                 SERIAL PRIMARY KEY,
    name               VARCHAR(200) NOT NULL,
    email              VARCHAR(200) UNIQUE,
    department         VARCHAR(100),
    role               VARCHAR(200),
    start_date         TIMESTAMPTZ,
    onboarding_status  VARCHAR(50) DEFAULT 'in_progress',
    manager_name       VARCHAR(200),
    manager_email      VARCHAR(200),
    location           VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS onboarding_tasks (
    id              SERIAL PRIMARY KEY,
    employee_id     INTEGER REFERENCES employees(id),
    task_name       VARCHAR(300) NOT NULL,
    category        VARCHAR(100),
    status          VARCHAR(50) DEFAULT 'pending',
    blocker_reason  VARCHAR(500),
    assigned_to     VARCHAR(200),
    due_date        TIMESTAMPTZ
);

-- ─────────────────────────────────────────────
-- Sales
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS contacts (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(200) NOT NULL,
    company   VARCHAR(200),
    email     VARCHAR(200),
    phone     VARCHAR(50),
    industry  VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS deals (
    id                   SERIAL PRIMARY KEY,
    deal_name            VARCHAR(300) NOT NULL,
    contact_id           INTEGER REFERENCES contacts(id),
    value                FLOAT,
    stage                VARCHAR(100),
    last_activity_date   TIMESTAMPTZ,
    expected_close_date  TIMESTAMPTZ,
    assigned_rep         VARCHAR(200),
    is_stalled           BOOLEAN DEFAULT FALSE,
    days_stalled         INTEGER DEFAULT 0,
    stall_reason         VARCHAR(500),
    probability          FLOAT DEFAULT 50,
    notes                TEXT
);

-- ─────────────────────────────────────────────
-- Operations
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS supplier_contracts (
    id                 SERIAL PRIMARY KEY,
    supplier_id        INTEGER REFERENCES suppliers(id),
    contract_number    VARCHAR(50) UNIQUE NOT NULL,
    sla_delivery_days  INTEGER DEFAULT 7,
    penalty_per_day    FLOAT DEFAULT 500,
    max_penalty        FLOAT DEFAULT 10000,
    start_date         TIMESTAMPTZ,
    end_date           TIMESTAMPTZ,
    is_active          BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS shipments (
    id                      SERIAL PRIMARY KEY,
    tracking_number         VARCHAR(50) UNIQUE NOT NULL,
    contract_id             INTEGER REFERENCES supplier_contracts(id),
    origin                  VARCHAR(200),
    destination             VARCHAR(200),
    cargo_description       VARCHAR(300),
    cargo_value             FLOAT,
    promised_delivery_date  TIMESTAMPTZ,
    actual_delivery_date    TIMESTAMPTZ,
    status                  VARCHAR(50) DEFAULT 'in_transit',
    has_sla_breach          BOOLEAN DEFAULT FALSE,
    days_delayed            INTEGER DEFAULT 0,
    calculated_penalty      FLOAT DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- Core Agent Tables
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS alerts (
    id                   SERIAL PRIMARY KEY,
    department           VARCHAR(50) NOT NULL,
    alert_type           VARCHAR(100) NOT NULL,
    severity             VARCHAR(20) DEFAULT 'High',
    status               VARCHAR(30) DEFAULT 'Open',
    title                VARCHAR(300) NOT NULL,
    description          TEXT,
    related_record_id    INTEGER,
    related_record_type  VARCHAR(100),
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    resolved_at          TIMESTAMPTZ,
    agent_run_id         VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id               SERIAL PRIMARY KEY,
    alert_id         INTEGER REFERENCES alerts(id),
    agent_name       VARCHAR(100),
    action           VARCHAR(200) NOT NULL,
    details          TEXT,
    step_index       INTEGER DEFAULT 0,
    timestamp        TIMESTAMPTZ DEFAULT NOW(),
    is_human_action  BOOLEAN DEFAULT FALSE,
    run_id           VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS approval_requests (
    id                SERIAL PRIMARY KEY,
    alert_id          INTEGER REFERENCES alerts(id),
    agent_name        VARCHAR(100),
    action_requested  VARCHAR(300),
    risk_level        VARCHAR(20),
    context_summary   TEXT,
    policy_reference  TEXT,
    status            VARCHAR(20) DEFAULT 'pending',
    decision_reason   TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    decided_at        TIMESTAMPTZ
);

-- ─────────────────────────────────────────────
-- Row Level Security (disable for dev, enable for prod)
-- ─────────────────────────────────────────────
ALTER TABLE suppliers          DISABLE ROW LEVEL SECURITY;
ALTER TABLE invoices           DISABLE ROW LEVEL SECURITY;
ALTER TABLE employees          DISABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding_tasks   DISABLE ROW LEVEL SECURITY;
ALTER TABLE contacts           DISABLE ROW LEVEL SECURITY;
ALTER TABLE deals              DISABLE ROW LEVEL SECURITY;
ALTER TABLE supplier_contracts DISABLE ROW LEVEL SECURITY;
ALTER TABLE shipments          DISABLE ROW LEVEL SECURITY;
ALTER TABLE alerts             DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs         DISABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests  DISABLE ROW LEVEL SECURITY;

SELECT 'Schema created successfully!' AS result;
