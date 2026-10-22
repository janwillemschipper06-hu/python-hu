-- ---------------------------------------------------------------------------
-- Reference: create the contained SQL user for the Container App's user-assigned
-- managed identity and grant it EXECUTE on the onboarding schema (stored-
-- procedure-only access; see docs/adr/0002 and docs/adr/0008).
--
-- This is NOT run by the DACPAC. The pipeline's SqlUserSetup job
-- (.devops/templates/stage-database.yml) runs the equivalent inline after the
-- DACPAC deploys, deriving the SID from the identity's client id (read directly
-- from the identity resource with `az identity show`). Kept here as documentation
-- and for manual/local execution.
--
-- The user is the user-assigned managed identity (docs/adr/0003), display name
-- id-cst-cop-<env>. It is created WITH SID (not FROM EXTERNAL PROVIDER) so it does
-- NOT require the SQL server's identity to have Microsoft Entra Directory Readers.
-- Azure SQL matches a managed identity by its client (application) id, so the SID
-- is built from the client id. TYPE = E is the category Azure SQL uses for
-- managed identities.
--
-- To run by hand, replace <env> and set @clientId to the identity's client
-- (application) id, e.g.:
--   az identity show -g rg-cst-cop-<env> -n id-cst-cop-<env> --query clientId -o tsv
-- ---------------------------------------------------------------------------

DECLARE @clientId UNIQUEIDENTIFIER = N'00000000-0000-0000-0000-000000000000'; -- <-- replace
DECLARE @sid VARBINARY(16) = CAST(@clientId AS VARBINARY(16));
DECLARE @sidText NVARCHAR(100) = CONVERT(NVARCHAR(100), @sid, 1);
DECLARE @sql NVARCHAR(MAX);

-- Drop the user if it already exists so it is always rebound to the identity's
-- current client id.
IF
    EXISTS (
        SELECT 1
        FROM sys.database_principals
        WHERE name = N'id-cst-cop-dev'
    )
    DROP USER [id-cst-cop-dev];

SET @sql = N'CREATE USER [id-cst-cop-dev] WITH SID = ' + @sidText + N', TYPE = E;';
EXEC sp_executesql @sql;

-- Grant EXECUTE on the onboarding schema only. Per docs/adr/0002 and
-- docs/adr/0008 the app reaches the database exclusively through stored
-- procedures — no direct SELECT/INSERT/UPDATE/DELETE on base tables — so it is
-- NOT added to db_datareader. Ownership chaining lets the schema-owned
-- procedures read/write the schema-owned tables on the caller's behalf. This one
-- schema-level grant covers every procedure in the schema, including the identity
-- ones (GetUserByOid, UpsertUser, AppendAuditEvent), with
-- no per-object grant needed.
GRANT EXECUTE ON SCHEMA::[onboarding] TO [id-cst-cop-dev];

-- Append-only audit trail (security-design §12): onboarding.AuditLog is written
-- only via the AppendAuditEvent procedure, and there is no update/delete proc.
-- The app has no direct table DML anyway (EXECUTE only, above); this DENY is
-- defence-in-depth so the log can never be rewritten or tombstoned even if a
-- direct table grant were ever added by mistake. Ownership chaining is unaffected,
-- so AppendAuditEvent still inserts normally.
DENY UPDATE, DELETE ON OBJECT::[onboarding].[AuditLog] TO [id-cst-cop-dev];
GO
