-- The onboarding schema owns every portal table and stored procedure. The app's
-- SQL principal (the Container App managed identity) is granted EXECUTE on this
-- schema only — never direct table rights — so all data access flows through the
-- EXECUTE-only stored procedures (docs/adr/0002, docs/adr/0008). That single
-- schema-level EXECUTE grant automatically covers every procedure added here
-- (GetUserByOid, UpsertUser, SearchCustomers, ...). The grant — and the
-- append-only DENY on AuditLog — are
-- applied after deploy because the app user does not exist at DACPAC time; see
-- database/Scripts/create-sql-user-app.sql and .devops/templates/stage-database.yml.
CREATE SCHEMA [onboarding] AUTHORIZATION [dbo];
