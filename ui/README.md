# AI Product Demand Analyzer UI

Standalone Angular frontend for the AI Product Demand Analyzer, with CoreUI Free components and styles. Dashboard, Products, Demand Analysis, and Forecasts use the existing FastAPI service.

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

`AnalyticsApiService` reads this base URL and calls the existing dashboard, product/store catalogs, product analytics, and sales summary endpoints. `ForecastApiService` uses the same configuration for forecast runs, predictions, evaluation, recommendations, and backtesting. API response types live in `core/models/`, and a shared HTTP interceptor handles backend error messages and connection failures.

For development, `angular.json` loads `proxy.conf.json`. Requests from the browser to `http://localhost:4200/api/...` are forwarded to `http://127.0.0.1:8000/api/...`, keeping browser requests on the UI origin. If the backend uses another host or port, update the proxy target. Stop and restart `npm start` after changing proxy configuration.

Frontend environment files are public configuration; never put credentials or secrets in them. Backend database settings belong in the backend's local `.env` file.

## Routes and current functionality

| Route | Status |
| --- | --- |
| `/dashboard` | API summary, historical monthly sales, and latest completed forecast |
| `/products` | API catalog with search and pagination |
| `/demand-analysis` | Historical product/store analysis, date filters, charts, and daily observation table |
| `/forecasts` | Create runs, browse history/predictions, evaluate actuals, review demand trends, and backtest baselines |
| `/reports` | Placeholder |
| `/ai-assistant` | Planned; no Ollama connection or active assistant |

The root URL and unknown routes redirect to Dashboard. The shell includes a responsive sidebar, page navigation, and application footer.

## Demand Analysis

Open `/demand-analysis`, search or page through the product catalog, select a product, and choose an optional store. The default store scope is **All Stores**. Product and store selectors load 50 catalog entries per request; searching resets catalog pagination and preserves the current selection, including when it is on another page. Catalog searches do not themselves apply analytics filters.

Choose dates and select **Apply Filters**. Both dates are optional, following the backend's existing rules:

- No dates: up to 365 calendar days ending on the product's latest sales date.
- Start date only: up to 365 days starting on that date, bounded by the product's latest sales date.
- End date only: up to 365 days ending on that date.
- Both dates: an inclusive range of at most 365 days; start must not exceed end.

The page validates required product selection, real ISO dates, date order, and the inclusive range limit before requesting analytics. **Reset Filters** cancels pending analytics and catalog requests, clears selections/searches/dates/validation, returns to All Stores, and reloads the first catalog pages. New Apply actions cancel obsolete analytics requests; component destruction cancels all active requests. Retry uses the last applied selection, and edited-but-unapplied filters are identified above the results.

Summary cards show total recorded units, distinct observed sales dates, the recorded date range, and **units per observed sales date**. This average is `total_units_sold / observed_dates`, not an average over all calendar days; no observations produce an unavailable average rather than an invented zero.

Daily and monthly charts use only the returned observations/totals. Time-based positions preserve missing periods as gaps; they never fill absent dates with zero or interpolate forecasts. Recorded zero sales have a baseline marker. Charts include accessible descriptions, exact monthly values in an expandable table, and exact daily values in the daily observation table. The daily table displays up to 25 rows per page and supports oldest/newest date ordering. Charts scroll within their own region on narrow screens.

API dependencies (all prefixed by the configured `/api/v1` base URL):

| Endpoint | Usage |
| --- | --- |
| `GET /products?page=...&page_size=50&search=...` | Searchable, paginated product selector |
| `GET /stores?page=...&page_size=50&search=...` | Optional searchable, paginated store selector |
| `GET /products/{product_id}/analytics?store_id=...&start_date=...&end_date=...` | Selected product's recorded daily/monthly sales and summary metrics; optional filters are omitted when blank |
| `GET /sales/summary` | Overall catalog history bounds, labeled separately from product metrics |

The page handles empty catalogs/search results, unavailable services, product-not-found responses, empty sales, and retries. A failed global history request does not block product analytics. The sales summary endpoint currently returns its full unpaginated daily history; this UI retains only its date bounds and does not render that daily array. Avoiding the download for very large histories would require a future backend metadata contract. Product analytics is already bounded to 365 calendar days by the backend.

Demand Analysis tests use the existing Angular/Vitest runner and mocked HTTP requests. Run `npm test -- --watch=false` for the full suite, or `npm test -- --watch=false --include="src/app/features/demand-analysis/**/*.spec.ts"` for feature tests. Additional API contract tests live in `core/services/analytics-api.service.spec.ts`. Coverage includes catalog loading/search/selection/paging, validation/reset, HTTP parameters, data transformations and averages, empty/error/retry states, cancellation/teardown, accessible chart markup, and table paging for a full year of observations.

## Forecasts

Open `/forecasts` for the latest completed run and its recorded model/version, cutoff, horizon, status, timestamps, and counts. Missing metadata is labeled **Not recorded**, rather than replaced with zero. **View Details** selects a history run and moves keyboard focus to its details heading. **Back to run history** returns focus to the history heading. History filters and pages preserve the selection; selecting another run cancels obsolete detail requests and resets detail pagination.

**Create Forecast** defaults to 30 days and accepts whole-number horizons from 1 through 30. The optional training cutoff is sent as `start_date`; it is not the first prediction date. Blank cutoff sends `null`, allowing the backend to use its latest sales date. The backend computes and saves the run synchronously before responding. The UI disables duplicate submissions while pending, reports the actual returned run ID/status/counts, selects that run, resets history to All/page one, and refreshes the latest overview. The creation response does not contain model metadata; that metadata is shown only when returned by a subsequent run query.

The API provides no live progress stream or creation idempotency key. A browser disconnect or navigation cancellation cannot undo work already received by the server. Check history before resubmitting after an interrupted connection. A failed refresh has its own error/retry state and does not invalidate a successful creation response.

Run history uses server pages of 10 with All, Pending, Running, Completed, and Failed filters. Predictions and recommendations use server pages of 50, avoiding rendering an entire 15,000-row forecast. Prediction rows identify dates, product IDs and store IDs without inventing catalog names. Decimal strings retain API precision in tables and metrics. The accessible prediction chart approximates individual rows on the **current page only**, with exact values in the table; it is neither a whole-run aggregate nor a continuous time series.

**Evaluate run** manually evaluates a completed persisted run against matching recorded actuals. Total/evaluated/unmatched predictions, coverage, MAE, WAPE, matched actual/predicted totals and evaluation status are displayed as returned. Partial/unavailable coverage is identified explicitly: matching observations alone do not establish overall forecast accuracy. Null MAE/WAPE are unavailable, not zero, and coverage is a data-matching measure rather than a quality score.

Completed runs also show **Demand recommendations** with Increase, Maintain, Reduce, and Insufficient data labels. Rows include exact nullable historical/forecast daily averages and change, coverage days/window, forecast horizon, and the backend's reason. Thresholds come from the response. These are demand trends, not inventory levels, purchase orders or guaranteed stocking quantities. Missing history is never treated as zero demand.

**Historical Backtesting** is separate from selected-run evaluation. Enter a required historical cutoff and a 1–30-day holdout horizon to compare the backend's trailing-average and weekday seasonal-naive baselines. The response supplies model metrics, holdout bounds, assumptions and any reported missing dates. It does not create a persisted run. Training uses data through the cutoff; subsequent holdout actuals are used for evaluation. The current backend requires sales somewhere on every requested holdout date and can still report unmatched individual series. Compare coverage and sample counts alongside errors; unavailable metrics cannot establish a winning model.

Verified API dependencies, prefixed by the configured `/api/v1` base URL:

| Endpoint | Contract used |
| --- | --- |
| `GET /forecasts/latest` | Latest completed run or `null` |
| `GET /forecasts/runs?page=...&page_size=10&status=...` | Server history; blank All status omitted |
| `POST /forecasts` | `{ horizon_days, start_date: date-or-null }`; synchronous creation response |
| `GET /forecasts/{run_id}/predictions?page=...&page_size=50` | Selected run's prediction rows |
| `POST /forecasts/evaluate` | `{ forecast_run_id }`; measured coverage and errors |
| `GET /recommendations?forecast_run_id=...&page=...&page_size=50` | Selected completed run's demand trends |
| `POST /forecasts/backtest` | `{ cutoff_date, horizon_days }`; nonpersisted baseline comparison |

The lazy `ForecastsPage` composes standalone creation, history, overview, predictions, evaluation, recommendations and backtesting components. Signals hold local UI state; `switchMap` cancels obsolete GET/detail requests, `exhaustMap` guards POST submissions, and `takeUntilDestroyed` cleans up active subscriptions. Loading and errors remove previous results from the affected panel. All panels reuse the global API error interceptor and CoreUI alerts/spinners within the existing application shell. Tables provide captions, column headers and keyboard-focusable horizontal scroll regions on narrow screens. Completed-only actions are disabled or explained for other statuses.

Forecast tests use mocked HTTP, with no database writes. Run the full verification commands above, or `npm test -- --watch=false --include="src/app/features/forecasts/**/*.spec.ts"` for feature tests. API service contracts are tested separately in `core/services/forecast-api.service.spec.ts`. Coverage includes validation, duplicate-submit guards, creation/refresh integration, selection/filter/page cancellation, teardown, exact decimals/null metrics, loading/empty/error/retry states, evaluation errors, recommendation labels/coverage, backtesting, and accessible chart/table/focus behavior.

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
      demand-analysis/ Historical analysis page, catalog pickers, charts, helpers, and tests
      forecasts/       Forecast workspace, run panels, form helpers, and tests
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

Production hosting, reverse-proxy configuration, backend startup, migrations, and data ingestion are deployment setup tasks. Reports and AI Assistant still require future UI implementation.

## CoreUI source and licensing

The UI foundation uses the official [CoreUI Free Angular Admin Template](https://github.com/coreui/coreui-free-angular-admin-template) and its free Angular component packages. The template is [MIT licensed](https://github.com/coreui/coreui-free-angular-admin-template/blob/main/LICENSE); its notice is retained in [COREUI-TEMPLATE-LICENSE.txt](COREUI-TEMPLATE-LICENSE.txt). The installed CoreUI Angular, CSS, and Angular icon integration packages declare MIT licenses. Dependencies retain their own licenses in package metadata. No CoreUI Pro components or assets are included.

## Git conventions

The UI is part of the main repository. Shared ignore rules are maintained in the root [`.gitignore`](../.gitignore), covering local configuration, `node_modules`, Angular caches, test output, and generated builds. Commit source, configuration, documentation, and the npm lockfile.
