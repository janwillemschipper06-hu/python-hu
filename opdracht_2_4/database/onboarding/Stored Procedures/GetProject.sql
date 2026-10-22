-- ---------------------------------------------------------------------------
-- Read one Project the caller may see (VisibleProject). Zero rows means "not
-- found or not visible" so the API cannot leak that a hidden Project exists.
-- Internal fields (hours, notes, rejection reason, tickets) are NULL for
-- customer users (@IsStaff = 0).
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[GetProject]
    @ActorOid UNIQUEIDENTIFIER,
    @IsStaff BIT,
    @ProjectId INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        p.[ProjectId],
        p.[CustomerConfigID],
        c.[CustomerName],
        p.[Type],
        p.[Name],
        p.[State],
        ru.[Email] AS [RequesterEmail],
        cu.[Email] AS [CreatedByEmail],
        p.[DepartmentId],
        p.[CustomerType],
        p.[Deadline],
        xu.[Email] AS [ConsultantEmail],
        p.[CreatedUtc],
        p.[UpdatedUtc],
        CASE WHEN @IsStaff = 1 THEN p.[RejectionReason] END AS [RejectionReason],
        CONVERT(NVARCHAR(36), ru.[EntraOid]) AS [RequesterOid],
        CASE WHEN @IsStaff = 1 THEN p.[Hours] END AS [Hours],
        CASE WHEN @IsStaff = 1 THEN p.[RequestNotes] END AS [RequestNotes],
        CASE WHEN @IsStaff = 1 THEN p.[RequestTicketId] END AS [RequestTicketId],
        CASE WHEN @IsStaff = 1 THEN p.[CommunicationTicketId] END AS [CommunicationTicketId]
    FROM [onboarding].[Project] AS p
    INNER JOIN [onboarding].[VisibleProject](@ActorOid, @IsStaff) AS v ON p.[ProjectId] = v.[ProjectId]
    INNER JOIN [onboarding].[Users] AS ru ON p.[RequesterUserId] = ru.[UserId]
    INNER JOIN [onboarding].[Users] AS cu ON p.[CreatedByUserId] = cu.[UserId]
    LEFT JOIN [onboarding].[Users] AS xu ON p.[ConsultantUserId] = xu.[UserId]
    LEFT JOIN [ext].[Customer] AS c ON p.[CustomerConfigID] = c.[CustomerConfigID]
    WHERE p.[ProjectId] = @ProjectId;
END;
