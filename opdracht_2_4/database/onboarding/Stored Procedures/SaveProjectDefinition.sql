-- ---------------------------------------------------------------------------
-- Replace the Installation or Migration definition of a Project
-- (docs/projects-design.md §5, Stage 4). The API validates every value and passes
-- the full definition; @Type is the type the caller is saving, which must match
-- the Project's. Only the columns of that type are written (the CHECKs on Project
-- keep the others NULL). For an Installation the connectors are replaced as a
-- set from @ConnectorsJson:
--   [{"position":1,"source_system_id":3,"license_count":1,
--     "companies_to_extract":2,"content_pack_ids":[11,12]}, ...]
-- Same rules as UpdateProject: Draft is author-only (via VisibleProject); after
-- Draft only an Admin may edit, and the edit is audited atomically with
-- value-free @AuditDetail.
--
-- Returns one row (Outcome, ProjectId):
--   Ok, NotFound (missing or not visible), Forbidden (customer user),
--   Locked (non-Admin editing after Draft), WrongType (@Type is not the Project's)
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[SaveProjectDefinition]
    @ActorOid UNIQUEIDENTIFIER,
    @IsStaff BIT,
    @IsAdmin BIT,
    @ProjectId INT,
    @Type VARCHAR(12),
    @PreferredInstallationTypeId INT = NULL,
    @PreferredPowerBILicenseId INT = NULL,
    @EnvDevelopment BIT = NULL,
    @EnvTest BIT = NULL,
    @EnvAcceptance BIT = NULL,
    @EnvProduction BIT = NULL,
    @EnvironmentConnectionId INT = NULL,
    @EnvironmentConnectionOther NVARCHAR(500) = NULL,
    @AzureSubscriptionByUs BIT = NULL,
    @PowerBILicenseByUs BIT = NULL,
    @PowerBILicensesSold INT = NULL,
    @AzureCostsInformed BIT = NULL,
    @SignedSoftwareAgreement BIT = NULL,
    @TeamsChannelAdded BIT = NULL,
    @TeamsChannelUrl NVARCHAR(2048) = NULL,
    @ConnectorsJson NVARCHAR(MAX) = NULL,
    @MigrationTypeId INT = NULL,
    @MigrationInformation NVARCHAR(MAX) = NULL,
    @AuditDetail NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @State VARCHAR(12), @ProjectType VARCHAR(12);

    SELECT
        @State = p.[State],
        @ProjectType = p.[Type]
    FROM [onboarding].[Project] AS p
    INNER JOIN [onboarding].[VisibleProject](@ActorOid, @IsStaff) AS v ON p.[ProjectId] = v.[ProjectId]
    WHERE p.[ProjectId] = @ProjectId;

    IF @State IS NULL
        BEGIN
            SELECT
                N'NotFound' AS [Outcome],
                @ProjectId AS [ProjectId];
            RETURN;
        END;

    IF @IsStaff = 0
        BEGIN
            SELECT
                N'Forbidden' AS [Outcome],
                @ProjectId AS [ProjectId];
            RETURN;
        END;

    IF @State <> 'Draft' AND @IsAdmin = 0
        BEGIN
            SELECT
                N'Locked' AS [Outcome],
                @ProjectId AS [ProjectId];
            RETURN;
        END;

    IF @ProjectType <> @Type
        BEGIN
            SELECT
                N'WrongType' AS [Outcome],
                @ProjectId AS [ProjectId];
            RETURN;
        END;

    BEGIN TRANSACTION;

    IF @Type = 'Installation'
        BEGIN
            UPDATE [onboarding].[Project]
            SET
                [PreferredInstallationTypeId] = @PreferredInstallationTypeId,
                [PreferredPowerBILicenseId] = @PreferredPowerBILicenseId,
                [EnvDevelopment] = @EnvDevelopment,
                [EnvTest] = @EnvTest,
                [EnvAcceptance] = @EnvAcceptance,
                [EnvProduction] = @EnvProduction,
                [EnvironmentConnectionId] = @EnvironmentConnectionId,
                [EnvironmentConnectionOther] = @EnvironmentConnectionOther,
                [AzureSubscriptionByUs] = @AzureSubscriptionByUs,
                [PowerBILicenseByUs] = @PowerBILicenseByUs,
                [PowerBILicensesSold] = @PowerBILicensesSold,
                [AzureCostsInformed] = @AzureCostsInformed,
                [SignedSoftwareAgreement] = @SignedSoftwareAgreement,
                [TeamsChannelAdded] = @TeamsChannelAdded,
                [TeamsChannelUrl] = @TeamsChannelUrl,
                [UpdatedUtc] = SYSUTCDATETIME()
            WHERE [ProjectId] = @ProjectId;

            DELETE FROM [onboarding].[ProjectConnector]
            WHERE [ProjectId] = @ProjectId;

            INSERT INTO [onboarding].[ProjectConnector]
            ([ProjectId], [Position], [SourceSystemId], [LicenseCount], [CompaniesToExtract], [ContentPackIds])
            SELECT
                @ProjectId AS [ProjectId],
                [j].[Position],
                [j].[SourceSystemId],
                [j].[LicenseCount],
                [j].[CompaniesToExtract],
                COALESCE([j].[ContentPackIds], N'[]') AS [ContentPackIds]
            FROM
                OPENJSON (COALESCE(@ConnectorsJson, N'[]'))
                WITH (
                    [Position] TINYINT '$.position',
                    [SourceSystemId] INT '$.source_system_id',
                    [LicenseCount] TINYINT '$.license_count',
                    [CompaniesToExtract] INT '$.companies_to_extract',
                    [ContentPackIds] NVARCHAR(MAX) '$.content_pack_ids' AS JSON
                ) AS [j];
        END;
    ELSE
        BEGIN
            UPDATE [onboarding].[Project]
            SET
                [MigrationTypeId] = @MigrationTypeId,
                [MigrationInformation] = @MigrationInformation,
                [UpdatedUtc] = SYSUTCDATETIME()
            WHERE [ProjectId] = @ProjectId;
        END;

    IF @State <> 'Draft'
        EXEC [onboarding].[AppendAuditEvent]
            @Action = N'SaveProjectDefinition',
            @ActorOid = @ActorOid,
            @TargetType = N'Project',
            @TargetId = @ProjectId,
            @Detail = @AuditDetail;

    COMMIT TRANSACTION;

    SELECT
        N'Ok' AS [Outcome],
        @ProjectId AS [ProjectId];
END;
