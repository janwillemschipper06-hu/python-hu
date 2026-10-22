-- ---------------------------------------------------------------------------
-- Delete a Project: the only hard delete, allowed solely for an Admin and only
-- for a Draft they can see (docs/projects-design.md §4). People and connectors cascade.
--
-- Returns one row (Outcome, ProjectId):
--   Ok, NotFound (missing or not visible, incl. another author's Draft),
--   Forbidden (non-Admin: PM or customer user), NotDraft (already submitted)
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[DeleteProject]
    @ActorOid UNIQUEIDENTIFIER,
    @IsStaff BIT,
    @IsAdmin BIT,
    @ProjectId INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @State VARCHAR(12);

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

    IF @IsAdmin = 0
        BEGIN
            SELECT
                N'Forbidden' AS [Outcome],
                @ProjectId AS [ProjectId];
            RETURN;
        END;

    IF @State <> 'Draft'
        BEGIN
            SELECT
                N'NotDraft' AS [Outcome],
                @ProjectId AS [ProjectId];
            RETURN;
        END;

    BEGIN TRANSACTION;

    DELETE FROM [onboarding].[Project]
    WHERE [ProjectId] = @ProjectId;

    EXEC [onboarding].[AppendAuditEvent]
        @Action = N'DeleteProject',
        @ActorOid = @ActorOid,
        @TargetType = N'Project',
        @TargetId = @ProjectId;

    COMMIT TRANSACTION;

    SELECT
        N'Ok' AS [Outcome],
        @ProjectId AS [ProjectId];
END;
