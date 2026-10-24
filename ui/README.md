# AI Product Demand Analyzer UI

Standalone Angular frontend for the AI Product Demand Analyzer, with CoreUI Free components and styles. Dashboard and Products display data from the existing FastAPI service.

## Stack and prerequisites

- Angular 22.2 with standalone components and lazy routes.
- CoreUI Angular 5.7.37 and CoreUI CSS 5.9.1, compatible with Angular 22.2.
- TypeScript 6, RxJS 7, Angular CLI, and Vitest.
- Node.js 24.15 or later in the Node 24 line; npm 11 (`packageManager` specifies npm 11.19.0).
- A running backend and configured PostgreSQL database for API data. See the [backend guide](../backend/README.md).

The repository uses npm and the committed `package-lock.json` for reproducible installs.

## Install and run on Windows

From the repository root:

```powershell
cd ui
npm ci
npm start
```

Open <http://localhost:4200>. Start the backend separately from `backend/`, with its Python environment active:

```powershell
python -m uvicorn app.main:app --reload
```

The backend listens at <http://127.0.0.1:8000>. Dashboard and Products show loading, empty, and error states according to API responses. No demonstration analytics are substituted when data is unavailable.

## Commands

Run these commands from `ui/`:

| Command | Purpose |
| --- | --- |
| `npm start` | Start the Angular development server with the API proxy |
| `npm run build` | Create an optimized production build in `dist/ui` |
| `npm run watch` | Rebuild development output when files change |
| `npm test` | Run tests using the existing Angular CLI/Vitest setup |
| `npm test -- --watch=false` | Run tests once for local verification or CI |
| `npm run lint` | Lint TypeScript, external templates, and inline templates; warnings fail verification |

ESLint 10, angular-eslint 22, and typescript-eslint 8 support the existing Angular 22 / TypeScript 6 toolchain. The flat configuration includes the recommended TypeScript and Angular rules and template accessibility checks. Application TypeScript and Angular templates also use strict checks during compilation. The repository CI installs UI dependencies, lints the frontend, runs unit tests, and builds production output.

Component tests use Angular's HTTP testing controller to verify loading, success, empty, error, retry, search, pagination, cancellation, and teardown. Interceptor tests cover FastAPI `detail` responses, structured validation issues, the existing backend error envelope, network failures, and malformed payloads. Mobile navigation tests verify visibility state, focus handling, dismissal, and lifecycle cleanup.

## API configuration and local proxy

Both environment files default to the public API path `/api/v1`:

- `src/environments/environment.ts`: development configuration.
- `src/environments/environment.production.ts`: production configuration, selected by the production build.

`AnalyticsApiService` reads this base URL and calls the existing `/dashboard/summary` and `/products` endpoints. API response types live in `core/models/`, and a shared HTTP interceptor handles backend error messages and connection failures.

For development, `angular.json` loads `proxy.conf.json`. Requests from the browser to `http://localhost:4200/api/...` are forwarded to `http://127.0.0.1:8000/api/...`, keeping browser requests on the UI origin. If the backend uses another host or port, update the proxy target. Stop and restart `npm start` after changing proxy configuration.

Frontend environment files are public configuration; never put credentials or secrets in them. Backend database settings belong in the backend's local `.env` file.

## Routes and current functionality

| Route | Status |
| --- | --- |
| `/dashboard` | API summary, historical monthly sales, and latest completed forecast |
| `/products` | API catalog with search and pagination |
| `/demand-analysis` | Placeholder |
| `/forecasts` | Placeholder; backend forecasting supports up to 30 days |
| `/reports` | Placeholder |
| `/ai-assistant` | Planned; no Ollama connection or active assistant |

The root URL and unknown routes redirect to Dashboard. The shell includes a responsive sidebar, page navigation, and application footer.

## Folder structure

```text
src/
  app/
    core/
      models/          Typed API responses
      services/        Centralized API access and service tests
      api-error.interceptor.ts
    features/
      dashboard/       Dashboard component, template, and styles
      products/        Product catalog component, template, and styles
    shared/            Reusable placeholder page
    app.*              Application shell, configuration, routing, and shell tests
  environments/        Development and production API configuration
  styles.scss          CoreUI stylesheet and global styles
public/                Static assets
proxy.conf.json        Local API forwarding
```

## Production hosting

```powershell
npm ci
npm run lint
npm test -- --watch=false
npm run build
```

Serve the generated application from `dist/ui/browser`. Configure the host to return `index.html` for application routes such as `/products`. Route `/api` to FastAPI through a same-origin reverse proxy; Angular's development proxy does not run in production. If deployment uses a separate API origin instead, update the production API URL and configure that origin on the backend.

Production hosting, reverse-proxy configuration, backend startup, migrations, and data ingestion are deployment setup tasks. Demand Analysis, Forecasts, Reports, and AI Assistant still require future UI implementation.

## CoreUI source and licensing

The UI foundation uses the official [CoreUI Free Angular Admin Template](https://github.com/coreui/coreui-free-angular-admin-template) and its free Angular component packages. The template is [MIT licensed](https://github.com/coreui/coreui-free-angular-admin-template/blob/main/LICENSE); its notice is retained in [COREUI-TEMPLATE-LICENSE.txt](COREUI-TEMPLATE-LICENSE.txt). The installed CoreUI Angular, CSS, and Angular icon integration packages declare MIT licenses. Dependencies retain their own licenses in package metadata. No CoreUI Pro components or assets are included.

## Git conventions

The UI is part of the main repository. Shared ignore rules are maintained in the root [`.gitignore`](../.gitignore), covering local configuration, `node_modules`, Angular caches, test output, and generated builds. Commit source, configuration, documentation, and the npm lockfile.
