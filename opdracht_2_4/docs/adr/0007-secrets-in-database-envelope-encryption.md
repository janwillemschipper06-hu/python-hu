# Customer secrets are stored in our database under application-layer envelope encryption

**Status:** accepted (supersedes ADR-0001; amended by ADR-0009)

> **Amended by [ADR-0009](./0009-no-machine-secret-consumer.md).** There is no machine
> secret-consumer / provisioning pipeline; **admin reveal is the sole secret read path.** Storing
> secrets in our database under envelope encryption still stands (the external vault is unavailable),
> but the "the pipeline must read values unattended" justification below no longer applies, and the
> `pipeline-required` flag / `pipeline-consumed` lifecycle trigger are removed.

The external secret vault and its separate operating team are no longer available, and the
onboarding pipeline must read secret values without an external dependency, so **the portal now owns
the full secret lifecycle and stores secrets in Azure SQL**. Because the DB/operator layer remains
untrusted, each secret value is protected with **application-layer envelope encryption**:
**AES-256-GCM** with a random per-value nonce under a random **Data Encryption Key (DEK)**, the DEK
**wrapped by an HSM-backed Key Encryption Key (KEK) in Key Vault Premium** that the backend's managed
identity can only **wrap/unwrap (no export)**. The database holds ciphertext only; a database
compromise alone yields nothing usable. This **supersedes**
[ADR-0001](./0001-secrets-written-through-to-external-vault.md).

## Considered options

- **Write-through to an external secret vault (ADR-0001).** No longer viable: the separate
  secrets-management team/vault is unavailable, and the pipeline needs first-party read access.
- **Store plaintext (or DB-native/TDE-only encryption).** Rejected: TDE protects files at rest, not
  against the DB operator or an application-level read; crown-jewel material would be exposed to the
  untrusted layer.
- **1Password-style password-derived key (PBKDF2 / SRP / zero-knowledge).** Rejected: those derive a
  key from a **human master password** for unattended-impossible decryption; here the **pipeline must
  decrypt unattended**, so the key must be a machine-held KEK. We match the *cipher* (AES-256-GCM),
  not the key-derivation model.
- **Application-layer envelope encryption with an HSM KEK in Key Vault (chosen).** Uses a vetted
  crypto library (answering ADR-0001's "custom cryptography" objection) and keeps the KEK out of the
  database.

## Consequences

- Secrets live in a **separate table/schema** reached only via **EXECUTE-only stored procedures**
  (ADR-0002); the backend decrypts server-side via Key Vault unwrap. Consumers never read the DB
  directly.
- **Admin reveal is permissive by decision:** any admin can reveal, **including bulk** (~20 at once),
  with **no step-up, no reason prompt, no one-time display, and no per-reveal alert** — the control
  is the admin's MFA'd session plus an **immutable per-reveal audit entry** and anomaly alerting on
  reveal/unwrap *volume*. This raises compromised-admin exposure — **accepted** (residual risk R4).
- **Lifecycle:** `stored` → `opened` (revealed or pipeline-consumed) → `purged` (ciphertext
  crypto-erased, value-free audit kept). A **daily** job purges opened secrets (short grace);
  **completion purge** disposes a secret when its onboarding task/project completes even if never
  opened; `pipeline-required` secrets are purged only on completion. Replacement **overwrites in
  place** (no plaintext history). This reverses `security-design.md` §11's "retained indefinitely".
- **No request-body logging** on submit/reveal/consume routes remains a hard control; no secret value
  ever appears in a log or trace.
- Full design in [authentication-and-access.md](../authentication-and-access.md) §11.
