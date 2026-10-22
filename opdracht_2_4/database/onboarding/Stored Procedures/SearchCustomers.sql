-- ---------------------------------------------------------------------------
-- Read-only customer lookup over the external ext.Customer table (docs/adr/0013,
-- docs/projects-design.md). Returns only id + name — never the other columns.
-- @Query is a case-insensitive substring match on the name (NULL/empty = all);
-- LIKE wildcards in @Query are escaped so they match literally. Capped at @Top
-- rows to keep the picker response small. EXECUTE-only access (docs/adr/0002).
-- ---------------------------------------------------------------------------
CREATE PROCEDURE [onboarding].[SearchCustomers]
    @Query NVARCHAR(255) = NULL,
    @Top INT = 25
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE
        @Pattern NVARCHAR(600)
        = N'%'
        + REPLACE(
            REPLACE(REPLACE(ISNULL(@Query, N''), N'\', N'\\'), N'%', N'\%'),
            N'_', N'\_'
        )
        + N'%';

    SELECT TOP (@Top)
        [CustomerConfigID] AS [Id],
        [CustomerName] AS [Name]
    FROM [ext].[Customer]
    WHERE [CustomerName] LIKE @Pattern ESCAPE N'\'
    ORDER BY [CustomerName], [CustomerConfigID];
END;
