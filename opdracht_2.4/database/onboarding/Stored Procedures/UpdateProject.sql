-- ---------------------------------------------------------------------------
-- Replace the editable header fields of a Project (docs/projects-design.md §3-§4).
-- The API merges a PATCH over the current values and passes the full set. Type is
-- immutable. Draft: only its author can see (and so edit) it. After Draft only an
-- Admin may edit, and every such edit is audited atomically with the change;
-- @AuditDetail is VALUE-FREE metadata (the changed field names).
--
-- Returns one row (Outcome, ProjectId):
--   Ok, NotFound (missing or not visible), Forbidden (customer user),
--   Locked (non-Admin editing after Draft), UnknownRequester, UnknownCustomer,
--   UnknownConsultant (@SetConsultant = 1 with no active user; Admin only)
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[UpdateProject]
    @ActorOid UNIQUEIDENTIFIER,
    @IsStaff BIT,
    @IsAdmin BIT,
    @ProjectId INT,
    @RequesterOid UNIQUEIDENTIFIER,
    @CustomerConfigID INT,
    @Name NVARCHAR(200),
    @DepartmentId INT = NULL,
    @CustomerType VARCHAR(10) = NULL,
    @Deadline DATE = NULL,
    @Hours INT = NULL,
    @RequestNotes NVARCHAR(MAX) = NULL,
    @AuditDetail NVARCHAR(MAX) = NULL,
    @ConsultantOid UNIQUEIDENTIFIER = NULL,
    @SetConsultant BIT = 0
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @State VARCHAR(12), @RequesterUserId INT, @ConsultantUserId INT;

    SELECT @State = p.[State]
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

    SELECT @RequesterUserId = [UserId]
    FROM [onboarding].[Users]
    WHERE [EntraOid] = @RequesterOid AND [DeactivatedUtc] IS NULL;

    IF @RequesterUserId IS NULL
        BEGIN
            SELECT
                N'UnknownRequester' AS [Outcome],
                @ProjectId AS [ProjectId];
            RETURN;
        END;

    IF @SetConsultant = 1
        BEGIN
            IF @IsAdmin = 0
                BEGIN
                    SELECT
                        N'Forbidden' AS [Outcome],
                        @ProjectId AS [ProjectId];
                    RETURN;
                END;

            SELECT @ConsultantUserId = [UserId]
            FROM [onboarding].[Users]
            WHERE [EntraOid] = @ConsultantOid AND [DeactivatedUtc] IS NULL;

            IF @ConsultantUserId IS NULL
                BEGIN
                    SELECT
                        N'UnknownConsultant' AS [Outcome],
                        @ProjectId AS [ProjectId];
                    RETURN;
                END;
        END;

    IF
        NOT EXISTS (
            SELECT 1 FROM [ext].[Customer]
            WHERE [CustomerConfigID] = @CustomerConfigID
        )
        BEGIN
            SELECT
                N'UnknownCustomer' AS [Outcome],
                @ProjectId AS [ProjectId];
            RETURN;
        END;

    BEGIN TRANSACTION;

    UPDATE [onboarding].[Project]
    SET
        [RequesterUserId] = @RequesterUserId,
        [CustomerConfigID] = @CustomerConfigID,
        [Name] = @Name,
        [DepartmentId] = @DepartmentId,
        [CustomerType] = @CustomerType,
        [Deadline] = @Deadline,
        [Hours] = @Hours,
        [RequestNotes] = @RequestNotes,
        [ConsultantUserId] = CASE WHEN @SetConsultant = 1 THEN @ConsultantUserId ELSE [ConsultantUserId] END,
        [UpdatedUtc] = SYSUTCDATETIME()
    WHERE [ProjectId] = @ProjectId;

    IF @State <> 'Draft'
        EXEC [onboarding].[AppendAuditEvent]
            @Action = N'UpdateProject',
            @ActorOid = @ActorOid,
            @TargetType = N'Project',
            @TargetId = @ProjectId,
            @Detail = @AuditDetail;

    COMMIT TRANSACTION;

    SELECT
        N'Ok' AS [Outcome],
        @ProjectId AS [ProjectId];
END;
