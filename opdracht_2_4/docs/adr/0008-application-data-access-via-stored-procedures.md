# Application code accesses the database only through stored procedures

**Status:** accepted

ADR 0002 makes the database *grant* boundary EXECUTE-only: the app's SQL principal has no
`SELECT`/`INSERT`/`UPDATE`/`DELETE` on base tables, only `EXECUTE` on stored procedures. This ADR
adds the matching **application-code convention** so the grant boundary is the default developer
path rather than only a server-side backstop:

- **The backend never composes ad-hoc SQL.** No `SELECT`/`INSERT`/`UPDATE`/`DELETE` (or other DML)
  strings appear in Python. Every data access — reads and writes alike — calls a named stored
  procedure.
- **Two thin data-access primitives share one execution core** (`app.core.db._run_procedure`);
  nothing else touches a cursor, builds SQL, or opens a connection directly:
  - `execute_procedure(proc, params) -> pandas.DataFrame` — the procedure's rows as a
    `pandas.DataFrame` (empty frame when it returns none), for callers that want tabular data.
  - `query_procedure(proc, model, params) -> list[Model]` — the same rows validated straight into a
    Pydantic model, for handing a result set to an API response without a hand-written column map.
  Both run a single stored procedure with bound parameters; services build their domain/response
  models from the result rather than composing SQL or holding connections themselves.
- **Procedures are allow-listed, parameters are always bound.** The primitive only runs procedures
  named in `ALLOWED_PROCS` and passes every argument as an ODBC parameter marker, so the one
  un-parameterizable token — the procedure name — is constrained to a known-safe set.
- **Failures are logged at the data layer.** `execute_procedure` logs the failing procedure name
  and re-raises, so a database error carries data-access context in the logs *before* the app's
  catch-all turns it into a JSON 500 (`app/core/errors.py`).

## Considered options

- **Direct parameterized queries in services (status quo skeleton).** A raw
  `SELECT ... FROM onboarding.Customer` lived in `services/customers.py`. Rejected as the ongoing
  pattern: it contradicts the ADR 0002 boundary (it only works while the app still holds
  `db_datareader`), and it scatters SQL and cursor handling across every service.
- **A thin query helper that runs arbitrary SQL strings.** Rejected: it keeps SQL in Python and
  leaves the door open to ad-hoc cross-table/cross-tenant queries — exactly what ADR 0002 removes
  at the grant layer.
- **Stored-procedure-only access through a single `_run_procedure` execution core with two typed
  primitives on top — `execute_procedure` → `DataFrame` and `query_procedure` → `list[Model]`
  (chosen).** The application is structurally unable to run ad-hoc SQL, mirrors the EXECUTE-only
  grant, centralizes connection/parameter/logging concerns in one place, and hands services either a
  DataFrame or validated Pydantic models — both trivial to consume.

## Consequences

- Every new read/write path is a **stored procedure + an `EXECUTE` grant + a call to
  `execute_procedure`** — a deliberate, reviewable step, consistent with ADR 0002.
- The app's SQL principal is granted `EXECUTE ON SCHEMA::onboarding` (no `db_datareader`,
  no direct table rights). The reference user script and the pipeline's `SqlUserSetup` job grant
  execute, not read.
- `pandas` becomes a backend runtime dependency (`api/requirements.txt`); `pyodbc` stays lazily
  imported inside `get_connection` so the test suite and tooling stay importable without the ODBC
  driver installed.
- Adding a data path means authoring the procedure, adding it to `ALLOWED_PROCS`, and granting
  `EXECUTE`.
- Stored procedures use `SET NOCOUNT ON` so their result set is what the primitive fetches.
- This is a load-bearing data-access convention; see `docs/architecture-design.md` §7.1 for the
  operational description.
