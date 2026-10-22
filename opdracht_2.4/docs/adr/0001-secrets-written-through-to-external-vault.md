# Customer secrets are written through to an external secret vault, never stored in our database

**Status:** superseded by ADR-0007

> **Superseded.** The external secret vault and separate secrets-management team are no longer
> available to this portal, so the portal must own secret storage and the onboarding pipeline must
> read the values directly. [ADR-0007](./0007-secrets-in-database-envelope-encryption.md) reverses
> this decision: secrets are now stored in Azure SQL under application-layer envelope encryption
> (AES-256-GCM DEK wrapped by an HSM KEK in Key Vault). The remainder of this ADR is retained for
> historical context only.

Customer-submitted secrets (passwords, client secrets, API keys) are the crown-jewel asset, and
our threat model treats the database/platform operator as partially untrusted. Rather than storing
secrets in Azure SQL under application-layer envelope encryption, the backend **writes each secret
through to an external secret vault at submission time** (holding plaintext only transiently in
memory) and persists **only a reference** (target location + metadata). The portal never holds the
value, so write-only behaviour is intrinsic and there is no in-portal plaintext reveal path.

The external secret vault is **provisioned, owned, and operated by a separate secrets-management
team**. The portal is only a write client: that team provides an endpoint, write-only credentials,
and a target addressing convention. The vault's structure, isolation, access control, retrieval,
lifecycle, retention, and any vendor/DPA relationship are that team's responsibility and out of
scope for this portal.

## Considered options

- **Application-layer envelope encryption** (AES-256-GCM per-value data keys wrapped by a
  per-customer KEK in an HSM-backed key store, ciphertext in Azure SQL). Rejected: it keeps
  crown-jewel material in our database and introduces custom cryptography we would have to get
  exactly right, for no benefit once a purpose-built secrets manager is in the picture.
- **Key Vault secret per value.** Rejected: root key is Microsoft-managed (inconsistent with the
  "platform untrusted" posture) and it still centralises secret custody in our tenant.
- **Write-through to an external secret vault (chosen).** Our database holds zero secret plaintext
  or ciphertext; custody and access are delegated to a purpose-built secrets manager run by a
  separate secrets-management team with its own audit, versioning, and access control.

## Consequences

- Secret custody, vendor risk, and any processor/DPA relationship are owned by the
  secrets-management team, not this portal.
- The portal's only standing secret is the **write-only credential** that team provides; it is held
  in Key Vault and used solely to write submitted values to the vault.
- The secret still transits the request path, so **no request-body logging** on secret-write
  routes is a hard, non-negotiable control.
- Deployment access to plaintext happens inside the vault, managed by the secrets-management team,
  not the portal.
- This decision **supersedes** any envelope-encryption / KEK / HSM design for secret storage.
