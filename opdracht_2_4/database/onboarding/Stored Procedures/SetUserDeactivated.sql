-- ---------------------------------------------------------------------------
-- Set or clear a user's soft-deactivation stamp, matched by Entra oid (Stage 6;
-- authentication-and-access §6). Pass a timestamp to deactivate, or NULL to
-- reactivate. This only records the lifecycle state in the mirror table — the
-- actual loss of access comes from removing the app-role assignment (and CAE at
-- sign-in), never from this flag, which
-- is never consulted for authorization.
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[SetUserDeactivated]
    @EntraOid UNIQUEIDENTIFIER,
    @DeactivatedUtc DATETIME2(7) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE [onboarding].[Users]
    SET [DeactivatedUtc] = @DeactivatedUtc
    WHERE [EntraOid] = @EntraOid;
END;
