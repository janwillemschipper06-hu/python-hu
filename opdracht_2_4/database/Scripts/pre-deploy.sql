-- ---------------------------------------------------------------------------
-- Pre-deploy script (runs before every DACPAC publish).
--
-- The database scoped credential used by the external data source (see
-- Security\ExternalSource.sql) requires a database master key, which a DACPAC
-- cannot model. Create it here, only when missing, so the deploy is idempotent.
-- The password comes from the pipeline secret `sqlMasterKeyPassword` via the
-- SQLCMD variable MasterKeyPassword; it is never stored in source control.
-- ---------------------------------------------------------------------------

IF
    NOT EXISTS (
        SELECT 1
        FROM sys.symmetric_keys
        WHERE name = '##MS_DatabaseMasterKey##'
    )
    BEGIN
        CREATE MASTER KEY ENCRYPTION BY PASSWORD = '$(MasterKeyPassword)';
    END
