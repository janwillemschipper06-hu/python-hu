-- ---------------------------------------------------------------------------
-- The connectors (1-3) of one Installation Project the caller may see
-- (VisibleProject), in Position order. Zero rows when none or not visible.
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[ListProjectConnectors]
    @ActorOid UNIQUEIDENTIFIER,
    @IsStaff BIT,
    @ProjectId INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        c.[SourceSystemId],
        c.[LicenseCount],
        c.[CompaniesToExtract],
        c.[ContentPackIds]
    FROM [onboarding].[ProjectConnector] AS c
    INNER JOIN [onboarding].[VisibleProject](@ActorOid, @IsStaff) AS v ON c.[ProjectId] = v.[ProjectId]
    WHERE c.[ProjectId] = @ProjectId
    ORDER BY c.[Position];
END;
