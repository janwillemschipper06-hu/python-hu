-- ---------------------------------------------------------------------------
-- Definition procedures (Stage 4): SaveProjectDefinition, GetProjectDefinition,
-- ListProjectConnectors. Covers the Draft/author rule, the post-Draft Admin-only
-- lock with audit, customer-user access, the type match and the connector
-- replace-as-a-set behaviour. Any failed expectation THROWs; the whole run is
-- rolled back, so it leaves no data behind.
--
-- Run against a scratch database (e.g. LocalDB) that has the onboarding schema
-- deployed and a plain table standing in for the external [ext].[Customer]:
--   CREATE TABLE ext.Customer (CustomerConfigID INT, CustomerName NVARCHAR(255));
-- It is not part of the DACPAC build or of any deployment.
-- ---------------------------------------------------------------------------
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

DECLARE @admin UNIQUEIDENTIFIER = NEWID(), @pm UNIQUEIDENTIFIER = NEWID(), @cust UNIQUEIDENTIFIER = NEWID();
INSERT INTO [onboarding].[Users] ([EntraOid], [Email]) VALUES (@admin, N'admin@t'), (@pm, N'pm@t'), (@cust, N'cust@t');
INSERT INTO [ext].[Customer] ([CustomerConfigID], [CustomerName]) VALUES (900002, N'Contoso');

INSERT INTO [onboarding].[LookupOption] ([Kind], [Name], [Family])
VALUES ('SourceSystem', N'AX-test', 'AXFO'), ('SourceSystem', N'SQL-test', 'SQL');
INSERT INTO [onboarding].[LookupOption] ([Kind], [Name]) VALUES ('MigrationType', N'Mig-test');
DECLARE @ax INT = (
    SELECT [LookupOptionId] FROM [onboarding].[LookupOption]
    WHERE [Name] = N'AX-test'
);
DECLARE @sql INT = (
    SELECT [LookupOptionId] FROM [onboarding].[LookupOption]
    WHERE [Name] = N'SQL-test'
);
DECLARE @mig INT = (
    SELECT [LookupOptionId] FROM [onboarding].[LookupOption]
    WHERE [Name] = N'Mig-test'
);

DECLARE @r TABLE ([Outcome] NVARCHAR(30), [ProjectId] INT);
DECLARE @inst INT, @migration INT;

INSERT INTO @r EXEC [onboarding].[CreateProject]
    @ActorOid = @pm, @CustomerConfigID = 900002, @Type = 'Installation', @Name = N'Inst';
SELECT @inst = [ProjectId] FROM @r;
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[CreateProject]
    @ActorOid = @pm, @CustomerConfigID = 900002, @Type = 'Migration', @Name = N'Mig';
SELECT @migration = [ProjectId] FROM @r;

DECLARE @two NVARCHAR(MAX) = CONCAT(
    N'[{"position":1,"source_system_id":',
    @ax,
    N',"license_count":2,"companies_to_extract":3,"content_pack_ids":[11,12]},',
    N'{"position":2,"source_system_id":',
    @sql,
    N',"license_count":1,"companies_to_extract":null,"content_pack_ids":[]}]'
);

-- Author saves their own Draft: columns and two connectors, no audit.
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[SaveProjectDefinition]
    @ActorOid = @pm, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @inst, @Type = 'Installation',
    @EnvProduction = 1, @SignedSoftwareAgreement = 0, @ConnectorsJson = @two;
IF (SELECT [Outcome] FROM @r) <> N'Ok' THROW 51001, 'author saves own Draft', 1;
IF (
    SELECT COUNT(*) FROM [onboarding].[ProjectConnector]
    WHERE [ProjectId] = @inst
) <> 2
    THROW 51002, 'two connectors expected', 1;
IF NOT EXISTS (
    SELECT 1 FROM [onboarding].[ProjectConnector]
    WHERE [ProjectId] = @inst AND [Position] = 1 AND [CompaniesToExtract] = 3 AND [ContentPackIds] = N'[11,12]'
) THROW 51003, 'connector 1 content not saved', 1;
IF NOT EXISTS (
    SELECT 1 FROM [onboarding].[ProjectConnector]
    WHERE [ProjectId] = @inst AND [Position] = 2 AND [CompaniesToExtract] IS NULL AND [ContentPackIds] = N'[]'
) THROW 51004, 'connector 2 content not saved', 1;
IF EXISTS (
    SELECT 1 FROM [onboarding].[AuditLog]
    WHERE [Action] = N'SaveProjectDefinition'
) THROW 51005, 'Draft saves must not be audited', 1;

-- Read back through the get procedures.
DECLARE @g TABLE (
    [ProjectId] INT, [Type] VARCHAR(12), [PreferredInstallationTypeId] INT, [PreferredPowerBILicenseId] INT,
    [EnvDevelopment] BIT, [EnvTest] BIT, [EnvAcceptance] BIT, [EnvProduction] BIT, [EnvironmentConnectionId] INT,
    [EnvironmentConnectionOther] NVARCHAR(500), [AzureSubscriptionByUs] BIT, [PowerBILicenseByUs] BIT,
    [PowerBILicensesSold] INT, [AzureCostsInformed] BIT, [SignedSoftwareAgreement] BIT, [TeamsChannelAdded] BIT,
    [TeamsChannelUrl] NVARCHAR(2048), [MigrationTypeId] INT, [MigrationInformation] NVARCHAR(MAX)
);
INSERT INTO @g EXEC [onboarding].[GetProjectDefinition] @ActorOid = @pm, @IsStaff = 1, @ProjectId = @inst;
IF (
    SELECT COUNT(*) FROM @g
    WHERE [EnvProduction] = 1 AND [SignedSoftwareAgreement] = 0
) <> 1
    THROW 51007, 'GetProjectDefinition must return the saved columns', 1;

DELETE FROM @g;
INSERT INTO @g EXEC [onboarding].[GetProjectDefinition] @ActorOid = @admin, @IsStaff = 1, @ProjectId = @inst;
IF EXISTS (SELECT 1 FROM @g) THROW 51008, 'another author''s Draft definition must be hidden', 1;

DECLARE
    @c TABLE ([SourceSystemId] INT, [LicenseCount] TINYINT, [CompaniesToExtract] INT, [ContentPackIds] NVARCHAR(500));
INSERT INTO @c EXEC [onboarding].[ListProjectConnectors] @ActorOid = @pm, @IsStaff = 1, @ProjectId = @inst;
IF (SELECT COUNT(*) FROM @c) <> 2 THROW 51009, 'ListProjectConnectors count', 1;
IF (SELECT TOP 1 [SourceSystemId] FROM @c) <> @ax THROW 51010, 'connectors must come back in Position order', 1;

-- Another author cannot touch the Draft; a customer user is hidden from it too.
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[SaveProjectDefinition]
    @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 1, @ProjectId = @inst, @Type = 'Installation';
IF (SELECT [Outcome] FROM @r) <> N'NotFound' THROW 51011, 'another author''s Draft is NotFound', 1;

-- Replace as a set: saving one connector removes the others.
DECLARE @one NVARCHAR(MAX) = CONCAT(
    N'[{"position":1,"source_system_id":', @ax, N',"license_count":5,"content_pack_ids":[]}]'
);
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[SaveProjectDefinition]
    @ActorOid = @pm, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @inst, @Type = 'Installation',
    @ConnectorsJson = @one;
IF (
    SELECT COUNT(*) FROM [onboarding].[ProjectConnector]
    WHERE [ProjectId] = @inst
) <> 1
    THROW 51012, 'connectors are replaced as a set', 1;
IF (
    SELECT [EnvProduction] FROM [onboarding].[Project]
    WHERE [ProjectId] = @inst
) IS NOT NULL
    THROW 51013, 'a full replace clears omitted columns', 1;

-- Type must match.
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[SaveProjectDefinition]
    @ActorOid = @pm, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @inst, @Type = 'Migration', @MigrationTypeId = @mig;
IF (SELECT [Outcome] FROM @r) <> N'WrongType' THROW 51014, 'wrong type rejected', 1;

-- Migration saves its own two columns.
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[SaveProjectDefinition]
    @ActorOid = @pm, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @migration, @Type = 'Migration',
    @MigrationTypeId = @mig, @MigrationInformation = N'Move it';
IF (SELECT [Outcome] FROM @r) <> N'Ok' THROW 51015, 'migration saves', 1;
IF NOT EXISTS (
    SELECT 1 FROM [onboarding].[Project]
    WHERE [ProjectId] = @migration AND [MigrationTypeId] = @mig AND [MigrationInformation] = N'Move it'
) THROW 51016, 'migration columns not saved', 1;

-- After Draft: PM is locked out, Admin edits are audited, customers cannot write.
UPDATE [onboarding].[Project] SET [State] = 'Approved'
WHERE [ProjectId] IN (@inst, @migration);
INSERT INTO [onboarding].[ProjectPerson] ([ProjectId], [Name], [Email], [UserId])
VALUES (@inst, N'C', N'cust@t', (
    SELECT [UserId] FROM [onboarding].[Users]
    WHERE [EntraOid] = @cust
));

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[SaveProjectDefinition]
    @ActorOid = @pm, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @inst, @Type = 'Installation', @EnvTest = 1;
IF (SELECT [Outcome] FROM @r) <> N'Locked' THROW 51017, 'PM locked after Draft', 1;
IF (
    SELECT [EnvTest] FROM [onboarding].[Project]
    WHERE [ProjectId] = @inst
) IS NOT NULL
    THROW 51018, 'a locked save must not change data', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[SaveProjectDefinition]
    @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 1, @ProjectId = @inst, @Type = 'Installation',
    @EnvTest = 1, @ConnectorsJson = @one, @AuditDetail = N'{"fields":["env_test"]}';
IF (SELECT [Outcome] FROM @r) <> N'Ok' THROW 51019, 'Admin edits after Draft', 1;
IF NOT EXISTS (
    SELECT 1 FROM [onboarding].[AuditLog]
    WHERE [Action] = N'SaveProjectDefinition' AND [TargetId] = CAST(@inst AS NVARCHAR(200)) AND [ActorOid] = @admin
) THROW 51020, 'Admin edit after Draft must be audited', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[SaveProjectDefinition]
    @ActorOid = @cust, @IsStaff = 0, @IsAdmin = 0, @ProjectId = @inst, @Type = 'Installation';
IF (SELECT [Outcome] FROM @r) <> N'Forbidden' THROW 51021, 'customer user must not edit', 1;

-- The assigned customer user can read the definition and connectors.
DELETE FROM @g;
INSERT INTO @g EXEC [onboarding].[GetProjectDefinition] @ActorOid = @cust, @IsStaff = 0, @ProjectId = @inst;
IF (SELECT COUNT(*) FROM @g) <> 1 THROW 51022, 'assigned customer reads the definition', 1;
DELETE FROM @c;
INSERT INTO @c EXEC [onboarding].[ListProjectConnectors] @ActorOid = @cust, @IsStaff = 0, @ProjectId = @inst;
IF (SELECT COUNT(*) FROM @c) <> 1 THROW 51023, 'assigned customer reads the connectors', 1;
DELETE FROM @g;
INSERT INTO @g EXEC [onboarding].[GetProjectDefinition] @ActorOid = @cust, @IsStaff = 0, @ProjectId = @migration;
IF EXISTS (SELECT 1 FROM @g) THROW 51024, 'unassigned Project definition stays hidden', 1;

ROLLBACK TRANSACTION;
PRINT 'project-definition-tests: all passed';
