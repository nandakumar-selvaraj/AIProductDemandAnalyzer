# AI Product Demand Analyzer

Deployment readiness (Phase 5.17): [final audit](docs/deployment/PHASE_5_17_FINAL_VALIDATION.md), [manual provisioning](docs/deployment/UPCLOUD_MANUAL_PROVISIONING.md), [active delivery](docs/deployment/GITHUB_ACTIONS.md). Dedicated Terraform/S3/KMS guidance is historical and inactive.

Dedicated application deployment preparation: [architecture](docs/deployment/ARCHITECTURE.md),
[implementation report](docs/deployment/IMPLEMENTATION_REPORT.md), and
[validation and remaining gates](docs/deployment/ACCEPTANCE.md). All four dedicated runtime images
now pass the HIGH/CRITICAL security gate; see [remediation evidence](docs/deployment/IMAGE_SECURITY.md).
Provisioning and deployment require separate explicit approval.
Existing shared-portfolio tooling is documented in the [Phase 8A overview](docs/PHASE8A_INFRASTRUCTURE.md);
do not provision both infrastructure paths for this application.

Product demand analytics application with an Angular UI, a FastAPI backend, and PostgreSQL. The backend generates baseline forecasts for up to 30 days; the UI displays recorded sales, product catalogs, and completed forecast summaries.

## Projects

| Project | Stack | Documentation |
| --- | --- | --- |
| [Backend API](backend/) | Python 3.13+, FastAPI, SQLAlchemy, Alembic, PostgreSQL | [Backend setup and API guide](backend/README.md) |
| [Angular UI](ui/) | Angular 22.2, CoreUI Free, TypeScript, RxJS | [UI setup and development guide](ui/README.md) |

## Backend API

The API supports CSV sales ingestion, sales summaries, forecast generation and retrieval, forecast accuracy evaluation, demand trend recommendations, product analytics, dashboard summaries, and historical baseline backtesting.

Follow the [backend README](backend/README.md) to create the Python environment, configure PostgreSQL, install dependencies, and apply migrations. From `backend/`, activate your environment and start the API:

```powershell
python -m uvicorn app.main:app --reload
```

The API runs at <http://127.0.0.1:8000>; interactive documentation is at <http://127.0.0.1:8000/docs>.

## Angular UI

The UI provides a responsive CoreUI shell with Dashboard, Products, Demand Analysis, Forecasts, Reports, and AI Assistant navigation. Demand Analysis explores historical product/store sales with date filters, charts, and recorded observations. Forecasts supports run creation/history, paginated predictions, actuals evaluation, demand trends, and historical baseline backtesting. Reports generates scoped historical sales, predictions, evaluation and recommendation reports with CSV exports and bounded complete-export support. AI Assistant uses FastAPI and private Ollama inference to explain verified business evidence, with bounded conversations, selected context, sources, limitations and cancellation. See the [UI guide](ui/README.md) and [backend guide](backend/README.md) for setup, API contracts and security/deployment limitations.

Use Node.js 24.15 or later in the Node 24 line and npm 11. From the repository root, start the UI in another terminal:

```powershell
cd ui
npm ci
npm start
```

Open <http://localhost:4200>. The Angular development server forwards `/api` to the backend at `http://127.0.0.1:8000` through `ui/proxy.conf.json`. Restart the development server after changing proxy settings. The [UI README](ui/README.md) covers environment configuration, routes, folder structure, CoreUI licensing, and production hosting.

## Verification

Run frontend checks from `ui/`:

```powershell
npm test -- --watch=false
npm run build
```

Run backend checks from `backend/` with its Python environment active:

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

PostgreSQL integration tests require a dedicated test database; see the backend guide. GitHub Actions runs separate backend and UI jobs in [.github/workflows/backend-ci.yml](.github/workflows/backend-ci.yml).

## Repository layout

```text
backend/             FastAPI application, migrations, ingestion tools, and tests
ui/                  Angular application, API services, and frontend tests
.github/workflows/   Backend and UI continuous integration
.gitignore           Shared rules for secrets, dependencies, caches, and build output
```

Keep credentials in local backend configuration. Generated output, dependencies, and downloaded datasets are excluded by the root `.gitignore`.

## Dedicated UpCloud deployment preparation

The single-application deployment path is documented in
[docs/deployment/ARCHITECTURE.md](docs/deployment/ARCHITECTURE.md), with
[validation and live acceptance gates](docs/deployment/ACCEPTANCE.md) and the
[implementation report](docs/deployment/IMPLEMENTATION_REPORT.md).
It uses owner-executed manual provisioning, compose.prod.yml, deploy/single, GHCR and dedicated validation/publication/deployment workflows. Dedicated Terraform is historical/inactive.
Existing shared-portfolio deployment tooling remains available separately. Do not provision
both paths for this application. Cloud provisioning, production account creation and deployment
require separate explicit approval.
