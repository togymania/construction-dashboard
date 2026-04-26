-- =====================================================================
-- Cleanup Demo Projects
-- =====================================================================
-- Day 7 housekeeping: drops every project except the production
-- "Istanbul Havalimani Terminal B" record (id = 1) so the system can be
-- exercised against a single, real-world project.
--
-- Behaviour:
--   * Idempotent. If the only remaining project is already id = 1
--     (or the project name was renamed), the DELETE simply affects
--     0 rows.
--   * Wrapped in a transaction. If anything fails, no rows are removed.
--   * Relies on the existing CASCADE rules:
--       - projects -> budget_items (ON DELETE CASCADE)
--       - projects -> expenses     (ON DELETE CASCADE)
--     Any rows in those child tables that belong to deleted projects
--     are removed automatically.
--
-- Usage (PowerShell):
--   $env:PGPASSWORD = "postgres"
--   psql -U postgres -d construction_db -f scripts/cleanup_demo_projects.sql
--
-- Safety check before running:
--   psql -U postgres -d construction_db -c "SELECT id, name FROM projects;"
-- =====================================================================

BEGIN;

-- ---- Pre-flight snapshot ----
SELECT 'BEFORE projects'     AS phase, COUNT(*) AS cnt FROM projects;
SELECT 'BEFORE budget_items' AS phase, COUNT(*) AS cnt FROM budget_items;
SELECT 'BEFORE expenses'     AS phase, COUNT(*) AS cnt FROM expenses;

-- ---- The cleanup ----
-- Keep the production project (Istanbul Havalimani Terminal B, id = 1).
-- Anything else is demo / test data and is dropped, along with any
-- budget_items or expenses that referenced those projects.
DELETE FROM projects WHERE id <> 1;

-- ---- Post-flight snapshot ----
SELECT 'AFTER projects'     AS phase, COUNT(*) AS cnt FROM projects;
SELECT 'AFTER budget_items' AS phase, COUNT(*) AS cnt FROM budget_items;
SELECT 'AFTER expenses'     AS phase, COUNT(*) AS cnt FROM expenses;

SELECT id, name, status, is_active FROM projects ORDER BY id;

COMMIT;
