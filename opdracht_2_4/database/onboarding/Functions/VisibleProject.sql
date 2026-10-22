-- ---------------------------------------------------------------------------
-- The single Project visibility rule (docs/projects-design.md §3, ADR-0013), used
-- by every Project procedure so it is declared once:
--
--   Staff (Admin/PM, @IsStaff = 1)  every Project except another author's Draft.
--   Customer user (@IsStaff = 0)    only Projects they are assigned to (a
--                                   ProjectPerson row linked to their active
--                                   Users row) that are Approved or later and not
--                                   Cancelled, so cancelling revokes access at once.
--
-- Returns the visible ProjectIds; callers join to it. Scope is resolved here, in
-- the database, from the caller's oid (docs/adr/0002).
-- ---------------------------------------------------------------------------
CREATE FUNCTION [onboarding].[VisibleProject](
    @ActorOid UNIQUEIDENTIFIER,
    @IsStaff BIT
)
RETURNS TABLE
AS
RETURN
(
    SELECT p.[ProjectId]
    FROM [onboarding].[Project] AS p
    WHERE
        (
            @IsStaff = 1
            AND (
                p.[State] <> 'Draft'
                OR p.[CreatedByUserId] IN (
                    SELECT u.[UserId] FROM [onboarding].[Users] AS u
                    WHERE u.[EntraOid] = @ActorOid
                )
            )
        )
        OR (
            @IsStaff = 0
            AND p.[State] IN ('Approved', 'InProgress', 'Ready', 'OnHold')
            AND EXISTS (
                SELECT 1
                FROM [onboarding].[ProjectPerson] AS pp
                INNER JOIN [onboarding].[Users] AS u ON pp.[UserId] = u.[UserId]
                WHERE
                    pp.[ProjectId] = p.[ProjectId]
                    AND u.[EntraOid] = @ActorOid
                    AND u.[DeactivatedUtc] IS NULL
            )
        )
);
