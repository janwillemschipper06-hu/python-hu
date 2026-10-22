-- ---------------------------------------------------------------------------
-- Record a user's first successful sign-in (invitation redemption), matched by
-- Entra oid. Sets RedeemedUtc once and never overwrites it, so repeated sign-ins
-- are no-ops. An unknown oid (e.g. a user not provisioned through the invite
-- flow) is ignored. Lifecycle bookkeeping only — never consulted for
-- authorization (docs/adr/0012).
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[MarkUserRedeemed]
    @EntraOid UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE [onboarding].[Users]
    SET [RedeemedUtc] = SYSUTCDATETIME()
    WHERE
        [EntraOid] = @EntraOid
        AND [RedeemedUtc] IS NULL;
END;
