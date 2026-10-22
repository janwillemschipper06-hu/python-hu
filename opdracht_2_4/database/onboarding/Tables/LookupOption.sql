-- ---------------------------------------------------------------------------
-- One row for every admin-managed dropdown option on a Project
-- (docs/projects-design.md §5). [Kind] says which dropdown the option belongs to,
-- so adding a new option or even a new dropdown needs no schema change. Options
-- are deactivated (IsActive), never deleted, so existing Projects keep their
-- reference. Whether an option suits a given Kind is validated by the API.
--
--   Family        SourceSystem and ContentPack: AXFO, NAVBC, CE or SQL. The family
--                 decides which content-pack questions apply to a connector.
--   PackKind      ContentPack only: Kickstart, Additional or Isv.
--   ExcludedSourceSystemId
--                 ContentPack only: not available for that source system
--                 (legacy "9A Advanced Manufacturing (Not available for AX)").
--   AllowsFreeText
--                 EnvironmentConnection only: the legacy "Other" option, which
--                 requires a free-text description.
-- ---------------------------------------------------------------------------
CREATE TABLE [onboarding].[LookupOption]
(
    [LookupOptionId] INT IDENTITY (1, 1) NOT NULL,
    [Kind] VARCHAR(30) NOT NULL,
    [Name] NVARCHAR(200) NOT NULL,
    [Family] VARCHAR(10) NULL,
    [PackKind] VARCHAR(10) NULL,
    [ExcludedSourceSystemId] INT NULL,
    [AllowsFreeText] BIT NOT NULL CONSTRAINT [DF_LookupOption_AllowsFreeText] DEFAULT (0),
    [SortOrder] INT NOT NULL CONSTRAINT [DF_LookupOption_SortOrder] DEFAULT (0),
    [IsActive] BIT NOT NULL CONSTRAINT [DF_LookupOption_IsActive] DEFAULT (1),
    CONSTRAINT [PK_LookupOption] PRIMARY KEY CLUSTERED ([LookupOptionId] ASC),
    CONSTRAINT [UQ_LookupOption_Kind_Name_Family] UNIQUE ([Kind] ASC, [Name] ASC, [Family] ASC),
    CONSTRAINT [CK_LookupOption_Kind] CHECK (
        [Kind] IN (
            'Department', 'SourceSystem', 'ContentPack', 'InstallationType',
            'PowerBILicense', 'EnvironmentConnection', 'MigrationType'
        )
    ),
    CONSTRAINT [CK_LookupOption_Family] CHECK ([Family] IS NULL OR [Family] IN ('AXFO', 'NAVBC', 'CE', 'SQL')),
    CONSTRAINT [CK_LookupOption_PackKind] CHECK (
        [PackKind] IS NULL OR [PackKind] IN ('Kickstart', 'Additional', 'Isv')
    ),
    CONSTRAINT [FK_LookupOption_ExcludedSourceSystem] FOREIGN KEY ([ExcludedSourceSystemId])
    REFERENCES [onboarding].[LookupOption] ([LookupOptionId])
);
