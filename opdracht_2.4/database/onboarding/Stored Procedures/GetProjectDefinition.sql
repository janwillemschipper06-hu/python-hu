-- ---------------------------------------------------------------------------
-- Read the Installation/Migration definition columns of one Project the caller
-- may see (VisibleProject). Zero rows means "not found or not visible". The
-- columns of the other type are NULL.
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[GetProjectDefinition]
    @ActorOid UNIQUEIDENTIFIER,
    @IsStaff BIT,
    @ProjectId INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        p.[ProjectId],
        p.[Type],
        p.[PreferredInstallationTypeId],
        p.[PreferredPowerBILicenseId],
        p.[EnvDevelopment],
        p.[EnvTest],
        p.[EnvAcceptance],
        p.[EnvProduction],
        p.[EnvironmentConnectionId],
        p.[EnvironmentConnectionOther],
        p.[AzureSubscriptionByUs],
        p.[PowerBILicenseByUs],
        p.[PowerBILicensesSold],
        p.[AzureCostsInformed],
        p.[SignedSoftwareAgreement],
        p.[TeamsChannelAdded],
        p.[TeamsChannelUrl],
        p.[MigrationTypeId],
        p.[MigrationInformation]
    FROM [onboarding].[Project] AS p
    INNER JOIN [onboarding].[VisibleProject](@ActorOid, @IsStaff) AS v ON p.[ProjectId] = v.[ProjectId]
    WHERE p.[ProjectId] = @ProjectId;
END;
