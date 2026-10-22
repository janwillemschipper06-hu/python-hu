-- ---------------------------------------------------------------------------
-- Append one row to the append-only audit trail (security-design §12). This is
-- the ONLY write path to onboarding.AuditLog: there is deliberately no update or
-- delete procedure, and the app principal is denied direct table DML, so history
-- can be added but never rewritten.
--
-- @Detail carries VALUE-FREE metadata only (e.g. JSON identifiers/counts). Never
-- pass a secret value, token, or request body (security-design §11.3).
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[AppendAuditEvent]
    @Action NVARCHAR(100),
    @ActorOid UNIQUEIDENTIFIER = NULL,
    @TargetType NVARCHAR(100) = NULL,
    @TargetId NVARCHAR(200) = NULL,
    @Detail NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO [onboarding].[AuditLog]
    ([ActorOid], [Action], [TargetType], [TargetId], [Detail])
    VALUES
    (@ActorOid, @Action, @TargetType, @TargetId, @Detail);
END;
