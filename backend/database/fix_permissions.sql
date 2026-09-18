-- Run this in Supabase SQL Editor to allow anon key full access (dev mode)
-- This grants INSERT, UPDATE, DELETE to the anon role on all tables

-- Disable RLS on all tables
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

-- Grant full access to anon and authenticated roles
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

SELECT 'Permissions granted successfully!' AS result;
