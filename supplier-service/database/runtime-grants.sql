-- Run as supplier_migrator after upgrade head (also after downgrade/re-upgrade).
\set ON_ERROR_STOP on
BEGIN;
GRANT SELECT, INSERT, UPDATE, DELETE ON supplier, supplier_category TO supplier_runtime;
GRANT SELECT ON category, alembic_version TO supplier_runtime;
COMMIT;
