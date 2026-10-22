-- No SECRET: authenticates as the logical server's primary user-assigned managed
-- identity, which must exist as a user (FROM EXTERNAL PROVIDER) on the remote DB.
-- Requires the database master key created in Scripts\pre-deploy.sql.
CREATE DATABASE SCOPED CREDENTIAL [MiCred]
WITH IDENTITY = 'Managed Identity';
