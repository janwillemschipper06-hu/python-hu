-- ---------------------------------------------------------------------------
-- A customer contact on a Project. UserId stays NULL until the person is invited
-- (Stage 6). A person with a UserId is a customer user of this Project: this
-- table is the join that scopes customer-user access inside the stored
-- procedures (docs/adr/0002, 0013). Email is unique per Project. The three
-- label flags are informational (a person may hold several); submit validation
-- needs at least one person per flag.
-- ---------------------------------------------------------------------------
CREATE TABLE [onboarding].[ProjectPerson]
(
    [ProjectPersonId] INT IDENTITY (1, 1) NOT NULL,
    [ProjectId] INT NOT NULL,
    [Name] NVARCHAR(200) NOT NULL,
    [Email] NVARCHAR(256) NOT NULL,
    [UserId] INT NULL,
    [IsCustomerProjectManager] BIT NOT NULL CONSTRAINT [DF_ProjectPerson_IsCustomerProjectManager] DEFAULT (0),
    [IsFunctional] BIT NOT NULL CONSTRAINT [DF_ProjectPerson_IsFunctional] DEFAULT (0),
    [IsTechnical] BIT NOT NULL CONSTRAINT [DF_ProjectPerson_IsTechnical] DEFAULT (0),
    [CreatedUtc] DATETIME2(7) NOT NULL CONSTRAINT [DF_ProjectPerson_CreatedUtc] DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [PK_ProjectPerson] PRIMARY KEY CLUSTERED ([ProjectPersonId] ASC),
    CONSTRAINT [UQ_ProjectPerson_Project_Email] UNIQUE ([ProjectId] ASC, [Email] ASC),
    CONSTRAINT [FK_ProjectPerson_Project] FOREIGN KEY ([ProjectId])
    REFERENCES [onboarding].[Project] ([ProjectId]) ON DELETE CASCADE,
    CONSTRAINT [FK_ProjectPerson_Users] FOREIGN KEY ([UserId])
    REFERENCES [onboarding].[Users] ([UserId])
);
GO

CREATE NONCLUSTERED INDEX [IX_ProjectPerson_UserId]
    ON [onboarding].[ProjectPerson] ([UserId] ASC)
    WHERE [UserId] IS NOT NULL;
