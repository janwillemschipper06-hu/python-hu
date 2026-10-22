-- ---------------------------------------------------------------------------
-- Append-only audit trail (authentication-and-access §9; security-design §12).
--
-- Rows are written ONLY through onboarding.AppendAuditEvent (insert); there is
-- deliberately no update/delete procedure, and the app principal is never given
-- direct table DML (create-sql-user-app.sql DENYs UPDATE/DELETE as defence in
-- depth), so the app can append but never rewrite or tombstone history.
--
-- Detail holds VALUE-FREE metadata only (e.g. JSON identifiers/counts). No secret
-- value, token, or request body is ever written here (security-design §11.3).
-- ---------------------------------------------------------------------------
CREATE TABLE [onboarding].[AuditLog]
(
    [AuditId] BIGINT IDENTITY (1, 1) NOT NULL,
    [EventUtc] DATETIME2(7) NOT NULL CONSTRAINT [DF_AuditLog_EventUtc] DEFAULT (SYSUTCDATETIME()),
    [ActorOid] UNIQUEIDENTIFIER NULL,
    [Action] NVARCHAR(100) NOT NULL,
    [TargetType] NVARCHAR(100) NULL,
    [TargetId] NVARCHAR(200) NULL,
    [Detail] NVARCHAR(MAX) NULL,
    CONSTRAINT [PK_AuditLog] PRIMARY KEY CLUSTERED ([AuditId] ASC)
);
