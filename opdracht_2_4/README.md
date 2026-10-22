# Customer Onboarding Portal

Internal 9Altitudes portal for onboarding BI customers. This repository currently
contains the **minimum deploy** (walking skeleton): all Azure resources in Bicep,
a minimal FastAPI Data API, and a React/Vite Static Web App wired to it through
the shared APIM gateway — enough to run the full deploy pipeline and start the
development cycle.

## Layout

| Path | Contents |
|------|----------|
| `infra/` | Bicep templates (`main.bicep`, `resources.bicep`, `modules/`) and per-environment parameter files. |
| `api/` | FastAPI Data API (`app/`), tests, and `Dockerfile`. |
| `frontend/` | React + Vite Static Web App. |
| `.devops/` | Azure DevOps pipeline, stage templates, and scripts. |
| `docs/` | Architecture, API, and security design; ADRs; deploy guide. |

## Getting started

- **Deploy & pipeline setup:** [docs/deploy.md](docs/deploy.md)
- **Architecture:** [docs/architecture-design.md](docs/architecture-design.md)
- **Decisions:** [docs/adr/](docs/adr/)

### Run the API locally

```bash
python -m venv .venv
.venv/Scripts/pip install -r api/requirements.txt httpx pytest
.venv/Scripts/python -m pytest api/tests
.venv/Scripts/python -m uvicorn app.main:app --app-dir api --port 8001
```

### Run the frontend locally

```bash
cd frontend
npm install
npm run dev
```

## Build and test

```bash
# Bicep (no Azure connection required)
az bicep build --file infra/main.bicep

# API: lint, type-check, test
.venv/Scripts/python -m ruff check api
.venv/Scripts/python -m mypy api/app
.venv/Scripts/python -m pytest api/tests

# Frontend: type-check + build
cd frontend && npm run build
```

## Contribute

Work on `develop` (auto-deploys to `dev`); changes reach `prod` once merged to
`main`. See [docs/deploy.md](docs/deploy.md) for the pipeline and the variable
groups / service connection it expects.
