-- ---------------------------------------------------------------------------
-- Visibility / Draft / lock matrix for the Project procedures (Stage 3).
-- Roles x states are exercised against VisibleProject, ListProjects,
-- UpdateProject, DeleteProject and CreateProject. Any failed expectation THROWs;
-- the whole run is rolled back, so it leaves no data behind.
--
-- Run against a scratch database (e.g. LocalDB) that has the onboarding schema
-- deployed and a plain table standing in for the external [ext].[Customer]:
--   CREATE TABLE ext.Customer (CustomerConfigID INT, CustomerName NVARCHAR(255));
-- It is not part of the DACPAC build or of any deployment.
-- ---------------------------------------------------------------------------
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

DECLARE @admin UNIQUEIDENTIFIER = NEWID(), @pm UNIQUEIDENTIFIER = NEWID();
DECLARE @cust UNIQUEIDENTIFIER = NEWID(), @other UNIQUEIDENTIFIER = NEWID(), @gone UNIQUEIDENTIFIER = NEWID();

INSERT INTO [onboarding].[Users] ([EntraOid], [Email]) VALUES (@admin, N'admin@t'), (@pm, N'pm@t');
INSERT INTO [onboarding].[Users] ([EntraOid], [Email]) VALUES (@cust, N'cust@t'), (@other, N'other@t');
INSERT INTO [onboarding].[Users] ([EntraOid], [Email], [DeactivatedUtc]) VALUES (@gone, N'gone@t', SYSUTCDATETIME());
DELETE FROM [ext].[Customer]
WHERE [CustomerConfigID] = 900001;
INSERT INTO [ext].[Customer] ([CustomerConfigID], [CustomerName]) VALUES (900001, N'Contoso');

DECLARE @states TABLE ([State] VARCHAR(12), [Id] INT);
DECLARE @r TABLE ([Outcome] NVARCHAR(30), [ProjectId] INT);
DECLARE @state VARCHAR(12), @id INT;

-- One Project per state, all authored by the admin, customer + deactivated user assigned.
DECLARE s CURSOR LOCAL FAST_FORWARD FOR
SELECT v
FROM (VALUES ('Draft'), ('Requested'), ('Approved'), ('InProgress'), ('Ready'), ('OnHold'), ('Cancelled')) AS t (v);
OPEN s;
FETCH NEXT FROM s INTO @state;
WHILE @@FETCH_STATUS = 0
    BEGIN
        DELETE FROM @r;
        INSERT INTO @r EXEC [onboarding].[CreateProject]
            @ActorOid = @admin, @CustomerConfigID = 900001, @Type = 'Installation', @Name = N'P',
            @Hours = 8, @RequestNotes = N'internal';
        IF (SELECT TOP 1 [Outcome] FROM @r) <> N'Ok' THROW 50001, 'create failed', 1;
        SELECT @id = [ProjectId] FROM @r;

        UPDATE [onboarding].[Project]
        SET
            [State] = @state,
            [PreviousState] = CASE WHEN @state = 'OnHold' THEN 'Approved' END
        WHERE [ProjectId] = @id;
        INSERT INTO [onboarding].[ProjectPerson] ([ProjectId], [Name], [Email], [UserId])
        VALUES (@id, N'C', N'cust@t', (
            SELECT [UserId] FROM [onboarding].[Users]
            WHERE [EntraOid] = @cust
        )),
        (@id, N'G', N'gone@t', (
            SELECT [UserId] FROM [onboarding].[Users]
            WHERE [EntraOid] = @gone
        ));
        INSERT INTO @states VALUES (@state, @id);
        FETCH NEXT FROM s INTO @state;
    END;
CLOSE s;
DEALLOCATE s;

-- ---- Visibility: every role x state ---------------------------------------
DECLARE @role VARCHAR(20), @oid UNIQUEIDENTIFIER, @staff BIT, @seen BIT, @want BIT, @msg NVARCHAR(200);
DECLARE m CURSOR LOCAL FAST_FORWARD FOR
SELECT
    r.[Role],
    r.[Oid],
    r.[IsStaff],
    s.[State],
    s.[Id]
FROM (
    VALUES
    ('admin-author', @admin, CAST(1 AS BIT)), ('pm-other', @pm, CAST(1 AS BIT)),
    ('customer', @cust, CAST(0 AS BIT)), ('unassigned', @other, CAST(0 AS BIT)),
    ('deactivated', @gone, CAST(0 AS BIT))
) AS r ([Role], [Oid], [IsStaff])
CROSS JOIN @states AS s;
OPEN m;
FETCH NEXT FROM m INTO @role, @oid, @staff, @state, @id;
WHILE @@FETCH_STATUS = 0
    BEGIN
        SET
            @seen = CASE WHEN EXISTS (
                SELECT 1 FROM [onboarding].[VisibleProject](@oid, @staff)
                WHERE [ProjectId] = @id
            ) THEN 1
            ELSE 0 END;
        SET @want = CASE
            WHEN @role = 'admin-author' THEN 1
            WHEN @role = 'pm-other' THEN CASE WHEN @state = 'Draft' THEN 0 ELSE 1 END
            WHEN
                @role = 'customer'
                THEN CASE WHEN @state IN ('Approved', 'InProgress', 'Ready', 'OnHold') THEN 1 ELSE 0 END
            ELSE 0
        END;
        IF @seen <> @want
            BEGIN
                SET @msg = CONCAT(N'visibility wrong: ', @role, N' / ', @state, N' saw=', @seen);
                THROW 50002, @msg, 1;
            END;
        FETCH NEXT FROM m INTO @role, @oid, @staff, @state, @id;
    END;
CLOSE m;
DEALLOCATE m;

-- ---- ListProjects mirrors the visibility rule -----------------------------
DECLARE @l TABLE (
    [ProjectId] INT,
    [CustomerConfigID] INT,
    [CustomerName] NVARCHAR(255),
    [Type] VARCHAR(12),
    [Name] NVARCHAR(200),
    [State] VARCHAR(12),
    [RequesterEmail] NVARCHAR(256),
    [CreatedByEmail] NVARCHAR(256),
    [DepartmentId] INT,
    [CustomerType] VARCHAR(10),
    [Deadline] DATE,
    [ConsultantEmail] NVARCHAR(256),
    [CreatedUtc] DATETIME2(7),
    [UpdatedUtc] DATETIME2(7),
    [RejectionReason] NVARCHAR(1000),
    [RequesterOid] NVARCHAR(36),
    [Hours] INT,
    [RequestNotes] NVARCHAR(MAX),
    [RequestTicketId] BIGINT,
    [CommunicationTicketId] BIGINT
);

INSERT INTO @l EXEC [onboarding].[ListProjects] @ActorOid = @pm, @IsStaff = 1;
IF
    (
        SELECT COUNT(*) FROM @l
        WHERE [ProjectId] IN (SELECT st.[Id] FROM @states AS st)
    ) <> 6
    THROW 50004, 'pm list should see 6 (no foreign Draft)', 1;
IF
    EXISTS (
        SELECT 1 FROM @l
        WHERE [Hours] IS NULL AND [ProjectId] IN (SELECT st.[Id] FROM @states AS st)
    )
    THROW 50007, 'staff lost internal fields', 1;
DELETE FROM @l;
INSERT INTO @l EXEC [onboarding].[ListProjects] @ActorOid = @cust, @IsStaff = 0;
IF
    (
        SELECT COUNT(*) FROM @l
        WHERE [ProjectId] IN (SELECT st.[Id] FROM @states AS st)
    ) <> 4
    THROW 50005, 'customer list should see 4', 1;
IF
    EXISTS (
        SELECT 1 FROM @l
        WHERE [Hours] IS NOT NULL OR [RequestNotes] IS NOT NULL
    )
    THROW 50006, 'customer sees internal fields', 1;

-- ---- UpdateProject: Draft author-only, post-Draft Admin-only + audit -----
DECLARE @draft INT = (
    SELECT [Id] FROM @states
    WHERE [State] = 'Draft'
);
DECLARE @requested INT = (
    SELECT [Id] FROM @states
    WHERE [State] = 'Requested'
);
DECLARE @approved INT = (
    SELECT [Id] FROM @states
    WHERE [State] = 'Approved'
);

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[UpdateProject]
    @ActorOid = @pm, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @draft,
    @RequesterOid = @admin, @CustomerConfigID = 900001, @Name = N'X';
IF (SELECT [Outcome] FROM @r) <> N'NotFound' THROW 50010, 'PM must not edit another author''s Draft', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[UpdateProject]
    @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 1, @ProjectId = @draft,
    @RequesterOid = @pm, @CustomerConfigID = 900001, @Name = N'Renamed';
IF (SELECT [Outcome] FROM @r) <> N'Ok' THROW 50011, 'author edits own Draft', 1;
IF
    (
        SELECT [Name] FROM [onboarding].[Project]
        WHERE [ProjectId] = @draft
    ) <> N'Renamed'
    THROW 50012, 'name not saved', 1;
IF
    (
        SELECT [RequesterUserId] FROM [onboarding].[Project]
        WHERE [ProjectId] = @draft
    )
    <> (
        SELECT [UserId] FROM [onboarding].[Users]
        WHERE [EntraOid] = @pm
    ) THROW 50013, 'requester not saved', 1;
IF
    EXISTS (
        SELECT 1 FROM [onboarding].[AuditLog]
        WHERE [Action] = N'UpdateProject' AND [TargetId] = CAST(@draft AS NVARCHAR(200))
    )
    THROW 50014, 'Draft edits must not be audited', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[UpdateProject]
    @ActorOid = @pm, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @requested,
    @RequesterOid = @admin, @CustomerConfigID = 900001, @Name = N'X';
IF (SELECT [Outcome] FROM @r) <> N'Locked' THROW 50015, 'PM must be locked out after Draft', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[UpdateProject]
    @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 1, @ProjectId = @requested,
    @RequesterOid = @admin, @CustomerConfigID = 900001, @Name = N'Admin edit', @AuditDetail = N'{"fields":["name"]}';
IF (SELECT [Outcome] FROM @r) <> N'Ok' THROW 50016, 'Admin edits after Draft', 1;
IF
    NOT EXISTS (
        SELECT 1 FROM [onboarding].[AuditLog]
        WHERE [Action] = N'UpdateProject' AND [TargetId] = CAST(@requested AS NVARCHAR(200)) AND [ActorOid] = @admin
    )
    THROW 50017, 'Admin edit after Draft must be audited', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[UpdateProject]
    @ActorOid = @cust, @IsStaff = 0, @IsAdmin = 0, @ProjectId = @approved,
    @RequesterOid = @admin, @CustomerConfigID = 900001, @Name = N'X';
IF (SELECT [Outcome] FROM @r) <> N'Forbidden' THROW 50018, 'customer user must not edit', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[UpdateProject]
    @ActorOid = @cust, @IsStaff = 0, @IsAdmin = 0, @ProjectId = @requested,
    @RequesterOid = @admin, @CustomerConfigID = 900001, @Name = N'X';
IF (SELECT [Outcome] FROM @r) <> N'NotFound' THROW 50019, 'hidden Project must read as NotFound', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[UpdateProject]
    @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 1, @ProjectId = @draft,
    @RequesterOid = @admin, @CustomerConfigID = 123, @Name = N'X';
IF (SELECT [Outcome] FROM @r) <> N'UnknownCustomer' THROW 50020, 'unknown customer rejected', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[UpdateProject]
    @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 1, @ProjectId = @draft,
    @RequesterOid = @gone, @CustomerConfigID = 900001, @Name = N'X';
IF (SELECT [Outcome] FROM @r) <> N'UnknownRequester' THROW 50021, 'deactivated requester rejected', 1;

-- ---- DeleteProject: Admin only, and only their own Draft ------------------
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[DeleteProject] @ActorOid = @pm, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @draft;
IF (SELECT [Outcome] FROM @r) <> N'NotFound' THROW 50030, 'PM must not delete another author''s Draft', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[DeleteProject]
    @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 1, @ProjectId = @requested;
IF (SELECT [Outcome] FROM @r) <> N'NotDraft' THROW 50031, 'non-Draft must not be deletable', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[DeleteProject] @ActorOid = @cust, @IsStaff = 0, @IsAdmin = 0, @ProjectId = @approved;
IF (SELECT [Outcome] FROM @r) <> N'Forbidden' THROW 50032, 'customer user must not delete', 1;

DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[DeleteProject] @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 0, @ProjectId = @draft;
IF (SELECT [Outcome] FROM @r) <> N'Forbidden' THROW 50036, 'non-Admin staff must not delete', 1;

INSERT INTO [onboarding].[ProjectPerson] ([ProjectId], [Name], [Email]) VALUES (@draft, N'D', N'd@t');
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[DeleteProject] @ActorOid = @admin, @IsStaff = 1, @IsAdmin = 1, @ProjectId = @draft;
IF (SELECT [Outcome] FROM @r) <> N'Ok' THROW 50033, 'author deletes own Draft', 1;
IF EXISTS (
    SELECT 1 FROM [onboarding].[Project]
    WHERE [ProjectId] = @draft
) THROW 50034, 'Draft not deleted', 1;
IF EXISTS (
    SELECT 1 FROM [onboarding].[ProjectPerson]
    WHERE [ProjectId] = @draft
) THROW 50035, 'people must cascade', 1;

-- ---- CreateProject guards -------------------------------------------------
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[CreateProject]
    @ActorOid = @gone, @CustomerConfigID = 900001, @Type = 'Migration', @Name = N'N';
IF (SELECT [Outcome] FROM @r) <> N'UnknownActor' THROW 50040, 'deactivated author rejected', 1;
DELETE FROM @r;
INSERT INTO @r EXEC [onboarding].[CreateProject]
    @ActorOid = @admin, @CustomerConfigID = 42, @Type = 'Migration', @Name = N'N';
IF (SELECT [Outcome] FROM @r) <> N'UnknownCustomer' THROW 50041, 'unknown customer rejected', 1;

ROLLBACK TRANSACTION;
PRINT 'project visibility tests passed';
