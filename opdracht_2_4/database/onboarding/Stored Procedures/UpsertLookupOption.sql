-- ---------------------------------------------------------------------------
-- Admin: add (@LookupOptionId NULL) or edit a dropdown option and return the
-- row. An edit replaces every value, so the admin screen sends the whole row
-- (deactivate = send IsActive 0); Kind never changes. Admin-only is enforced by
-- the API router (ADR-0010/0012). A duplicate (Kind, Name, Family) raises the
-- unique-key error 2627 and a bad Kind/Family/PackKind a CHECK error 547, which
-- the API maps to 409/422. An unknown id returns no row (404).
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[UpsertLookupOption]
    @LookupOptionId INT = NULL,
    @Kind VARCHAR(30) = NULL,
    @Name NVARCHAR(200),
    @Family VARCHAR(10) = NULL,
    @PackKind VARCHAR(10) = NULL,
    @ExcludedSourceSystemId INT = NULL,
    @AllowsFreeText BIT = 0,
    @SortOrder INT = 0,
    @IsActive BIT = 1
AS
BEGIN
    SET NOCOUNT ON;

    SET @Name = LTRIM(RTRIM(@Name));
    IF NULLIF(@Name, N'') IS NULL
        THROW 50002, 'Name is required.', 1;

    IF @LookupOptionId IS NULL
        BEGIN
            INSERT INTO [onboarding].[LookupOption]
            ([Kind], [Name], [Family], [PackKind], [ExcludedSourceSystemId], [AllowsFreeText], [SortOrder], [IsActive])
            OUTPUT
                INSERTED.[LookupOptionId] AS [Id],
                INSERTED.[Kind],
                INSERTED.[Name],
                INSERTED.[Family],
                INSERTED.[PackKind],
                INSERTED.[ExcludedSourceSystemId],
                INSERTED.[AllowsFreeText],
                INSERTED.[SortOrder],
                INSERTED.[IsActive]
            VALUES
            (@Kind, @Name, @Family, @PackKind, @ExcludedSourceSystemId, @AllowsFreeText, @SortOrder, @IsActive);
            RETURN;
        END;

    UPDATE [onboarding].[LookupOption]
    SET
        [Name] = @Name,
        [Family] = @Family,
        [PackKind] = @PackKind,
        [ExcludedSourceSystemId] = @ExcludedSourceSystemId,
        [AllowsFreeText] = @AllowsFreeText,
        [SortOrder] = @SortOrder,
        [IsActive] = @IsActive
    OUTPUT
        INSERTED.[LookupOptionId] AS [Id],
        INSERTED.[Kind],
        INSERTED.[Name],
        INSERTED.[Family],
        INSERTED.[PackKind],
        INSERTED.[ExcludedSourceSystemId],
        INSERTED.[AllowsFreeText],
        INSERTED.[SortOrder],
        INSERTED.[IsActive]
    WHERE [LookupOptionId] = @LookupOptionId;
END;
