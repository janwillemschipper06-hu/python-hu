-- ---------------------------------------------------------------------------
-- Seeds the admin-managed dropdown options (LookupOption) from the legacy
-- Microsoft Forms (docs/projects-design.md §5). Included by post-deploy.sql.
--
-- Idempotent and non-destructive: a row is inserted only when its
-- (Kind, Name, Family) is missing, so re-running the pipeline never duplicates
-- rows or overwrites options an Admin renamed, re-ordered or deactivated.
-- ---------------------------------------------------------------------------

-- Plain dropdowns and source systems first, so content packs can reference them.
INSERT INTO [onboarding].[LookupOption] ([Kind], [Name], [Family], [AllowsFreeText], [SortOrder])
SELECT
    [v].[Kind],
    [v].[Name],
    [v].[Family],
    [v].[AllowsFreeText],
    [v].[SortOrder]
FROM (
    VALUES
    ('Department', N'9A Belgium', NULL, 0, 1),
    ('Department', N'9A Denmark', NULL, 0, 2),
    ('Department', N'9A France', NULL, 0, 3),
    ('Department', N'9A Netherlands', NULL, 0, 4),
    ('InstallationType', N'During a requirements session, the actual installation type will be determined', NULL, 0, 1),
    ('InstallationType', N'On-Premise', NULL, 0, 2),
    ('InstallationType', N'Azure Cloud', NULL, 0, 3),
    ('InstallationType', N'On-Premise / Azure Cloud Hybrid', NULL, 0, 4),
    ('InstallationType', N'Fabric', NULL, 0, 5),
    ('PowerBILicense', N'Power BI Pro', NULL, 0, 1),
    ('PowerBILicense', N'Power BI Premium Per User', NULL, 0, 2),
    ('PowerBILicense', N'To Be Decided', NULL, 0, 3),
    ('EnvironmentConnection', N'Connect all environments to production data', NULL, 0, 1),
    ('EnvironmentConnection', N'Connect prod to production data and other environments to sandbox data', NULL, 0, 2),
    ('EnvironmentConnection', N'Other', NULL, 1, 3),
    ('MigrationType', N'Server Migration', NULL, 0, 1),
    ('MigrationType', N'NAV / BC (on-prem) to BCSaaS', NULL, 0, 2),
    ('MigrationType', N'BCSaaS API to BC2ADLS', NULL, 0, 3),
    ('MigrationType', N'Fabric', NULL, 0, 4),
    ('MigrationType', N'Fabric - Warehouse', NULL, 0, 5),
    ('MigrationType', N'(A)AS to PPU', NULL, 0, 6),
    ('MigrationType', N'Other (define in the migration information)', NULL, 0, 7),
    ('SourceSystem', N'Microsoft Dynamics AX (On-Premise)', 'AXFO', 0, 1),
    ('SourceSystem', N'Microsoft Dynamics D365 F&O (SaaS)', 'AXFO', 0, 2),
    ('SourceSystem', N'Microsoft Dynamics NAV (On-Premise)', 'NAVBC', 0, 3),
    ('SourceSystem', N'Microsoft Dynamics D365 BC (On-Premise)', 'NAVBC', 0, 4),
    ('SourceSystem', N'Microsoft Dynamics D365 BC (SaaS)', 'NAVBC', 0, 5),
    ('SourceSystem', N'Microsoft Dynamics D365 CE (SaaS)', 'CE', 0, 6),
    ('SourceSystem', N'Microsoft SQL Server', 'SQL', 0, 7)
) AS [v] ([Kind], [Name], [Family], [AllowsFreeText], [SortOrder])
WHERE NOT EXISTS (
    SELECT 1
    FROM [onboarding].[LookupOption] AS [t]
    WHERE
        [t].[Kind] = [v].[Kind]
        AND [t].[Name] = [v].[Name]
        AND ([t].[Family] = [v].[Family] OR ([t].[Family] IS NULL AND [v].[Family] IS NULL))
);

-- Content packs. AX/F&O and NAV/BC share the Kickstart and additional packs;
-- "9A Advanced Manufacturing" is not available for AX.
INSERT INTO [onboarding].[LookupOption] ([Kind], [Name], [Family], [PackKind], [ExcludedSourceSystemId], [SortOrder])
SELECT
    'ContentPack' AS [Kind],
    [v].[Name],
    [v].[Family],
    [v].[PackKind],
    [ss].[LookupOptionId],
    [v].[SortOrder]
FROM (
    VALUES
    (N'Kickstart Finance', 'AXFO', 'Kickstart', NULL, 1),
    (N'Kickstart Logistics', 'AXFO', 'Kickstart', NULL, 2),
    (N'Manufacturing', 'AXFO', 'Additional', NULL, 3),
    (N'Projects', 'AXFO', 'Additional', NULL, 4),
    (N'9A Advanced Manufacturing', 'AXFO', 'Additional', N'Microsoft Dynamics AX (On-Premise)', 5),
    (N'Kickstart Finance', 'NAVBC', 'Kickstart', NULL, 1),
    (N'Kickstart Logistics', 'NAVBC', 'Kickstart', NULL, 2),
    (N'Manufacturing', 'NAVBC', 'Additional', NULL, 3),
    (N'Projects', 'NAVBC', 'Additional', NULL, 4),
    (N'4PS', 'NAVBC', 'Isv', NULL, 5),
    (N'4PS UK', 'NAVBC', 'Isv', NULL, 6),
    (N'ACA / XPRT Premium Package', 'NAVBC', 'Isv', NULL, 7),
    (N'It Suits Fashion 365', 'NAVBC', 'Isv', NULL, 8),
    (N'Kickstart CE', 'CE', 'Kickstart', NULL, 1),
    (N'9A Memberships Management', 'CE', 'Additional', NULL, 2),
    (N'9A Events', 'CE', 'Additional', NULL, 3),
    (N'9A Project Service Operations', 'CE', 'Additional', NULL, 4),
    (N'9A Field Service', 'CE', 'Additional', NULL, 5),
    (N'9A Field Service NL', 'CE', 'Additional', NULL, 6),
    (N'9A Field Service DK', 'CE', 'Additional', NULL, 7)
) AS [v] ([Name], [Family], [PackKind], [ExcludedSourceSystemName], [SortOrder])
LEFT JOIN [onboarding].[LookupOption] AS [ss]
    ON [v].[ExcludedSourceSystemName] = [ss].[Name] AND [ss].[Kind] = 'SourceSystem'
WHERE NOT EXISTS (
    SELECT 1
    FROM [onboarding].[LookupOption] AS [t]
    WHERE [t].[Kind] = 'ContentPack' AND [t].[Family] = [v].[Family] AND [t].[Name] = [v].[Name]
);
