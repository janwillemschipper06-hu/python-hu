-- ---------------------------------------------------------------------------
-- Insert or update a portal user, keyed by Entra oid. Used by provisioning
-- (Stage 5 invite) and at first sign-in (redemption). Email is overwritten with the
-- latest known value; the invited/redeemed timestamps
-- are only advanced when a non-NULL value is supplied (COALESCE preserves the
-- existing stamp), so setting RedeemedUtc at sign-in never clears InvitedUtc.
--
-- Returns the resulting row so the caller gets the surrogate UserId. Role is not
-- stored here; Entra is the only source of truth (docs/adr/0012).
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[UpsertUser]
    @EntraOid UNIQUEIDENTIFIER,
    @Email NVARCHAR(256),
    @InvitedUtc DATETIME2(7) = NULL,
    @RedeemedUtc DATETIME2(7) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    IF
        EXISTS (
            SELECT 1 FROM [onboarding].[Users]
            WHERE [EntraOid] = @EntraOid
        )
        UPDATE [onboarding].[Users]
        SET
            [Email] = @Email,
            [InvitedUtc] = COALESCE(@InvitedUtc, [InvitedUtc]),
            [RedeemedUtc] = COALESCE(@RedeemedUtc, [RedeemedUtc])
        WHERE [EntraOid] = @EntraOid;
    ELSE
        INSERT INTO [onboarding].[Users]
        ([EntraOid], [Email], [InvitedUtc], [RedeemedUtc])
        VALUES
        (@EntraOid, @Email, @InvitedUtc, @RedeemedUtc);

    SELECT
        [UserId],
        [EntraOid],
        [Email],
        [InvitedUtc],
        [RedeemedUtc],
        [CreatedUtc]
    FROM [onboarding].[Users]
    WHERE [EntraOid] = @EntraOid;
END;
