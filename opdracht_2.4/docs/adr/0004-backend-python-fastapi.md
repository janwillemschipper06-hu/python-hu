# The backend Data API is built in Python with FastAPI

**Status:** accepted

The single backend Data API (architecture-design.md §5, api-design.md §9) is implemented in **Python 3.13+
using FastAPI**, served by uvicorn and packaged as a container image for the shared Container Apps
Environment. This matches the api-design.md wire contract, which is already expressed in Python
(`TypedDict`, `Literal`, `NotRequired`, `Page[T]`), and aligns the stack with the sister project
`9A-Ops-BI-Advanced-Monitoring` (same FastAPI + `pyodbc` + msodbcsql18 container pattern) that this deploy
is modelled on.

## Considered options

- **Python + FastAPI (chosen).** Matches the existing api-design.md Python contract, gives OpenAPI/Swagger
  for free, containerises to a small image, and pairs naturally with the EXECUTE-only stored-procedure
  data layer (ADR 0002) via `pyodbc`. Reuses the proven sister-repo tooling.
- **.NET / ASP.NET Core.** Rejected: the only reference to it lives in `docs/archive/inital-plan.md`, an
  explicitly superseded brainstorm, and it would diverge from both the api-design contract and the sister
  repo, doubling the platform patterns the team maintains.
- **Node.js.** Rejected: only ever used for the throwaway prototype (`docs/prototype-lessons-learned.md`);
  no production commitment and no fit with the Python-typed contract.

## Consequences

- The backend lives under `api/` (FastAPI app in `api/app`, tested with `pytest` + Starlette `TestClient`).
- Shared Python tooling (Black, Ruff, mypy strict) is configured in the repo-root `pyproject.toml`,
  matching the sister repo.
- Swapping the backend language later would mean rewriting the whole API surface — this is a load-bearing,
  hard-to-reverse choice, which is why it is recorded here.
