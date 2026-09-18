-- ============================================================
-- AIONOS Phase 4 -- Orchestration / Delegation Tree Schema
-- Run in Supabase SQL Editor
-- ============================================================

-- Tracks every sub-agent spawned by the Supervisor during an orchestration run.
CREATE TABLE IF NOT EXISTS agent_tasks (
    id              SERIAL PRIMARY KEY,
    parent_run_id   UUID          NOT NULL,   -- Supervisor's run_id
    child_run_id    UUID,                      -- department agent run_id (set on completion)
    parent_dept     VARCHAR(50)   NOT NULL DEFAULT 'Supervisor',
    child_dept      VARCHAR(50)   NOT NULL,    -- Finance | HR | Sales | Operations
    alert_id        INTEGER       REFERENCES alerts(id),
    status          VARCHAR(20)   NOT NULL DEFAULT 'pending',
    triggered_at    TIMESTAMPTZ   DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    result_summary  TEXT,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS agent_tasks_parent_run_idx ON agent_tasks (parent_run_id);
CREATE INDEX IF NOT EXISTS agent_tasks_alert_idx      ON agent_tasks (alert_id);
CREATE INDEX IF NOT EXISTS agent_tasks_status_idx     ON agent_tasks (status);

ALTER TABLE agent_tasks DISABLE ROW LEVEL SECURITY;

SELECT 'Orchestration schema created!' AS result;
