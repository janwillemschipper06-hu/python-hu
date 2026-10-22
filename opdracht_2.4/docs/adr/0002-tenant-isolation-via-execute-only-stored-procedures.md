# Tenant isolation is enforced by EXECUTE-only stored procedures, not application code alone

**Status:** accepted

Customer users must only ever see their own customer's project(s). The Container App connects to
Azure SQL with a single managed identity, so login-based Row-Level Security cannot distinguish
end users. Instead, **all data access goes through parameterized stored procedures that enforce the
`UserCustomers` join**, and the app's SQL principal is granted **`EXECUTE` on those procedures only
— no direct `SELECT`/`INSERT`/`UPDATE`/`DELETE` on base tables**. The caller's scope is derived
from the validated Entra JWT (`oid` → allowed `customerId`s; admins all-scope via a role claim),
and all external identifiers are GUIDs.

## Considered options

- **Application-layer authorization only** (middleware checks, direct parameterized queries).
  Rejected as the sole boundary: a single missing `WHERE customerId = ...` in app code could
  cross-tenant leak.
- **SESSION_CONTEXT + Row-Level Security.** Rejected here: because the same application code sets
  the session context, RLS only guards against a query-writing bug, not a genuine trust boundary,
  and adds complexity for modest value.
- **EXECUTE-only stored-procedure boundary (chosen).** The authorization filter lives in the
  database and the app is physically unable to run a raw cross-tenant query, even with a code bug.

## Consequences

- The data-access layer is stored-procedure-based; ad-hoc queries from the app are not possible by
  grant.
- New read/write paths require a stored procedure plus an `EXECUTE` grant, which is a deliberate,
  reviewable step.
- Combined with GUID identifiers and deny-by-default checks, this closes the primary IDOR /
  cross-tenant risk at the strongest available layer for this architecture.
