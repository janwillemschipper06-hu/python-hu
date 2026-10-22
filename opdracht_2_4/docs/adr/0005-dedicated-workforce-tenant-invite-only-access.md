# Human access uses a dedicated workforce Entra tenant, invite-only, with admin authority anchored in Entra

**Status:** accepted

> **Amendment ([ADR-0011](./0011-admin-app-role-assigned-directly-to-users.md)):** the admin-authority
> **mechanism** below — a `Portal-Admins` **security group** mapped to the `Admin` app role — is
> **superseded**. Assigning an app role to a *group* needs Entra ID **P1**, which we don't have and
> don't want to require. Admin authority is now a **direct `Admin` app-role assignment on the user**
> (an `appRoleAssignment` on the API service principal), managed from the portal via Graph. The rest
> of this ADR stands: dedicated workforce tenant, B2B guests only, invite-only, and admin anchored in
> the **signed `Admin` app-role claim** (never a DB flag). Read every "`Portal-Admins` membership"
> below as "the user's `Admin` app-role assignment", and the "group owner" bootstrap as "assign your
> user the `Admin` app role in the `cop-api-dev` enterprise app".

All human sign-in (admins and customers) runs through a **dedicated, standard workforce Entra
tenant** — separate from both the 9altitudes corporate directory and the tenant hosting the
application's Azure resources. **"Dedicated" denotes workforce-identity isolation, not single-app
exclusivity: the tenant hosts several 9altitudes-hosted applications, this portal among them**, so
sign-in security policies are **scoped to this portal's app registrations** rather than applied
tenant-wide (see [authentication-and-access.md](../authentication-and-access.md) §5). **Every human
is a B2B guest** (admins are guested in from the 9altitudes corporate tenant, customers from their own
organizations), **there are no member humans**, and **self-service sign-up is disabled**: a person can
sign in only after being
**invited from the portal admin view**. Admin authority is not a database flag — it is membership of
an Entra **`Portal-Admins` security group** mapped to an **`Admin` app role**, so authority is
carried in the **signed token** and cannot be granted by a database compromise. The portal manages
that group's membership via Microsoft Graph so admins are provisioned from the portal, never the
Entra admin center. This **reverses** the earlier Entra External ID (CIAM) + open self-registration
design.

## Considered options

- **Entra External ID (CIAM) tenant with open self-registration (previous design).** Rejected: the
  portal handles a small, known set of invited customer contacts; open sign-up is unnecessary
  attack surface and cannot express "invite-only by an admin".
- **Single corporate/app tenant for everyone.** Rejected: mixes external customers into the
  corporate directory and couples identity administration to infrastructure administration.
- **Admin flag stored in the `Users` table.** Rejected: the DB/operator is untrusted (ADR-0002); a
  SQL bug or operator could mint an admin. Authority must live in the signed token.
- **App-generated invite link/token that grants access.** Rejected: a leaked link would let anyone
  impersonate the invitee. Access derives only from a verified Entra identity plus our own
  `Users`/`UserCustomers` rows; the Entra B2B redemption link confers only guest directory status,
  not portal access.
- **Dedicated workforce tenant, invite-only, admin anchored in `Portal-Admins`/`Admin` app role
  (chosen).**

## Consequences

- One admin **Invite** action atomically issues a Graph B2B invitation, creates/reuses a `Users`
  row, and provisions scope (`UserCustomers` links for a user, or `Portal-Admins` membership for an
  admin). Re-inviting an existing email never duplicates the identity.
- The `Users.role` column may mirror the role for display but is **never** authoritative for admin.
- **Jan Willem Schipper is the `Portal-Admins` group owner** to bootstrap the first admin and as a
  manual fallback; the portal's Graph permission is scoped as tightly as possible (group-owner /
  administrative-unit rather than tenant-wide).
- Conditional Access in the identity tenant enforces MFA (phishing-resistant for admins, app-based
  for guests; no SMS/email OTP factor) and CAE for near-real-time de-provisioning. Because the tenant
  hosts multiple apps, these policies are **scoped to this portal's app registrations**, not applied
  tenant-wide.
- Full design in [authentication-and-access.md](../authentication-and-access.md).
