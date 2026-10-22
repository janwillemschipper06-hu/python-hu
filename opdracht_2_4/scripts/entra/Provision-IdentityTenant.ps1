#Requires -Modules Microsoft.Graph.Applications, Microsoft.Graph.Identity.SignIns, Microsoft.Graph.Users

<#
.SYNOPSIS
    Provisions every Microsoft Entra object the Customer Onboarding Portal needs
    in the IDENTITY tenant, idempotently, so dev and prod are built the same way.

.DESCRIPTION
    Creates / reuses, in the identity tenant:
      1. cop-api-<env>  - the API (audience) app registration + service principal
                          with the Admin and Extract.Read app roles and the
                          access_as_user delegated scope (all GUIDs PINNED so
                          downstream config never churns between rebuilds).
      2. cop-spa-<env>  - the SPA public client (PKCE redirect URIs) + service
                          principal, delegated to the API's access_as_user and
                          pre-authorized so users never see a consent prompt.
      3. cop-graph-<env> SERVICE PRINCIPAL ONLY - the app registration itself lives
                          in the RESOURCE/CORPORATE tenant (created by IT, with the
                          federated credential trusting the UAMI). This script only
                          provisions its SP here and grants the four Microsoft Graph
                          application permissions directly on that SP (option 4 - no
                          permissions are declared/consented in the resource tenant).
      4. (optional) a bootstrap admin - invite a B2B guest and assign the Admin app
                          role directly on the cop-api SP (ADR-0011). There is NO
                          Portal-Admins group: admin authority is a DIRECT user
                          app-role assignment (assigning a role to a group needs
                          Entra ID P1, which we neither have nor require).
      5. (always) cop-adf-<env> - the ADF reporting machine client
                          (Stage 9) + its Extract.Read application app-role assignment on
                          the cop-api SP, and optionally its certificate.

    Entra work this script covers, by plan stage (docs/authentication-implementation-plan.md):
      - Stage 1 : cop-api app (Admin role, access_as_user scope, identifier URI) + bootstrap admin;
                  cop-spa app (SPA redirect URIs, public-client flows, delegated API access).
      - Stage 4 : finalised SPA redirect URIs (pass -SpaRedirectUris).
      - Stage 5 : cop-graph SP + User.Invite.All + AppRoleAssignment.ReadWrite.All.
      - Stage 6 : cop-graph SP + User.ReadWrite.All + User.Read.All + Application.Read.All
                  (Application.Read.All is required to list appRoleAssignedTo for the user list).
      - Stage 9 : Extract.Read app role on cop-api (always created) + cop-adf client (always created; optional -AdfCertPath).

    NOT covered here, on purpose:
      - Stage 7 Conditional Access + cross-tenant inbound MFA trust - require Entra ID P1. This
        identity tenant is currently "Microsoft Entra ID Free", so CA policies cannot be created.
        Do this once the tenant is licensed (per-user P1 or External Identities P1 / MAU).
      - The cop-graph app REGISTRATION + its federated credential (they live in the RESOURCE tenant,
        created by IT) and the user-assigned managed identity (UAMI).
      - Container Apps built-in auth (EasyAuth) config and the `allowedApplications` ADF appid
        allowlist - those are infra (bicep), not Entra objects.

    Re-running is safe: existing objects are reused, not duplicated.

.NOTES
    Requires: Global Administrator (or Privileged Role Administrator) in the
    identity tenant to grant the Graph application permissions and the Admin role.
    Install the module first if needed:  Install-Module Microsoft.Graph -Scope CurrentUser
#>

[CmdletBinding()]
param(
    # Identity tenant (dev default). For prod, pass the prod identity tenant ID.
    [string]$IdentityTenantId = '0ef950c5-f5cc-4a60-a2cc-22c8f7e10f52',

    # Environment suffix used in display names: cop-api-<env>, cop-spa-<env>, cop-graph-<env>.
    [string]$EnvSuffix = 'dev',

    # SPA redirect URIs (SPA / PKCE platform). Override per environment.
    [string[]]$SpaRedirectUris = @(
        'http://localhost:5173', 'http://localhost:5173/blank.html',
        'https://icy-moss-0bf843003.3.azurestaticapps.net', 'https://icy-moss-0bf843003.3.azurestaticapps.net/blank.html'
    ),

    # cop-graph application (client) ID - the app registered in the RESOURCE/CORPORATE
    # tenant (multitenant, with the FIC to the UAMI). dev = 2e499fff-...; set for prod.
    [string]$GraphAppClientId = '2e499fff-f1cf-46e7-b082-c79fe38fc972',

    # Optional: invite this email as the bootstrap admin and assign the Admin app role.
    # Leave blank to skip (assign the first admin manually later).
    [string]$BootstrapAdminEmail = '',

    # Optional public-key certificate (.cer/.crt) to upload to the cop-adf-<env> client for
    # cert auth. Leave blank to add the cert later (ADF-side / Key Vault).
    [string]$AdfCertPath = '',

    # Where an invited admin lands after redeeming (the SPA origin). Used only when
    # -BootstrapAdminEmail is set.
    [string]$InviteRedirectUrl = 'https://icy-moss-0bf843003.3.azurestaticapps.net',

    # Pinned GUIDs - keep these STABLE across rebuilds and across dev/prod so the
    # bicepparams that reference role / scope IDs never need to change.
    # These 4 GUIDs are ALSO hardcoded in api/app/integrations/graph.py (role assignment).
    [string]$AdminAppRoleId      = 'd9ca4663-5e3a-41d0-84af-fb97b4becbf1',
    [string]$PmAppRoleId         = 'bb99654e-c0a6-4fc9-9896-4503cafa4f08',
    [string]$UserAppRoleId       = 'bb810150-d66a-4059-8fea-89a05b4c5d7c',
    [string]$ExtractReadAppRoleId = 'd77cec0a-1a75-443d-b99b-aa560cae40a1',
    [string]$AccessAsUserScopeId = '0b1f9c84-2d3e-4a56-8f7b-9c0d1e2f3a4b'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Well-known IDs
$MicrosoftGraphAppId = '00000003-0000-0000-c000-000000000000'
# Microsoft Graph application-permission (app-role) IDs - fixed by Microsoft.
$GraphAppRoles = @{
    'User.Invite.All'                 = '09850681-111b-4a89-9bed-3f2cae46d706'
    'AppRoleAssignment.ReadWrite.All' = '06b708a9-e830-4db3-a914-8e69da51d44f'
    'User.ReadWrite.All'              = '741f803b-c850-494e-b5df-cde7c675a1ca'
    'User.Read.All'                   = 'df021288-bdef-4463-88db-98f22de89214'
    'Application.Read.All'           = '9a5d68dd-52b0-4cc2-bd40-abcf44ac3a30'
}

$apiName   = "cop-api-$EnvSuffix"
$spaName   = "cop-spa-$EnvSuffix"
$graphName = "cop-graph-$EnvSuffix"
$adfName   = "cop-adf-$EnvSuffix"

function Write-Step { param([string]$Message) Write-Host "`n==> $Message" -ForegroundColor Cyan }

# Single-object 'eq' lookups never need paging, so we deliberately DO NOT pass -All:
# the Microsoft.Graph -All auto-pager intermittently throws "The given key was not
# present in the dictionary" (it accesses a nextLink key that isn't there). Retry
# once on that transient error; never swallow it to $null (that would create a dup).
function Invoke-GraphLookup {
    param([scriptblock]$ScriptBlock)
    for ($i = 0; $i -lt 3; $i++) {
        try {
            $hits = @(& $ScriptBlock)
            if ($hits.Count -gt 0) { return $hits[0] }
            return $null
        }
        catch {
            if ($_.Exception.Message -like '*key was not present*' -and $i -lt 2) {
                Start-Sleep -Milliseconds 400
                continue
            }
            throw
        }
    }
}

function Get-AppByName {
    param([string]$Name)
    Invoke-GraphLookup { Get-MgApplication -Filter "displayName eq '$Name'" -ErrorAction Stop }
}

function Get-SpByAppId {
    param([string]$AppId)
    Invoke-GraphLookup { Get-MgServicePrincipal -Filter "appId eq '$AppId'" -ErrorAction Stop }
}

# Microsoft.Graph list cmdlets can throw "The given key was not present in the
# dictionary" when paging an EMPTY collection with -All (e.g. a brand-new SP with
# no app-role assignments). Treat that as "no results" so existence checks still work.
function Invoke-SafeList {
    param([scriptblock]$ScriptBlock)
    try {
        $r = & $ScriptBlock
        if ($null -eq $r) { return @() }
        return @($r)
    }
    catch {
        if ($_.Exception -is [System.Collections.Generic.KeyNotFoundException] -or
            $_.Exception.Message -like '*key was not present*') {
            return @()
        }
        throw
    }
}

# Idempotent app-role assignment: tolerate the "already exists" conflict so re-runs
# never fail even if the existence pre-check missed a grant.
function Add-AppRoleAssignment {
    param(
        [Parameter(Mandatory)][string]$SpId,
        [Parameter(Mandatory)][string]$PrincipalId,
        [Parameter(Mandatory)][string]$ResourceId,
        [Parameter(Mandatory)][string]$AppRoleId,
        [Parameter(Mandatory)][string]$Label
    )
    try {
        New-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $SpId `
            -PrincipalId $PrincipalId -ResourceId $ResourceId -AppRoleId $AppRoleId -ErrorAction Stop | Out-Null
        Write-Host "  granted: $Label"
    }
    catch {
        if ($_.Exception.Message -like '*already exist*') {
            Write-Host "  already granted: $Label"
        }
        else { throw }
    }
}

# ---------------------------------------------------------------------------
Write-Step "Connecting to Microsoft Graph (identity tenant $IdentityTenantId)"
Connect-MgGraph -TenantId $IdentityTenantId -Scopes @(
    'Application.ReadWrite.All',
    'AppRoleAssignment.ReadWrite.All',
    'User.Invite.All',
    'User.ReadWrite.All'
) -NoWelcome

$ctx = Get-MgContext
if ($ctx.TenantId -ne $IdentityTenantId) {
    throw "Connected tenant $($ctx.TenantId) does not match -IdentityTenantId $IdentityTenantId. Aborting."
}
Write-Host "Connected as $($ctx.Account)"

# ---------------------------------------------------------------------------
# 1. API app (cop-api-<env>)
# ---------------------------------------------------------------------------
Write-Step "Ensuring API app '$apiName'"

$apiAppRoles = @(
    @{
        Id                 = $AdminAppRoleId
        DisplayName        = 'Portal Admin'
        Value              = 'Admin'
        Description        = 'Full portal administration. Assigned directly to each admin user (ADR-0011).'
        AllowedMemberTypes = @('User')
        IsEnabled          = $true
    },
    @{
        Id                 = $PmAppRoleId
        DisplayName        = 'Project Manager'
        Value              = 'PM'
        Description        = 'Project manager: creates projects and sees status. Assigned directly to each PM user.'
        AllowedMemberTypes = @('User')
        IsEnabled          = $true
    },
    @{
        Id                 = $UserAppRoleId
        DisplayName        = 'Portal User'
        Value              = 'User'
        Description        = 'Default portal user. Assigned directly to each user.'
        AllowedMemberTypes = @('User')
        IsEnabled          = $true
    },
    @{
        Id                 = $ExtractReadAppRoleId
        DisplayName        = 'Extract.Read'
        Value              = 'Extract.Read'
        Description        = 'Read-only reporting extraction. Assigned to the ADF machine client (Stage 9).'
        AllowedMemberTypes = @('Application')
        IsEnabled          = $true
    }
)

$apiObject = @{
    Oauth2PermissionScopes = @(
        @{
            Id                      = $AccessAsUserScopeId
            Value                   = 'access_as_user'
            Type                    = 'User'
            IsEnabled               = $true
            AdminConsentDisplayName = 'Access the Customer Onboarding Portal API as the signed-in user'
            AdminConsentDescription = 'Allows the SPA to call the portal API on behalf of the signed-in user.'
            UserConsentDisplayName  = 'Access the portal API on your behalf'
            UserConsentDescription  = 'Allows the app to call the portal API as you.'
        }
    )
}

$api = Get-AppByName -Name $apiName
if (-not $api) {
    $api = New-MgApplication -DisplayName $apiName -SignInAudience 'AzureADMyOrg' -AppRoles $apiAppRoles -Api $apiObject
    Write-Host "Created $apiName (appId $($api.AppId))"
}
else {
    Update-MgApplication -ApplicationId $api.Id -AppRoles $apiAppRoles
    Write-Host "Reusing existing $apiName (appId $($api.AppId)); app roles re-applied"
}

# Identifier URI must be api://<appId> and can only be set once the appId is known.
if (-not ($api.IdentifierUris -contains "api://$($api.AppId)")) {
    Update-MgApplication -ApplicationId $api.Id -IdentifierUris @("api://$($api.AppId)")
    Write-Host "Set identifier URI api://$($api.AppId)"
}

$apiSp = Get-SpByAppId -AppId $api.AppId
if (-not $apiSp) {
    $apiSp = New-MgServicePrincipal -AppId $api.AppId
    Write-Host "Created service principal for $apiName (objectId $($apiSp.Id))"
}
else {
    Write-Host "Reusing service principal for $apiName (objectId $($apiSp.Id))"
}

# Invite-only: a user must be a guest AND hold an app role to get a token for this API.
Update-MgServicePrincipal -ServicePrincipalId $apiSp.Id -AppRoleAssignmentRequired:$true
Write-Host "Assignment required = true on $apiName (users without a role cannot sign in)"

# ---------------------------------------------------------------------------
# 2. SPA app (cop-spa-<env>)
# ---------------------------------------------------------------------------
Write-Step "Ensuring SPA app '$spaName'"

$spaRequiredResourceAccess = @(
    @{
        ResourceAppId  = $api.AppId
        ResourceAccess = @(
            @{ Id = $AccessAsUserScopeId; Type = 'Scope' }
        )
    }
)

$spa = Get-AppByName -Name $spaName
if (-not $spa) {
    $spa = New-MgApplication -DisplayName $spaName -SignInAudience 'AzureADMyOrg' `
        -Spa @{ RedirectUris = $SpaRedirectUris } `
        -RequiredResourceAccess $spaRequiredResourceAccess `
        -IsFallbackPublicClient:$true
    Write-Host "Created $spaName (appId $($spa.AppId))"
}
else {
    Update-MgApplication -ApplicationId $spa.Id -Spa @{ RedirectUris = $SpaRedirectUris } `
        -RequiredResourceAccess $spaRequiredResourceAccess -IsFallbackPublicClient:$true
    Write-Host "Reusing existing $spaName (appId $($spa.AppId)); redirect URIs + API permission re-applied"
}

$spaSp = Get-SpByAppId -AppId $spa.AppId
if (-not $spaSp) {
    $spaSp = New-MgServicePrincipal -AppId $spa.AppId
    Write-Host "Created service principal for $spaName (objectId $($spaSp.Id))"
}
else {
    Write-Host "Reusing service principal for $spaName (objectId $($spaSp.Id))"
}

# Pre-authorize the SPA on the API's access_as_user so no interactive consent is needed.
$apiObjectWithPreauth = $apiObject.Clone()
$apiObjectWithPreauth['PreAuthorizedApplications'] = @(
    @{ AppId = $spa.AppId; DelegatedPermissionIds = @($AccessAsUserScopeId) }
)
Update-MgApplication -ApplicationId $api.Id -Api $apiObjectWithPreauth
Write-Host "Pre-authorized $spaName on $apiName/access_as_user"

# ---------------------------------------------------------------------------
# 3. Graph caller SP (app registration lives in the resource tenant)
# ---------------------------------------------------------------------------
Write-Step "Ensuring Graph caller SP '$graphName' (appId $GraphAppClientId) + Graph app roles"

$graphClientSp = Get-SpByAppId -AppId $GraphAppClientId
if (-not $graphClientSp) {
    $graphClientSp = New-MgServicePrincipal -AppId $GraphAppClientId
    Write-Host "Provisioned service principal for $graphName (objectId $($graphClientSp.Id))"
}
else {
    Write-Host "Reusing service principal for $graphName (objectId $($graphClientSp.Id))"
}

$graphResourceSp = Get-SpByAppId -AppId $MicrosoftGraphAppId
if (-not $graphResourceSp) { throw "Microsoft Graph service principal not found in tenant. Aborting." }

$existingGrants = Invoke-SafeList { Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $graphClientSp.Id -All }
foreach ($entry in $GraphAppRoles.GetEnumerator()) {
    $alreadyGranted = $existingGrants | Where-Object { $_.AppRoleId -eq $entry.Value -and $_.ResourceId -eq $graphResourceSp.Id }
    if ($alreadyGranted) {
        Write-Host "  already granted: $($entry.Key)"
    }
    else {
        Add-AppRoleAssignment -SpId $graphClientSp.Id -PrincipalId $graphClientSp.Id `
            -ResourceId $graphResourceSp.Id -AppRoleId $entry.Value -Label $entry.Key
    }
}

# ---------------------------------------------------------------------------
# 4. Optional bootstrap admin
# ---------------------------------------------------------------------------
if ($BootstrapAdminEmail) {
    Write-Step "Bootstrapping admin '$BootstrapAdminEmail'"
    $existingUser = Invoke-GraphLookup { Get-MgUser -Filter "mail eq '$BootstrapAdminEmail'" -ErrorAction Stop }
    if ($existingUser) {
        $adminUserId = $existingUser.Id
        Write-Host "User already present (objectId $adminUserId)"
    }
    else {
        $invite = New-MgInvitation -InvitedUserEmailAddress $BootstrapAdminEmail `
            -InviteRedirectUrl $InviteRedirectUrl -SendInvitationMessage:$true
        $adminUserId = $invite.InvitedUser.Id
        Write-Host "Invited $BootstrapAdminEmail (objectId $adminUserId)"
    }

    $hasAdmin = (Invoke-SafeList { Get-MgServicePrincipalAppRoleAssignedTo -ServicePrincipalId $apiSp.Id -All }) |
        Where-Object { $_.PrincipalId -eq $adminUserId -and $_.AppRoleId -eq $AdminAppRoleId }
    if ($hasAdmin) {
        Write-Host "Admin app role already assigned"
    }
    else {
        Add-AppRoleAssignment -SpId $apiSp.Id -PrincipalId $adminUserId `
            -ResourceId $apiSp.Id -AppRoleId $AdminAppRoleId -Label "Admin -> $BootstrapAdminEmail"
    }
}
else {
    Write-Host "`n(Skipping bootstrap admin - no -BootstrapAdminEmail provided.)"
}

# ---------------------------------------------------------------------------
# 5. ADF reporting client (Stage 9) - always created
# ---------------------------------------------------------------------------
if ($true) {
    Write-Step "Ensuring ADF reporting client '$adfName' + Extract.Read assignment"

    $adf = Get-AppByName -Name $adfName
    if (-not $adf) {
        $adf = New-MgApplication -DisplayName $adfName -SignInAudience 'AzureADMyOrg'
        Write-Host "Created $adfName (appId $($adf.AppId))"
    }
    else {
        Write-Host "Reusing existing $adfName (appId $($adf.AppId))"
    }

    if ($AdfCertPath) {
        if (-not (Test-Path $AdfCertPath)) { throw "AdfCertPath not found: $AdfCertPath" }
        $cer = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new((Resolve-Path $AdfCertPath).Path)
        $keyCred = @{
            Type        = 'AsymmetricX509Cert'
            Usage       = 'Verify'
            Key         = $cer.RawData
            DisplayName = "CN=$adfName"
        }
        Update-MgApplication -ApplicationId $adf.Id -KeyCredentials @($keyCred)
        Write-Host "Uploaded certificate from $AdfCertPath (thumbprint $($cer.Thumbprint))"
    }
    else {
        Write-Host "No -AdfCertPath given; upload the ADF certificate later (ADF-side / Key Vault)."
    }

    $adfSp = Get-SpByAppId -AppId $adf.AppId
    if (-not $adfSp) {
        $adfSp = New-MgServicePrincipal -AppId $adf.AppId
        Write-Host "Created service principal for $adfName (objectId $($adfSp.Id))"
    }
    else {
        Write-Host "Reusing service principal for $adfName (objectId $($adfSp.Id))"
    }

    $hasExtract = (Invoke-SafeList { Get-MgServicePrincipalAppRoleAssignedTo -ServicePrincipalId $apiSp.Id -All }) |
        Where-Object { $_.PrincipalId -eq $adfSp.Id -and $_.AppRoleId -eq $ExtractReadAppRoleId }
    if ($hasExtract) {
        Write-Host "Extract.Read already assigned to $adfName"
    }
    else {
        Add-AppRoleAssignment -SpId $apiSp.Id -PrincipalId $adfSp.Id `
            -ResourceId $apiSp.Id -AppRoleId $ExtractReadAppRoleId -Label "Extract.Read -> $adfName"
    }
}

# ---------------------------------------------------------------------------
# Summary - paste these into infra/environments/<env>/main.bicepparam
# ---------------------------------------------------------------------------
Write-Step "DONE. Record these values (they change on every rebuild except the pinned GUIDs):"

$summary = [ordered]@{
    'entraTenantId         (identity tenant)'      = $IdentityTenantId
    'entraApiClientId      (cop-api appId)'        = $api.AppId
    'entraApiAudience      (api://<cop-api appId>)' = "api://$($api.AppId)"
    'entraApiSpObjectId    (cop-api SP objectId)'  = $apiSp.Id
    'entraSpaClientId      (cop-spa appId)'        = $spa.AppId
    'VITE_SPA_CLIENT_ID    (frontend build)'       = $spa.AppId
    'entraAdminAppRoleId   (PINNED)'               = $AdminAppRoleId
    'PmAppRoleId           (PINNED)'               = $PmAppRoleId
    'UserAppRoleId         (PINNED)'               = $UserAppRoleId
    'ExtractReadAppRoleId  (PINNED)'               = $ExtractReadAppRoleId
    'access_as_user scope  (PINNED)'               = $AccessAsUserScopeId
    'entraGraphClientId    (resource-tenant app)'  = $GraphAppClientId
    'cop-graph SP objectId (identity tenant)'      = $graphClientSp.Id
}
$summary['entraAdfClientId      (cop-adf appId)'] = $adf.AppId
$summary['cop-adf SP objectId   (allowlist/role)'] = $adfSp.Id
$summary.GetEnumerator() | ForEach-Object { '{0,-45} {1}' -f $_.Key, $_.Value } | Write-Host

Write-Host "`nReminder: entraApiClientId / entraApiAudience / entraApiSpObjectId / entraSpaClientId" -ForegroundColor Yellow
Write-Host "changed -> update main.bicepparam + the frontend VITE_SPA_CLIENT_ID, then redeploy so" -ForegroundColor Yellow
Write-Host "Container Apps built-in auth (EasyAuth) validates against the new app." -ForegroundColor Yellow
Write-Host "Stage 7 (Conditional Access + cross-tenant MFA trust) is NOT provisioned here - it needs" -ForegroundColor Yellow
Write-Host "Entra ID P1; this tenant is currently Free. Do it once the tenant is licensed." -ForegroundColor Yellow
