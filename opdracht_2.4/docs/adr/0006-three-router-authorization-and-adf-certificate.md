# Authorization is enforced at three routers, and ADF authenticates with a certificate

**Status:** accepted (amended by ADR-0009 and ADR-0010)

> **Amended by [ADR-0009](./0009-no-machine-secret-consumer.md).** The `/extract/*` router no longer
> serves a `Secret.Consume` pipeline identity — there is no machine secret-consumer. It now carries
> only the `Extract.Read` reporting identity (certificate client, `appid` allowlist). The
> three-router shape and ADF-certificate decision below are otherwise unchanged.
>
> **Amended by [ADR-0010](./0010-platform-authentication-via-container-apps-built-in-auth.md).** The
> machine-caller `appid` allowlist moves from the shared APIM into **this repo's** Container Apps
> built-in auth (`allowedApplications`); token *validation* is likewise performed by that platform
> layer, not the app. The authorization model below is otherwise unchanged.

The API is split into **three routers, each carrying a mandatory router-level guard** so no endpoint
can be accidentally under-protected: **`/api/v1/admin/*`** (requires the `Admin` app-role claim),
**`/api/v1/portal/*`** (a customer-scoped guest **or** an admin acting within the customer named in
the request), and **`/api/v1/extract/*`** (the ADF machine client only, `Extract.Read` app role, no
user context). A **single API app registration** is the audience for all three. The **ADF reporting
identity is a separate client app registration that authenticates with a certificate** (Key
Vault-stored, rotated), because Azure Data Factory cannot use workload-identity federation for
REST/Web calls and managed identity is unreliable against a custom-API audience across tenants.

## Considered options

- **Per-endpoint authorization checks.** Rejected as the primary boundary: one endpoint missing a
  decorator silently over-shares. Router-level guards make protection the default and omission the
  exception.
- **A single mixed router with role branching inside handlers.** Rejected: admin, customer, and
  machine traffic have different identities and blast radii; separating them lets the token layer
  reject a wrong-role caller before any handler runs.
- **Separate app registration per router.** Rejected: unnecessary; one audience with distinct
  **app roles** (`Admin`, `Extract.Read`) already gives token-layer separation. The ADF client is a
  separate registration only because it is a different *caller*, not to separate routers.
- **ADF via managed identity / workload-identity federation, no stored credential (previous §5.4).**
  Rejected: not supported by ADF for REST linked services to a custom API audience.
- **Three routers + single API app registration + ADF certificate client (chosen).**

## Consequences

- **Admins may act on both the admin and customer routers**; the customer guard resolves an admin's
  scope from the customer named in the request, and a plain identity that is neither admin nor scoped
  guest is rejected.
- The database's EXECUTE-only stored procedures (ADR-0002) remain the second enforcement layer
  beneath the guards.
- **This reverses `security-design.md` §5.4's "no client secret or certificate stored anywhere"**: a
  standing ADF certificate now exists. It is Key-Vault-stored, rotated, scoped to `Extract.Read`,
  and gated by a Container Apps built-in auth `appid` allowlist (`allowedApplications`; see
  [ADR-0010](./0010-platform-authentication-via-container-apps-built-in-auth.md)); a client secret is
  a documented fallback (residual risk R5 in security-design §18). Extract feeds never carry secret
  values.
- Full design in [authentication-and-access.md](../authentication-and-access.md).
