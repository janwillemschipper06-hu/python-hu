-- ---------------------------------------------------------------------------
-- List every portal user for the admin lifecycle view (Stage 6; authentication-
-- and-access §6/§8). Returns one row per onboarding.Users row with the invite
-- lifecycle stamps.
--
-- EntraOid is CONVERTed to text so the app receives a stable GUID string
-- regardless of the ODBC driver's uniqueidentifier representation. Role is not
-- stored here (Entra is the only source, docs/adr/0012). EXECUTE-only
-- access via ownership chaining (docs/adr/0002, docs/adr/0008).
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[ListUsers]
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        [u].[Email],
        [u].[InvitedUtc],
        [u].[RedeemedUtc],
        [u].[DeactivatedUtc],
        [u].[CreatedUtc],
        CONVERT(NVARCHAR(36), [u].[EntraOid]) AS [EntraOid]
    FROM [onboarding].[Users] AS [u]
    ORDER BY [u].[Email];
END;
