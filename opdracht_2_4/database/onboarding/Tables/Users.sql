-- ---------------------------------------------------------------------------
-- One row per invited portal identity, keyed by the Entra object id (oid).
--
-- A user's role is NOT stored here: it lives only in Entra as the user's app-role
-- assignment on the API app and is read from the signed token (docs/adr/0012).
-- Invited/redeemed timestamps track the invite lifecycle. Reached only
-- through the onboarding stored procedures (docs/adr/0002, docs/adr/0008).
-- ---------------------------------------------------------------------------
CREATE TABLE [onboarding].[Users]
(
    [UserId] INT IDENTITY (1, 1) NOT NULL,
    [EntraOid] UNIQUEIDENTIFIER NOT NULL,
    [Email] NVARCHAR(256) NOT NULL,
    [InvitedUtc] DATETIME2(7) NULL,
    [RedeemedUtc] DATETIME2(7) NULL,
    -- Soft-deactivation stamp (Stage 6): set when an admin deactivates the user
    -- (all scope links and the `Admin` app-role assignment are removed, but the
    -- Entra guest object and this row are retained for audit — authentication-
    -- and-access §6). NULL means active; a timestamp means deactivated. Cleared
    -- again on reactivation. Never used for authorization — the live token's
    -- role/scope is the source of truth.
    [DeactivatedUtc] DATETIME2(7) NULL,
    [CreatedUtc] DATETIME2(7) NOT NULL CONSTRAINT [DF_Users_CreatedUtc] DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [PK_Users] PRIMARY KEY CLUSTERED ([UserId] ASC),
    CONSTRAINT [UQ_Users_EntraOid] UNIQUE ([EntraOid] ASC)
);
