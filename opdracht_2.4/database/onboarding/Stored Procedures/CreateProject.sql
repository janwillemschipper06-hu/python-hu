-- ---------------------------------------------------------------------------
-- Create a Project in state Draft (docs/projects-design.md §3-§4). The caller is
-- the author (CreatedByUserId). The requester defaults to the caller; the API
-- passes @RequesterOid when another PM is chosen and has already checked the
-- requester's role (roles live only in Entra, docs/adr/0012).
--
-- Returns one row (Outcome, ProjectId):
--   Ok               created; ProjectId is set
--   UnknownActor     the caller has no active Users row
--   UnknownRequester the requester has no active Users row
--   UnknownCustomer  CustomerConfigID is not in ext.Customer
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[CreateProject]
    @ActorOid UNIQUEIDENTIFIER,
    @RequesterOid UNIQUEIDENTIFIER = NULL,
    @CustomerConfigID INT,
    @Type VARCHAR(12),
    @Name NVARCHAR(200),
    @DepartmentId INT = NULL,
    @CustomerType VARCHAR(10) = NULL,
    @Deadline DATE = NULL,
    @Hours INT = NULL,
    @RequestNotes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @ActorUserId INT, @RequesterUserId INT, @ProjectId INT;

    SELECT @ActorUserId = [UserId]
    FROM [onboarding].[Users]
    WHERE [EntraOid] = @ActorOid AND [DeactivatedUtc] IS NULL;

    IF @ActorUserId IS NULL
        BEGIN
            SELECT
                N'UnknownActor' AS [Outcome],
                CAST(NULL AS INT) AS [ProjectId];
            RETURN;
        END;

    SELECT @RequesterUserId = [UserId]
    FROM [onboarding].[Users]
    WHERE [EntraOid] = ISNULL(@RequesterOid, @ActorOid) AND [DeactivatedUtc] IS NULL;

    IF @RequesterUserId IS NULL
        BEGIN
            SELECT
                N'UnknownRequester' AS [Outcome],
                CAST(NULL AS INT) AS [ProjectId];
            RETURN;
        END;

    IF
        NOT EXISTS (
            SELECT 1 FROM [ext].[Customer]
            WHERE [CustomerConfigID] = @CustomerConfigID
        )
        BEGIN
            SELECT
                N'UnknownCustomer' AS [Outcome],
                CAST(NULL AS INT) AS [ProjectId];
            RETURN;
        END;

    BEGIN TRANSACTION;

    INSERT INTO [onboarding].[Project]
    (
        [CustomerConfigID], [Type], [Name], [RequesterUserId], [CreatedByUserId],
        [DepartmentId], [CustomerType], [Deadline], [Hours], [RequestNotes]
    )
    VALUES
    (
        @CustomerConfigID, @Type, @Name, @RequesterUserId, @ActorUserId,
        @DepartmentId, @CustomerType, @Deadline, @Hours, @RequestNotes
    );

    SET @ProjectId = SCOPE_IDENTITY();

    EXEC [onboarding].[AppendAuditEvent]
        @Action = N'CreateProject',
        @ActorOid = @ActorOid,
        @TargetType = N'Project',
        @TargetId = @ProjectId;

    COMMIT TRANSACTION;

    SELECT
        N'Ok' AS [Outcome],
        @ProjectId AS [ProjectId];
END;
