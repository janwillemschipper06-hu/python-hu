-- Object definitions in a DACPAC do not get SQLCMD variable substitution, so the
-- remote server and database are literals. Both environments read the same CST DB.
CREATE EXTERNAL DATA SOURCE [RemoteSource]
WITH (
    TYPE = RDBMS,
    LOCATION = 'sql-9a-ba-cst.database.windows.net',
    DATABASE_NAME = 'BA_CST_PROD',
    CREDENTIAL = [MiCred]
);
