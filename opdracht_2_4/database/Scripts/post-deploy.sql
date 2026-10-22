-- ---------------------------------------------------------------------------
-- Post-deploy script (runs after every DACPAC publish).
--
-- The managed-identity DB user and its permission grants are created by the
-- SqlUserSetup job in the pipeline (.devops/templates/stage-database.yml), which
-- runs after this DACPAC deploys so the schema already exists.
-- ---------------------------------------------------------------------------

-- Seeds the Project lookups (the admin-managed options from the legacy forms).
:r .\seed-lookups.sql
