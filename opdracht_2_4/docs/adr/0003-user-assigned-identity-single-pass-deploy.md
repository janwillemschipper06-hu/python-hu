# The Container App pulls its image with a user-assigned managed identity, deployed in a single pass

**Status:** accepted (supersedes the system-assigned-identity choice in architecture-design.md §5)

The backend Container App needs `AcrPull` on the shared ACR before its first image pull. With a
**system-assigned** identity the `principalId` only exists after the Container App is created, so the
role assignment has to be a second, ordered deployment step — the two-phase deploy architecture-design.md
§5 originally accepted. Instead we create a **user-assigned managed identity (UAMI)** first, grant it
`AcrPull` on the shared ACR, and only then provision the Container App referencing it. Everything deploys
in **one pass** with no ordering wrinkle.

This mirrors the sister project `9A-Ops-BI-Advanced-Monitoring`, whose infra this deploy is modelled on,
keeping both repos operationally identical.

## Considered options

- **System-assigned identity + two-phase AcrPull (original §5).** Rejected: forces a deliberately ordered
  second deployment step purely to work around the principalId-after-create timing, for no real benefit.
- **User-assigned identity, created first (chosen).** The `principalId` is known before the Container App
  exists, so the AcrPull grant lands before the first pull and the whole stack deploys in a single pass.
  The small cost is one extra long-lived resource (the UAMI) to manage.

## Consequences

- One `Microsoft.ManagedIdentity/userAssignedIdentities` resource (`id-cst-cop-<env>`) is provisioned in
  the app resource group and referenced by the Container App.
- The same UAMI is the single principal granted `AcrPull` (shared ACR) and `Key Vault Secrets User`
  (app Key Vault), so all app-to-Azure access flows through one identity.
- architecture-design.md §5 is updated to describe the UAMI single-pass model instead of the
  system-assigned two-phase model.
