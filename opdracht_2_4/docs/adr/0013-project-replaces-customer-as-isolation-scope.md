# Project replaces Customer as the isolation and assignment scope

**Status:** accepted (supersedes the customer-scoped model in ADR-0002 and the `UserCustomers` join in
`docs/authentication-and-access.md`; the EXECUTE-only stored-procedure mechanism of ADR-0002/0008 is unchanged)

The portal's unit of work becomes the **Project** (an installation or migration), previously tracked
outside the portal in a Microsoft Forms + Power Automate + SQL flow. A **Customer** is now only a
read-only FO record, exposed as the external table `ext.Customer`, that a Project points to.

## Decisions

- **Users are assigned to Projects, never to Customers.** `onboarding.ProjectUsers(ProjectId, UserId)`
  replaces `UserCustomers` as the only source of a customer user's scope, enforced inside the
  EXECUTE-only stored procedures.
- **Customers are not managed by the portal.** `onboarding.Customer`, `UserCustomers`, their stored
  procedures, the `customers` API module and the customer UI are removed. No customer endpoints exist;
  customers are read only to fill a Project's customer dropdown and to display its name.
- **Staff visibility:** Admin and PM see every Project except another author's `Draft`. Customer users
  see only assigned Projects that are `Approved` or later.
- **Access is granted at Approve, atomically:** one Admin action creates the Freshdesk request ticket,
  issues the Entra B2B invites and assigns the users, or none of it. A failure leaves the Project
  `Requested` (blocking, never silent).

## Why

- The old isolation boundary (Customer) no longer matches how work is run: one customer has many
  installations and migrations, and each has its own people.
- Making the Project the boundary means a bug can never expose one project's data to another project's
  users, and the customer table needs no write path or privilege.
- The trade-off: a person working on several Projects needs one assignment per Project, and cross-project
  customer views need an extra aggregation by customer id.

## Consequences

- Hard to reverse once Project data and assignments exist, hence this ADR.
- All docs that say "customer-scoped" (security, authentication-and-access, api, functional) must be
  updated in the implementation stage that removes the customer module.
- See `docs/projects-design.md` and `docs/projects-implementation-plan.md`.
