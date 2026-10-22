-- ---------------------------------------------------------------------------
-- A source-system connector of an Installation Project: 1-3 per Project
-- (Position 1-3; "at least one" is enforced at submit). CompaniesToExtract
-- applies to the AXFO and NAVBC families only. ContentPackIds is a JSON array of
-- LookupOption ids (e.g. [12,15]); the API validates that they are packs of the
-- source system's family.
-- ---------------------------------------------------------------------------
CREATE TABLE [onboarding].[ProjectConnector]
(
    [ProjectConnectorId] INT IDENTITY (1, 1) NOT NULL,
    [ProjectId] INT NOT NULL,
    [Position] TINYINT NOT NULL,
    [SourceSystemId] INT NOT NULL,
    [LicenseCount] TINYINT NOT NULL,
    [CompaniesToExtract] INT NULL,
    [ContentPackIds] NVARCHAR(500) NOT NULL CONSTRAINT [DF_ProjectConnector_ContentPackIds] DEFAULT ('[]'),
    CONSTRAINT [PK_ProjectConnector] PRIMARY KEY CLUSTERED ([ProjectConnectorId] ASC),
    CONSTRAINT [UQ_ProjectConnector_Project_Position] UNIQUE ([ProjectId] ASC, [Position] ASC),
    CONSTRAINT [CK_ProjectConnector_Position] CHECK ([Position] BETWEEN 1 AND 3),
    CONSTRAINT [CK_ProjectConnector_LicenseCount] CHECK ([LicenseCount] BETWEEN 1 AND 5),
    CONSTRAINT [CK_ProjectConnector_Companies] CHECK ([CompaniesToExtract] IS NULL OR [CompaniesToExtract] >= 1),
    CONSTRAINT [CK_ProjectConnector_ContentPackIds] CHECK (ISJSON([ContentPackIds]) = 1),
    CONSTRAINT [FK_ProjectConnector_Project] FOREIGN KEY ([ProjectId])
    REFERENCES [onboarding].[Project] ([ProjectId]) ON DELETE CASCADE,
    CONSTRAINT [FK_ProjectConnector_SourceSystem] FOREIGN KEY ([SourceSystemId])
    REFERENCES [onboarding].[LookupOption] ([LookupOptionId])
);
