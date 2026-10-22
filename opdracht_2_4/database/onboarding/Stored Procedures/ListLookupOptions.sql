-- ---------------------------------------------------------------------------
-- Read the dropdown options. @Kind = NULL returns every kind (the API caches
-- this for the Project forms); @IncludeInactive = 1 also returns deactivated
-- options for the Admin lookup screen. Any signed-in role may read the picker
-- view; the API decides who may ask for inactive ones.
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[ListLookupOptions]
    @Kind VARCHAR(30) = NULL,
    @IncludeInactive BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        [LookupOptionId] AS [Id],
        [Kind],
        [Name],
        [Family],
        [PackKind],
        [ExcludedSourceSystemId],
        [AllowsFreeText],
        [SortOrder],
        [IsActive]
    FROM [onboarding].[LookupOption]
    WHERE
        (@Kind IS NULL OR [Kind] = @Kind)
        AND (@IncludeInactive = 1 OR [IsActive] = 1)
    ORDER BY [Kind], [Family], [SortOrder], [Name];
END;
