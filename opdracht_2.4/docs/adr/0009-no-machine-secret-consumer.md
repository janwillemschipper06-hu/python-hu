# No machine secret-consumer — admin reveal is the only secret read path

**Status:** accepted (amends ADR-0006 and ADR-0007)

The portal is a customer↔admin information-exchange tool: customers submit secrets and admins
retrieve them by hand. There is **no automated "onboarding/provisioning pipeline" that reads
secrets, and there never will be.** We therefore remove the **`Secret.Consume`** app role, its
**pipeline client app registration**, and the **`POST /api/v1/extract/secrets/consume`** endpoint;
**admin reveal becomes the sole secret read path.** This **amends** ADR-0006 (the `/extract/*` router
now serves only the `Extract.Read` reporting identity) and ADR-0007 (secrets still live in our
database under envelope encryption — that stands, because the external vault is unavailable and
admins need a first-party, audited reveal path — but its "the pipeline must read values unattended"
justification no longer applies).

## Consequences

- **ADR-0007 stands, narrowed.** Secrets remain in Azure SQL under application-layer envelope
  encryption reached via EXECUTE-only stored procedures; the backend decrypts server-side for
  **admin reveal only**. The load-bearing reason is now "the external vault is unavailable and admins
  need a first-party, audited reveal path," not "a machine must decrypt unattended."
- **Secret lifecycle simplifies** to `stored → opened (revealed to an admin) → purged`. The
  `pipeline-consumed` trigger and the `pipeline-required` flag are removed; the daily purge (opened
  secrets) and completion purge (on onboarding completion) are unchanged.
- **The `/extract/*` router survives for reporting only** (`Extract.Read`, ADF certificate client,
  Container Apps built-in auth `appid` allowlist — see
  [ADR-0010](./0010-platform-authentication-via-container-apps-built-in-auth.md)) — see ADR-0006.
  `require_extract_client` accepts only `Extract.Read`.
- **Residual risk R4 is unchanged** (a compromised admin can still bulk-reveal). Removing the machine
  secret-retrieval identity slightly shrinks the attack surface.
- Stale references to the pipeline / `Secret.Consume` remain in `security-design.md`,
  `api-design.md`, `functional-design.md`, and `architecture-design.md`; those already defer to
  `authentication-and-access.md` (updated alongside this ADR) and should be swept when next touched.
- Full design in [authentication-and-access.md](../authentication-and-access.md) §10–§11.
