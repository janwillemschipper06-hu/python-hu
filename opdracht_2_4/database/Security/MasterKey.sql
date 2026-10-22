-- Declared so the project model can validate the scoped credential. The actual key
-- is created with its password in Scripts\pre-deploy.sql, so the key is already
-- present on the target and this object produces no change at publish.
CREATE MASTER KEY;
