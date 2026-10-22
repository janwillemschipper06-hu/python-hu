# Authentication is offloaded to the platform (Container Apps built-in auth); the app only authorizes

**Status:** accepted

> **Amends [`authentication-and-access.md`](../authentication-and-access.md) §2, §4.3, §10** (the API
> no longer validates tokens itself) and **amends [ADR-0006](./0006-three-router-authorization-and-adf-certificate.md)**
> (the machine-caller `appid` allowlist moves from the shared APIM into this repo's Container Apps
> auth configuration). The three-router authorization model, app roles, and ADF certificate decision
> are otherwise unchanged.

Inbound access-token **validation** (signature, issuer, audience, expiry) is performed by **Azure
Container Apps built-in authentication** — the platform auth feature ("EasyAuth") — configured as a
`Microsoft.App/containerApps/authConfigs` resource in **this repo's Bicep**, running in **API mode**
(`globalValidation.unauthenticatedClientAction: Return401`). The FastAPI application **no longer
validates JWTs itself**: it reads the platform-injected, pre-validated principal
(`X-MS-CLIENT-PRINCIPAL`) behind the existing `validated_token` dependency and spends its logic
budget on **authorization only** — the three-router guards and customer scope. The identity tenant is
a dedicated, standard workforce Entra tenant (ADR-0005), so the provider's issuer/metadata is set to
that tenant's OpenID configuration and `allowedAudiences` is the API's Application ID URI. The **ADF
machine-caller `appid` allowlist** is enforced natively by the platform via `allowedApplications`,
keeping it owned and versioned in this repo instead of in the shared APIM.

## Considered options

- **App-side JWT validation (PyJWT/JWKS in the API).** What Stage 1 first built: fetch the tenant's
  OIDC metadata/JWKS and validate `iss`/`aud`/signature/`exp` in code. **Rejected as the standing
  approach** — it puts crypto, JWKS-rotation, and issuer-matching burden in our code and duplicates a
  platform capability. The one thing worth keeping from it is the **`validated_token` seam**.
- **APIM `validate-jwt` policy (shared APIM).** **Rejected as the primary mechanism** — APIM is
  shared infrastructure owned by another team and is **not deployable from this repository**, so we
  cannot own, review, or version the policy here. APIM may still front the app for network/routing,
  but authentication must not depend on cross-team policy we do not control.
- **Container Apps built-in auth (chosen).** Deployable and versioned from this repo's Bicep;
  validates both **interactive (user)** and **client-credentials (machine)** tokens; and
  `allowedApplications` gives us the ADF `appid` allowlist natively, in our own infrastructure.

## Consequences

- **Reverses "the API validates tokens" (`authentication-and-access.md` §2, third bullet)** and the
  app-side validation implied by §4.3. Validation now happens in the platform; the app **trusts the
  injected principal**. The `validated_token` seam and every guard that reads claims through it
  (`require_admin`, `require_portal_user`, `require_extract_client`) are **unchanged in shape** — this
  is why the downstream stages of the implementation plan are not rewritten.
- **The `appid` allowlist moves from the shared APIM into our `allowedApplications`** (amends
  ADR-0006's "gated by an APIM `appid` allowlist" and §10). APIM remains only a network/routing
  front; the authoritative machine-caller allowlist is ours, in Bicep.
- **`allowedApplications` gates *every* caller by `azp`/`appid`, not only machine callers.**
  Container Apps built-in auth applies the allowlist to interactive (user) tokens too, so the SPA's
  client ID must be present or the platform returns `403` on every browser call; an **empty**
  `allowedApplications` denies **all** callers (it is not "allow all"). The Bicep therefore always
  includes the SPA client ID (`entraSpaClientId`) alongside any machine callers, and omits the
  authorization policy entirely when neither is configured (so platform-validated callers still reach
  the app, which authorizes by role). *Learned at the Stage 1/4 review: an empty allowlist locked the
  interactive SPA out with a platform `403` on every path, including the role-free `whoami`.*
- **Auth `401`s are emitted by the platform layer**, not the app — so auth-failure detection and
  alerting (§12 / plan Stage 10) point at **Container Apps auth logs**, not application logs.
- The provider configuration may require a **client secret / metadata reference** stored in the
  **existing Key Vault** (the app's user-assigned identity already holds *Key Vault Secrets User*);
  no new secret-management pattern is introduced. This is verified during Stage 1 implementation.
- Because the identity tenant is a **dedicated, standard workforce Entra tenant** (ADR-0005), the
  provider issuer must match the authority the SPA (plan Stage 4) signs in against
  (`login.microsoftonline.com`). This is a **config value**, confirmed with a real token at the
  Stage 1 review gate.
- The app keeps a **thin `validated_token`** that parses the injected principal — **no cryptography
  in our code** — so the app stays locally runnable and testable by injecting a fake principal at
  that seam (this replaces the old "local-dev bypass" question).

Full design in [authentication-and-access.md](../authentication-and-access.md); execution order in
[authentication-implementation-plan.md](../authentication-implementation-plan.md).
