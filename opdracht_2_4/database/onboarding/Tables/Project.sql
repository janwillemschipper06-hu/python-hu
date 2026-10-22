-- ---------------------------------------------------------------------------
-- A Project is one installation or migration for a customer (docs/adr/0013,
-- docs/projects-design.md §5). It replaces Customer as the isolation/assignment
-- scope. CustomerConfigID points at the read-only external ext.Customer, so there
-- is deliberately no foreign key to it.
--
-- Like the legacy Installation/Migration tables, the type-specific definition
-- lives on the same row: the installation columns are used only when
-- Type = 'Installation', the migration columns only when Type = 'Migration'
-- (enforced by the CHECK constraints below). Everything except the identity
-- columns is nullable while the Project is a Draft; completeness is enforced by
-- the submit validation (Stage 5). The lookup columns reference LookupOption;
-- that the option has the right Kind is validated by the API.
-- ---------------------------------------------------------------------------
CREATE TABLE [onboarding].[Project]
(
    [ProjectId] INT IDENTITY (1, 1) NOT NULL,
    [CustomerConfigID] INT NOT NULL,
    [Type] VARCHAR(12) NOT NULL,
    [Name] NVARCHAR(200) NOT NULL,
    [State] VARCHAR(12) NOT NULL CONSTRAINT [DF_Project_State] DEFAULT ('Draft'),
    [PreviousState] VARCHAR(12) NULL,
    [RejectionReason] NVARCHAR(1000) NULL,
    [RequesterUserId] INT NOT NULL,
    [CreatedByUserId] INT NOT NULL,
    [DepartmentId] INT NULL,
    [CustomerType] VARCHAR(10) NULL,
    [Deadline] DATE NULL,
    [Hours] INT NULL,
    [RequestNotes] NVARCHAR(MAX) NULL,
    [ConsultantUserId] INT NULL,
    [RequestTicketId] BIGINT NULL,
    [CommunicationTicketId] BIGINT NULL,

    -- Installation definition
    [PreferredInstallationTypeId] INT NULL,
    [PreferredPowerBILicenseId] INT NULL,
    [EnvDevelopment] BIT NULL,
    [EnvTest] BIT NULL,
    [EnvAcceptance] BIT NULL,
    [EnvProduction] BIT NULL,
    [EnvironmentConnectionId] INT NULL,
    [EnvironmentConnectionOther] NVARCHAR(500) NULL,
    [AzureSubscriptionByUs] BIT NULL,
    [PowerBILicenseByUs] BIT NULL,
    [PowerBILicensesSold] INT NULL,
    [AzureCostsInformed] BIT NULL,
    [SignedSoftwareAgreement] BIT NULL,
    [TeamsChannelAdded] BIT NULL,
    [TeamsChannelUrl] NVARCHAR(2048) NULL,

    -- Migration definition
    [MigrationTypeId] INT NULL,
    [MigrationInformation] NVARCHAR(MAX) NULL,

    [CreatedUtc] DATETIME2(7) NOT NULL CONSTRAINT [DF_Project_CreatedUtc] DEFAULT (SYSUTCDATETIME()),
    [UpdatedUtc] DATETIME2(7) NOT NULL CONSTRAINT [DF_Project_UpdatedUtc] DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [PK_Project] PRIMARY KEY CLUSTERED ([ProjectId] ASC),
    CONSTRAINT [CK_Project_Type] CHECK ([Type] IN ('Installation', 'Migration')),
    CONSTRAINT [CK_Project_State] CHECK (
        [State] IN ('Draft', 'Requested', 'Approved', 'InProgress', 'Ready', 'OnHold', 'Cancelled')
    ),
    CONSTRAINT [CK_Project_PreviousState] CHECK (
        [PreviousState] IS NULL OR [PreviousState] IN ('Approved', 'InProgress', 'Ready')
    ),
    CONSTRAINT [CK_Project_CustomerType] CHECK ([CustomerType] IS NULL OR [CustomerType] IN ('Direct', 'Indirect')),
    CONSTRAINT [CK_Project_Hours] CHECK ([Hours] IS NULL OR [Hours] >= 0),
    CONSTRAINT [CK_Project_LicensesSold] CHECK ([PowerBILicensesSold] IS NULL OR [PowerBILicensesSold] >= 0),
    CONSTRAINT [CK_Project_MigrationColumns] CHECK (
        [Type] = 'Migration' OR ([MigrationTypeId] IS NULL AND [MigrationInformation] IS NULL)
    ),
    CONSTRAINT [CK_Project_InstallationColumns] CHECK (
        [Type] = 'Installation' OR (
            [PreferredInstallationTypeId] IS NULL AND [PreferredPowerBILicenseId] IS NULL
            AND [EnvDevelopment] IS NULL AND [EnvTest] IS NULL AND [EnvAcceptance] IS NULL AND [EnvProduction] IS NULL
            AND [EnvironmentConnectionId] IS NULL AND [EnvironmentConnectionOther] IS NULL
            AND [AzureSubscriptionByUs] IS NULL AND [PowerBILicenseByUs] IS NULL AND [PowerBILicensesSold] IS NULL
            AND [AzureCostsInformed] IS NULL AND [SignedSoftwareAgreement] IS NULL
            AND [TeamsChannelAdded] IS NULL AND [TeamsChannelUrl] IS NULL
        )
    ),
    CONSTRAINT [FK_Project_Requester] FOREIGN KEY ([RequesterUserId]) REFERENCES [onboarding].[Users] ([UserId]),
    CONSTRAINT [FK_Project_CreatedBy] FOREIGN KEY ([CreatedByUserId]) REFERENCES [onboarding].[Users] ([UserId]),
    CONSTRAINT [FK_Project_Consultant] FOREIGN KEY ([ConsultantUserId]) REFERENCES [onboarding].[Users] ([UserId]),
    CONSTRAINT [FK_Project_Department] FOREIGN KEY ([DepartmentId])
    REFERENCES [onboarding].[LookupOption] ([LookupOptionId]),
    CONSTRAINT [FK_Project_InstallationType] FOREIGN KEY ([PreferredInstallationTypeId])
    REFERENCES [onboarding].[LookupOption] ([LookupOptionId]),
    CONSTRAINT [FK_Project_PowerBILicense] FOREIGN KEY ([PreferredPowerBILicenseId])
    REFERENCES [onboarding].[LookupOption] ([LookupOptionId]),
    CONSTRAINT [FK_Project_EnvironmentConnection] FOREIGN KEY ([EnvironmentConnectionId])
    REFERENCES [onboarding].[LookupOption] ([LookupOptionId]),
    CONSTRAINT [FK_Project_MigrationType] FOREIGN KEY ([MigrationTypeId])
    REFERENCES [onboarding].[LookupOption] ([LookupOptionId])
);
GO

CREATE NONCLUSTERED INDEX [IX_Project_CustomerConfigID] ON [onboarding].[Project] ([CustomerConfigID] ASC);
GO

CREATE NONCLUSTERED INDEX [IX_Project_State] ON [onboarding].[Project] ([State] ASC);
