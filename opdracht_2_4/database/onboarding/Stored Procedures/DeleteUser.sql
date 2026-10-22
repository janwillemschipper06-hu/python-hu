-- ---------------------------------------------------------------------------
-- Hard-delete a portal user's application records, matched by Entra oid (Stage 6
-- delete / revoke-pending; authentication-and-access §6). Removes the Users
-- row. Idempotent: a no-op when the oid is unknown.
--
-- This removes only the application-side mirror. The authoritative identity — the
-- Entra B2B guest object — is deleted separately by the backend via Microsoft
-- Graph; that, plus CAE, is what actually revokes access. The append-only
-- AuditLog keeps the oid as free text (no FK), so the deletion stays audited.
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[DeleteUser]
    @EntraOid UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE
        @UserId INT
        = (
            SELECT [UserId] FROM [onboarding].[Users]
            WHERE [EntraOid] = @EntraOid
        );

    IF @UserId IS NULL
        RETURN;

    DELETE FROM [onboarding].[Users]
    WHERE [UserId] = @UserId;
END;
