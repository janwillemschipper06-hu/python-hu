# Security Design

This document specifies the end-to-end security design for the Customer Onboarding Portal. It
builds on `docs/functional-design.md` (what the product does), `docs/architecture-design.md`
(hosting/networking/storage), and `docs/api-design.md` (API surface). The full **identity,
authorization, and secret-handling** design lives in `docs/authentication-and-access.md`; this
document is the security authority and §3–§6 below defer their detailed mechanics to it.

## 1. Threat model — assume breach

We adopt an explicit **assume-breach / zero-trust** posture. The designated crown-jewel asset is
the set of **customer-submitted secrets** (passwords, client secrets, API keys). The following are
treated as *partially untrusted*:

- External attackers and malicious/abusive customer users.
- A **compromised 9altitudes admin account**.
- The **cloud-platform / database-operator layer** itself.

Every decision below is justified against this model. The single most important consequence is
that **customer secrets are stored only as ciphertext under application-layer envelope encryption,
with the key-encryption key held in an HSM outside the database** (§3), so a database compromise
alone yields nothing usable.

### 1.1 The trusted app tier — accepted residual risk

The assume-breach model above lists the platform/DB-operator layer as untrusted, but one component
is unavoidably **trusted**: the backend Container App. At submit, admin-reveal, and pipeline-consume
time it sees secrets in **plaintext in memory**, and its managed identity can **wrap/unwrap the
key-encryption key (KEK)** in Key Vault. A fully compromised backend could therefore (i) harvest
secrets while they are in flight and (ii) decrypt stored ciphertext it is asked to serve. Stated
honestly: *the cloud platform and database are untrusted, but the app tier is trusted with in-flight
plaintext and unwrap capability.* This is the portal's principal residual crown-jewel exposure.

Mitigations the portal owns: no request-body logging on secret routes (§3.4), anomaly alerting on
secret reveal/decrypt/Key-Vault-unwrap volume (§10), **wrap/unwrap-only (no export)** on the KEK so
the key material never leaves the HSM (§9), daily and completion-based purge to minimize the volume
of decryptable secrets at rest (§3.3), and least standing privilege everywhere (§6). The remaining
exposure — a wholesale compromise of the running backend — is **documented and accepted as residual
risk, owner Nick Goossens** (see §18). It cannot be fully engineered away while the app must handle
plaintext to store and serve it.

## 2. Data classification

| Class | Examples | Where it lives | Protection |
|---|---|---|---|
| **Crown-jewel secrets** | passwords, client secrets, API keys | Azure SQL as **ciphertext** (§3) | Application-layer envelope encryption (AES-256-GCM per-value DEK wrapped by an HSM KEK in Key Vault); KEK never in the DB; separate schema behind EXECUTE-only procs; daily + completion purge |
| **Business data** (non-sensitive) | project/task structure & status, tenant IDs, workspace names, comments | Azure SQL | TDE at rest, TLS in transit, stored-proc access boundary (§6) |
| **Personal data** | customer user name, email, sign-up date | Azure SQL | As business data + deletion/anonymization path (§13) |
| **Security audit log** | who did what, when (incl. every secret reveal, value-free) | Append-only store (Log Analytics immutability + retention, §10) | Retained ~12 months, pseudonymized on deletion |

## 3. Customer secrets — stored in the database under envelope encryption

Customer secrets are **stored in Azure SQL as ciphertext**, protected by **application-layer
envelope encryption**. This **reverses ADR-0001** (write-through to an external secret vault): the
external vault and its separate operating team are no longer available, and the onboarding pipeline
must read secret values without an external dependency, so the portal now **owns the full secret
lifecycle**. See [ADR-0007](./adr/0007-secrets-in-database-envelope-encryption.md) and
`authentication-and-access.md` §11. Because the DB/operator layer remains untrusted (§1), secrets
are never stored in the clear and the wrapping key never lives in the database.

### 3.1 Encryption scheme

1. Customer submits a `secret` field over TLS (`PUT /api/v1/portal/tasks/{taskId}/fields/{fieldKey}`).
2. The backend holds the plaintext **only transiently in memory** and encrypts it with **AES-256-GCM**
   (authenticated encryption) using a **random per-value nonce**, under a random 256-bit **Data
   Encryption Key (DEK)**.
3. The DEK is **wrapped by the HSM-backed Key Encryption Key (KEK)** in **Key Vault Premium**; the
   backend's managed identity has **wrap/unwrap only, no export**. The plaintext KEK never leaves the
   HSM and is never present in the database.
4. Azure SQL stores **ciphertext + nonce + auth tag + wrapped DEK + key-version only**, in a separate
   table/schema, linked to the customer/task/field. The API always renders the value as
   `· submitted ·` unless it is explicitly revealed (§3.2).
5. Plaintext and the unwrapped DEK are discarded from memory.

A **vetted cryptography library** is used — no hand-rolled primitives. Replacing a secret
**overwrites in place**: only the current encrypted value is kept, so there is no plaintext (or
ciphertext) version history; value-free audit metadata is retained.

> A 1Password-style password-derived key (PBKDF2/SRP/zero-knowledge) is deliberately **not** used:
> those derive a key from a human master password for unattended-impossible decryption, whereas the
> onboarding pipeline must decrypt **unattended**. We match the cipher (AES-256-GCM), not the
> key-derivation model.

### 3.2 Retrieval — machine and admin reveal

- **Machine / pipeline retrieval.** The onboarding/provisioning pipeline calls an authenticated
  endpoint (`POST /api/v1/extract/secrets/consume`, certificate auth, **`Secret.Consume`** app role,
  §5.4); the **backend decrypts server-side** via Key Vault unwrap and returns the value over TLS.
  Consumers **never read the database directly**, so decryption is a single audited chokepoint. The
  reporting feeds (`Extract.Read`) never return secrets.
- **Admin reveal.** Any admin can reveal a stored secret, **including bulk reveal of many values at
  once** (an admin routinely needs ~20 for a hand-off). By decision there is **no step-up re-auth,
  no reason prompt, no one-time display, and no per-reveal high-signal alert** — the control is the
  admin's already-MFA'd session (§5.1) plus a **normal immutable audit entry per reveal** (§10) and
  **anomaly alerting on reveal volume**. The value stays viewable until the purge job runs, so a
  mis-keyed value is not destroyed prematurely. This is permissive and raises compromised-admin
  exposure — **accepted as residual risk R4** (§18).

### 3.3 Lifecycle & disposal

State machine: **`stored`** (encrypted, unused) → **`opened`** (revealed to an admin, or consumed by
the pipeline) → **`purged`** (ciphertext **crypto-erased**; only value-free audit metadata remains).

- A **daily** disposal job crypto-erases the ciphertext of `opened` secrets, after a short same-day
  grace so the admin can use the value.
- **Completion purge:** a secret is also disposed once its **onboarding task/project is complete**,
  even if it was never opened, so crown jewels never linger indefinitely.
- A secret still needed by the pipeline is marked **`pipeline-required`** and is **not** auto-purged
  on reveal — only on onboarding completion.

### 3.4 Transit & logging hardening (mandatory)

The secret transits `App Gateway/WAF → APIM → Container App → Azure SQL` (and back on reveal/consume):

- **No request-body logging** on secret **submit / reveal / consume** routes anywhere — APIM
  diagnostics, Container App stdout, and Application Insights MUST exclude request/response bodies for
  these routes, on **success and error paths alike**.
- **No secret value ever appears in any log or trace.**
- All hops are **TLS 1.2+ with certificate validation**.

## 4. Encryption

- **In transit**: TLS 1.2+ enforced on every hop (client→WAF→APIM→Container App→SQL/Key Vault).
- **At rest**:
  - **Crown-jewel secrets** are protected by **application-layer envelope encryption** (AES-256-GCM
    per-value DEK wrapped by an HSM KEK in Key Vault Premium, §3) — independent of and stronger than
    database-native encryption.
  - The remaining (non-sensitive) database is protected by Azure SQL **Transparent Data Encryption
    (TDE)**.
- Application-layer cryptography now exists **only** for secret storage and uses a **vetted library**,
  never hand-rolled primitives (ADR-0007 supersedes ADR-0001's write-through model).

## 5. Identity & authentication

All human sign-in runs through a **dedicated workforce Entra identity tenant** (separate from both the
corporate directory and the application's resource tenant): **every human is a B2B guest** — admins are
guested in from the **9altitudes corporate tenant** (their home directory), customer users from their
own organizations — and **self-service sign-up is disabled**, so access is **invite-only** from the
portal admin view. Full design in `authentication-and-access.md` §2–§3;
[ADR-0005](./adr/0005-dedicated-workforce-tenant-invite-only-access.md).

### 5.1 Admins (B2B guests, home: corporate tenant)

- Admin authority is a **direct `Admin` app-role assignment** on the user (an `appRoleAssignment` on
  the API app; **no group, no Entra ID P1** — see
  [ADR-0011](./adr/0011-admin-app-role-assigned-directly-to-users.md)) in the identity tenant, carried
  in the **signed token** — never a database flag (a DB compromise cannot mint an admin). The
  assignment is managed **from the portal** via Microsoft Graph; the first admin is bootstrapped (and
  recovered) by assigning the role in the `cop-api-dev` enterprise app.
- Admins authenticate against the **corporate tenant**, whose **Conditional Access** requires
  **phishing-resistant authentication strength** (Microsoft Authenticator device-bound passkey or
  Windows Hello for Business — no hardware purchase required); the identity tenant **honours this via
  cross-tenant inbound MFA trust**. Legacy authentication blocked. Admin browser session is
  **non-persistent**.

### 5.2 Customer users (B2B guests, invite-only)

- **Self-service sign-up is off.** A customer user exists only by an admin **Invite** (one atomic
  action: Graph B2B invitation + `Users` row + `UserCustomers` link; §6, `authentication-and-access.md`
  §3). No app-generated bearer token is emailed — access derives only from a verified Entra identity
  plus our own rows; a leaked Entra redemption link grants only guest directory status, not portal
  access.
- **App-based MFA is required for all customer users** — Microsoft Authenticator (or a device-bound
  passkey), enforced by Conditional Access in our tenant with cross-tenant inbound MFA trust. **SMS
  and email OTP are not accepted** as an MFA factor (phishable / SIM-swappable). Email verification
  remains mandatory at sign-up but is not an MFA factor.
- A guest sees **nothing** until an admin links them to a customer (`UserCustomers`). Because sign-up
  is invite-only, the open-registration bot/abuse surface no longer exists; the WAF bot rules (§7)
  remain as defence in depth.

### 5.3 Sessions & tokens

- Entra default **short-lived access tokens** are kept (not extended).
- Conditional Access **sign-in frequency**: ~8h for admins, ~24h for customers.
- **Continuous Access Evaluation (CAE)** is enabled so revocation (disabled user, risk detected,
  access unlinked, admin demoted) takes near-real-time effect rather than waiting for token expiry.

### 5.4 ADF / reporting service principal

- ADF authenticates as a **separate client app registration** using a **certificate**
  (client-credentials), because ADF **cannot** use workload-identity federation for REST/Web linked
  services and managed identity is unreliable against a custom-API audience across tenants. The
  certificate is **Key-Vault-stored and rotated on a schedule**; a client secret is a documented
  fallback. **This reverses the earlier "no client secret or certificate stored anywhere" stance** —
  see [ADR-0006](./adr/0006-three-router-authorization-and-adf-certificate.md) and residual risk R5.
- The **reporting** identity is granted a dedicated least-privilege app role **`Extract.Read`** that
  can reach only the `/api/v1/extract/*` router — never admin, customer, or write routes. The
  **onboarding/provisioning pipeline** that reads secrets is a **distinct machine identity** holding
  a separate **`Secret.Consume`** role for `POST /api/v1/extract/secrets/consume` only.
- APIM additionally validates the caller's `appid`/`oid` against an allowlist. The reporting feeds
  never carry secret values.

### 5.5 Browser session hardening (React SPA)

The admin and customer views are a React SPA calling the API through APIM. The following are
mandatory:

- **Token placement.** The **access token lives in memory only** — never in `localStorage` or
  `sessionStorage`. The **refresh token is held in an `HttpOnly`, `Secure`, `SameSite=Strict`
  cookie**, and **CSRF protection** (anti-forgery token / origin checks) is applied to every
  state-changing request that relies on that cookie.
- **Content-Security-Policy.** A **strict CSP** (default-src 'self'; no inline/eval script; explicit
  allowlist for APIM origin and required Azure endpoints only), alongside `Strict-Transport-Security`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and a
  restrictive `Permissions-Policy`.
- **Output-encoding of customer-authored content.** All customer-supplied strings — task comments and
  text-field values — are rendered as **inert text**, using React's default escaping, with **no
  `dangerouslySetInnerHTML`** and **no HTML/Markdown rendering** of customer input anywhere, most
  importantly in the **admin** UI (where a stored-XSS payload could otherwise pivot an admin session).
  Customer input is validated server-side for length and character set on submission. This is the
  authoritative rule referenced by `functional-design.md` §8.

## 6. Authorization & tenant isolation

Authorization is enforced at **two layers**: mandatory **router-level guards** in the app, and the
**EXECUTE-only stored-procedure boundary** in the database (see ADR-0002 and
[ADR-0006](./adr/0006-three-router-authorization-and-adf-certificate.md)).

- **Three routers, each with a mandatory router-level guard** (deny-by-default), so no endpoint can be
  accidentally left under-protected:
  - **`/api/v1/admin/*`** — requires the `Admin` app-role claim; all-scope.
  - **`/api/v1/portal/*`** — a **customer-scoped guest** *or* an **admin** acting within the customer
    named in the request; a plain identity that is neither is rejected.
  - **`/api/v1/extract/*`** — machine clients only (`Extract.Read` for reporting, `Secret.Consume`
    for the provisioning pipeline; no user context, APIM `appid` allowlist).
  A **single API app registration** is the audience for all three; token-layer separation comes from
  distinct app roles.
- The Container App validates the Entra JWT (signature, issuer, audience, expiry) and derives the user
  (`oid`) and — for customer users — their allowed `customerId`s from `UserCustomers` (admins are
  all-scope via the role claim).
- **All data access goes through parameterized stored procedures** that enforce the `UserCustomers`
  join (and task-assignment checks for writes) inside the database. The app's SQL principal is granted
  **`EXECUTE` on those procedures only — no `SELECT`/`INSERT`/`UPDATE`/`DELETE` on base tables** (the
  secrets schema included), so the app *physically cannot* run a raw cross-tenant query even with a
  code bug.
- All externally referenced identifiers are **GUIDs** (non-enumerable), mitigating IDOR.
- Authorization is **deny-by-default**: any request whose object cannot be tied to the caller's scope
  is rejected. Client-supplied IDs are never trusted for authorization.

## 7. Network

- **Edge**: the existing shared **Application Gateway WAF v2** fronts the shared APIM, running the
  **OWASP core rule set in Prevention mode** with managed bot rules; this project's routes ride it.
  Azure DDoS Protection on the gateway public IP is confirmed. No new edge is provisioned.
- **APIM** performs JWT validation, per-caller **rate-limiting/quotas**, and IP policy for this
  project's routes/products.
- **Backend**: the Container App ingress is **internal-only** (no public path), reached privately by
  APIM over the existing VNet integration.
- **Azure SQL**: reached over a **private endpoint** with **public network access disabled**,
  **Entra-only authentication (SQL logins/local auth disabled)**, and **TLS 1.2+** enforced. The
  Container App connects via its managed identity — no connection-string password anywhere.
  (Shared-server caveat: reconcile with the existing shared SQL Server's posture during
  implementation.)

## 8. Egress control

The Container App runs in a **shared** Container Apps Environment, so a hard, per-app deny-by-default
FQDN allowlist is **not reliably enforceable** at this app's boundary. Egress is controlled by
**monitoring and anomaly alerting** instead of a hard allowlist:

- The backend's legitimate outbound destinations are a small, known set — Entra login
  (`login.microsoftonline.com`), Microsoft Graph (`graph.microsoft.com`, for invite/group
  management), Azure Key Vault, and Azure SQL.
- Outbound traffic is **logged and alerted on anomaly**: connections to destinations outside the known
  set, or unusual **Key Vault unwrap / secret-reveal** volume, raise alerts (§10).
- Because crown-jewel secrets are now **at rest as ciphertext** in SQL and the KEK is unwrap-only in
  the HSM, the exfiltration value of a compromised container is the **in-flight plaintext** and its
  **unwrap capability** (addressed in §1.1, §9), neither of which a hard FQDN allowlist would prevent.

> If a **dedicated** CAE is ever provisioned for this portal, upgrade this to a hard deny-by-default
> FQDN allowlist (Entra login, Graph, Key Vault, SQL only).

## 9. Application configuration & secrets

- **Managed identity is used for every Azure resource** (SQL, Key Vault, ACR image pull).
- The security-critical stored key material is:
  - The **HSM-backed KEK in Key Vault Premium** that wraps every secret DEK. The backend's managed
    identity holds **wrap/unwrap only (no export)**; the key material never leaves the HSM, never
    appears in environment variables, image layers, or the repository, and is subject to a defined
    **rotation/re-wrap** procedure.
  - The **ADF client certificate** (§5.4), Key-Vault-stored and rotated, used only by the reporting
    identity.
- No other standing application credential exists; there is no connection-string password and no
  external-vault write key (removed with ADR-0001).

## 10. Logging, monitoring & detection

- All logs (App Gateway/WAF, APIM, Container App, Key Vault access, SQL audit, Entra sign-in/audit)
  ship to a central **Log Analytics** workspace.
- **Anomaly-based alert rules** (not one alert per action): unusual **secret reveal / decrypt / Key
  Vault unwrap volume**, off-hours admin bursts, spikes in authentication failures or authorization
  denials, impossible-travel.
- **High-signal alert on every user→customer link creation** (the admin **Invite**/link action). This
  single action is the entire gate for who can see a customer's data, and the threat model treats a
  compromised admin as untrusted, so each link creation raises an immediate alert on top of the audit
  entry. (Four-eyes / dual-control on this action was **considered and deliberately deferred as
  disproportionate**; alerting + the append-only audit trail is the accepted detective control.)
- **Secret reveals are audited but not individually alerted** — the value-free per-reveal audit entry
  plus the anomaly alert on reveal *volume* is the compensating detective control for the permissive
  bulk-reveal design (§3.2). Every role change (`Admin` app-role assignment) is also audited.
- The application **audit trail** (who did what to which project/task/secret) is an **append-only
  table the app principal cannot UPDATE or DELETE**. Immutability and the ~12-month retention window
  are provided by **Log Analytics immutability/retention** on the shipped logs.
- **No secret values and no request bodies ever appear in any log** (§3.4).
- **Microsoft Sentinel** (cloud SIEM) is a documented, recommended future add-on for full
  correlation/investigation once volume justifies it.

## 11. Retention & data lifecycle

- **Crown-jewel secrets are minimized, not retained indefinitely.** Each secret is disposed
  (crypto-erased) by the **daily purge** once opened, and by **completion purge** when its onboarding
  task/project completes even if never opened (§3.3). This replaces the earlier "retain indefinitely
  because no secrets are in the DB" stance, which no longer holds now that secrets live in Azure SQL.
- **Portal business data is retained indefinitely** for clean historical/audit continuity; with
  secrets purged, the retained data is non-sensitive.
- **Security audit log** is retained **~12 months** in its immutable store, then aged out.

## 12. Vulnerability & patch management

- **Microsoft Defender for Cloud** plans enabled on the crown-jewel path: **Defender for Containers**
  (high-value on the crown-jewel path); **Defender for Azure SQL** reused if the shared server already
  has it; and — now that Key Vault holds the **crown-jewel wrapping KEK** and the ADF certificate —
  **Defender for Key Vault is enabled** for anomalous-access/unwrap detection (the previous "one
  low-value secret" rationale for omitting it no longer applies).
- Automated **dependency-update PRs** are raised by GitHub Advanced Security dependency scanning
  (§15); base images are **pinned by digest** and bumped by automation.
- Container is **rebuilt and redeployed** when base-image CVEs appear.
- **Patch SLA**: critical within 7 days, high within 30 days.

## 13. Data deletion & anonymization

- **Data deletion**: a documented, admin-driven procedure deletes or anonymizes a specific person's
  `User` row (and unlinks them, removing any `Admin` app-role assignment) on request. Their name in
  comments is handled as part of the same procedure.
- The **security audit log is retained but pseudonymized** on deletion (opaque user ID instead of
  name) so the security/forensic record survives while personal data is removed.
- **Reporting extraction minimizes personal data.** The `/extract/notifications` feed
  (`api-design.md`) does **not** replicate raw recipient email addresses / Teams identifiers into the
  data warehouse; it emits only the opaque `recipientUserId`, so personal contact data does not cross
  into the DWH/Power BI boundary.

## 14. Incident response

- A concise **IR runbook** defines roles and contacts.
- **Playbooks** matched to the crown-jewel design:
  - **(a) Suspected secret / KEK compromise** — rotate the Key Vault KEK and **re-wrap** DEKs (or
    force secret re-submission), review Key Vault unwrap logs and the secret-reveal audit trail,
    notify affected customers, and purge exposed secrets.
  - **(b) Suspected secret exposure in transit/logs** — verify no body logging regressed on
    submit/reveal/consume routes, rotate affected secrets via re-submission, assess blast radius.
  - **(c) Suspected admin-account compromise** — remove the `Admin` app-role assignment (CAE cuts access
    near-real-time), review the reveal/link audit trail for the window, rotate any secrets bulk-revealed
    during it.
- An **annual tabletop test** exercises the runbook.

## 15. Secure development & testing

- CI (Azure DevOps Pipelines) uses a **single, consolidated scanner stack: GitHub Advanced Security
  for Azure DevOps** — **CodeQL** (SAST), **secret scanning** (blocks the ADF certificate, KEK
  references, or any credential being committed), and **dependency scanning** (vulnerable dependency
  alerts + update PRs). One SAST + one secret scanner + one dependency scanner avoids triage fatigue.
- **Branch protection** on `main` with required PR reviews and status checks; **signed commits**.
- **Deployment via OIDC workload-identity federation** — the pipeline receives short-lived Azure
  tokens; no service-principal secret is stored.
- The **container image vulnerability scan blocks the pipeline** on high/critical findings.
- A **third-party penetration test** is commissioned **before go-live** (focused on the auth,
  tenant-isolation, and secret storage/reveal paths) with periodic retests.
- **DAST** is a documented future add-on.

## 16. Backup & disaster recovery

- **Azure SQL point-in-time restore (PITR)** is the sole database backup mechanism, retention set to
  **14 days**. This now also covers the **encrypted secret ciphertext**; a restore recovers ciphertext
  only, which is worthless without the KEK — so restoring the database never re-exposes purged
  plaintext.
- **Geo-redundant backup storage** is confirmed enabled for regional resilience — no active
  geo-replication and no long-term retention.
- **KEK availability is the disaster-recovery critical path for secrets.** Key Vault Premium
  **soft-delete and purge-protection are enabled**, and the KEK is covered by Key Vault's backup so the
  wrapping key cannot be lost independently of the ciphertext (losing the KEK would render every stored
  secret unrecoverable).
- Documented targets: **RPO ≤ 1 hour, RTO ≤ 24 hours**, with an **annual restore test** that includes
  a KEK-unwrap check.

## 17. Open items for implementation

- Confirm DDoS Protection status on the shared App Gateway public IP.
- Reconcile "SQL public access disabled / Entra-only / private endpoint" with the **shared** SQL
  Server's current server-wide posture (may already be enforced).
- Egress control on the shared CAE is resolved as **monitoring + anomaly alerting** (§8); revisit
  toward a hard FQDN allowlist only if a dedicated CAE is provisioned.
- Pin the exact least-privilege **Microsoft Graph** permission for portal-driven invite/group
  management (group-owner / administrative-unit scope rather than tenant-wide).
- Confirm the ADF authentication path (certificate vs. fallback client secret) with the reporting team.

## 18. Governance & accepted residual risks (NIS2 Art. 20)

NIS2 Article 20 requires management-body accountability and security-awareness training, in addition
to the technical Article 21 measures specified above.

- **Accountable owner**: **Nick Goossens** owns the portal's security risk posture — approval of the
  design, sign-off of the accepted residual risks below, and the maintenance of the risk register.
- **Risk register**: the residual risks below are recorded in a maintained risk register, reviewed
  periodically.
- **Security-awareness training**: staff with admin access complete security-awareness training on an
  **annual** cadence.

### 18.1 Accepted residual risks

| # | Residual risk | Why accepted / compensating control | Owner |
|---|---|---|---|
| R1 | **Compromised backend Container App** can harvest in-flight plaintext secrets and unwrap stored ciphertext via the KEK (§1.1). | Unavoidable while the app must handle plaintext to store and serve it; compensated by no-body-logging, reveal/unwrap anomaly alerting, wrap/unwrap-only (no export) KEK, daily + completion purge to minimize decryptable volume, and least privilege. | Nick Goossens |
| R2 | **A fully-malicious all-scope admin** can unilaterally link an attacker-controlled user to any customer (§10). | Four-eyes deferred as disproportionate; compensated by a high-signal alert on every link creation + the append-only audit trail (detective control). | Nick Goossens |
| R4 | **Crown-jewel secrets now live in our database** (reversal of ADR-0001), and any admin can **bulk-reveal** them with only session MFA + audit (§3.2). | Envelope encryption with an HSM KEK the DB never holds; separate schema behind EXECUTE-only procs; daily + completion purge (minimization); immutable per-reveal audit + anomaly alerting on reveal volume; strong admin MFA/CA. Accepted as the cost of owning the secret lifecycle without an external vault. | Nick Goossens |
| R5 | **ADF holds a standing certificate** (reversal of §5.4's "no stored credential"). | Certificate (not a shared string), Key-Vault-stored and rotated, scoped to `Extract.Read`, gated by an APIM `appid` allowlist; reporting extract feeds carry no secrets (secret retrieval is a separate `Secret.Consume` identity). | Nick Goossens |
