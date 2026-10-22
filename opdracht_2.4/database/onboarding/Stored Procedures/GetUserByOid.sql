-- ---------------------------------------------------------------------------
-- Look up a single portal user by their Entra object id (oid). Returns zero or
-- one row (EntraOid is unique). The authorization layer uses this to resolve the
-- signed-in caller to their Users row (authentication-and-access §4.1).
--
-- EXECUTE-only access: the app is granted EXECUTE on the onboarding schema, not
-- SELECT on the tables (docs/adr/0002, docs/adr/0008); ownership chaining lets
-- this schema-owned procedure read the schema-owned Users table.
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[GetUserByOid]
    @EntraOid UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        [UserId],
        [Email],
        [InvitedUtc],
        [RedeemedUtc],
        [DeactivatedUtc],
        [CreatedUtc],
        CONVERT(NVARCHAR(36), [EntraOid]) AS [EntraOid]
    FROM [onboarding].[Users]
    WHERE [EntraOid] = @EntraOid;
END;
