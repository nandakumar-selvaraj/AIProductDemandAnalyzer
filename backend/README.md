# AI Product Demand Analyzer backend

FastAPI service for sales ingestion and summaries, trailing-average demand forecasting, paginated forecast prediction retrieval, forecast accuracy evaluation, and forecast-based demand trend recommendations. On-hand inventory, purchase orders, lead times, costs, authentication, and AI features are not available in this phase.

## Stack and layout

Python 3.13+ (the existing local environment is Python 3.15.1), FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL with Psycopg 3, pytest, HTTPX, and Ruff.

```text
backend/
  app/{api,core,db,models,repositories,schemas,services}/
  alembic/                 migration history
  data/raw/                manually downloaded Kaggle CSV (ignored by Git)
  scripts/                 CLI tools
  tests/{unit,integration}/
```

## Windows PowerShell setup

Run commands from `backend/`. Select a supported Python installation with `py -0p`; the Python launcher is optional if unavailable. This checkout's existing environment is `backend/venv`. For a fresh checkout, create an environment at the backend root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

In VS Code use **Python: Select Interpreter** and choose `backend/venv/Scripts/python.exe` in this checkout (or `backend/.venv/Scripts/python.exe` if you created the fresh environment above). Dependencies are pinned in `requirements.txt`; `pyproject.toml` mirrors runtime and development dependencies.

For this checkout, activate the existing environment from `backend/` with `.\venv\Scripts\Activate.ps1`. If you created the fresh `.venv` above, activate it with `.\.venv\Scripts\Activate.ps1` instead.

## PostgreSQL and configuration

Install PostgreSQL locally and create the dedicated development database:

```powershell
createdb -U postgres ai_product_demand_analyzer
Copy-Item .env.example .env
```

Set `DATABASE_URL` in `.env`, for example `postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/ai_product_demand_analyzer`. Never commit `.env` or use real credentials in source. No database connection or schema creation happens on application import/startup.

Apply or inspect migrations:

```powershell
alembic upgrade head
alembic current
alembic downgrade -1
```

## Kaggle data and ingestion

Download `train.csv` manually from [Kaggle Demand Forecasting Kernels Only](https://www.kaggle.com/competitions/demand-forecasting-kernels-only/data) into `data/raw/train.csv`. No Kaggle credentials are needed once downloaded. Expected headers: `date,store,item,sales`. The dataset covers 2013-01-01 through 2017-12-31, providing five years of daily sales history. The data contains no inventory balance, costs, product descriptions, or categories; ingestion does not fabricate them.

Validate without a database connection:

```powershell
python scripts/ingest_kaggle_data.py --file data/raw/train.csv --validate-only
```

Ingest (one transaction; exact repeated keys are de-duplicated with the last row winning; existing daily sales quantities are updated):

```powershell
python scripts/ingest_kaggle_data.py --file data/raw/train.csv --batch-size 1000
```

The summary reports read, inserted, updated, rejected, and duplicate-skipped rows, plus up to 100 validation issues. A failed database transaction rolls back all imported data. Database uniqueness constraints and PostgreSQL conflict handling make concurrent imports safe. Store and item codes are stable `STORE_n` and `ITEM_n` identifiers.

## API

Start from `backend/`:

```powershell
python -m uvicorn app.main:app --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health: `http://127.0.0.1:8000/api/v1/health` (process only)
- Readiness: `http://127.0.0.1:8000/api/v1/ready` (checks PostgreSQL)
- Sales upload: `POST /api/v1/ingestion/sales` with multipart field `file` (25 MiB default maximum; configure with `MAX_UPLOAD_BYTES`)
- Sales summary: `GET /api/v1/sales/summary` returns the earliest/latest sales dates, total units sold, distinct stores and products with sales, and daily totals.
- Forecast creation: `POST /api/v1/forecasts` with `{"horizon_days": 30}` creates a forecast run and daily predictions. `horizon_days` defaults to 30 and accepts 1–30; optional `start_date` sets the historical cutoff and cannot be after the latest sales date.
- Forecast predictions: `GET /api/v1/forecasts/{run_id}/predictions?page=1&page_size=50` reads saved predictions for a run. `page` starts at 1; `page_size` defaults to 50 and ranges from 1 to 500. Results are ordered by forecast date, store ID, product ID, then prediction ID. Unknown run IDs return 404; a valid run with no predictions returns an empty list.
- Forecast evaluation: `POST /api/v1/forecasts/evaluate` with `{"forecast_run_id": 1}` evaluates only completed runs by matching saved predictions to actual sales for the same store, product, and forecast date. Missing actuals count as unmatched. Missing runs return 404, non-completed runs return 409, invalid requests return 422, and database failures return 503.
- Latest forecast: `GET /api/v1/forecasts/latest` returns the newest completed run or JSON `null` when none exists.
- Forecast run history: `GET /api/v1/forecasts/runs?page=1&page_size=50&status=completed` returns stable paginated runs; status is optional.
- Products: `GET /api/v1/products?page=1&page_size=50&search=ITEM_1` searches item code and name.
- Stores: `GET /api/v1/stores?page=1&page_size=50&search=STORE_1` searches store code and name.
- Product analytics: `GET /api/v1/products/{product_id}/analytics?store_id=1&start_date=2017-01-01&end_date=2017-12-31` returns daily/monthly totals and observed-date coverage. The default window is the most recent 365 calendar days available for the product; explicit ranges are capped at 365 days.
- Dashboard: `GET /api/v1/dashboard/summary` returns counts and historical monthly sales plus metadata for the latest completed forecast, or `latest_forecast: null` when unavailable.
- Historical backtest: `POST /api/v1/forecasts/backtest` with `{"cutoff_date":"2017-11-30","horizon_days":30}` compares trailing-average and seasonal-naive baselines. The holdout window must have at least one recorded sale on every date.

Backtests are calculated on demand and are not persisted. Both models are generated from data on or before the cutoff; holdout actuals are queried only after prediction generation. The trailing average requires all 30 training dates. Seasonal naive repeats the last observed corresponding weekday and requires the preceding seven training dates. Missing values are never imputed as zero. Metrics include matched/unmatched predictions and series; WAPE is null if matched actual demand is zero. Backtests establish measured results but do not select a superior model automatically.
- Inventory recommendations: `GET /api/v1/recommendations?forecast_run_id=1&page=1&page_size=50` calculates forecast-based demand trends. The run ID is required and positive; page starts at 1; page size defaults to 50 and is capped at 500. Results are stably ordered by store then product. Missing runs return 404, incomplete runs 409, invalid parameters 422, and database failures 503.

Example recommendation response:

```json
{
  "forecast_run_id": 1,
  "page": 1,
  "page_size": 50,
  "total_records": 1,
  "total_pages": 1,
  "increase_threshold_percent": "10",
  "reduce_threshold_percent": "-10",
  "items": [
    {
      "store_id": 1,
      "product_id": 2,
      "recommendation": "increase",
      "reason": "Forecast daily demand is at least the increase threshold above history.",
      "historical_daily_average": "10",
      "forecast_daily_average": "12",
      "change_percent": "20",
      "forecast_horizon_days": 30,
      "historical_coverage_days": 30,
      "historical_window_start": "2017-12-02",
      "historical_window_end": "2017-12-31"
    }
  ]
}
```

Recommendations are calculated on demand and are not written to `stock_recommendations`; that table requires inventory values absent from the source data. Increase is recommended at or above +10%, reduce at or below -10%, and maintain between those thresholds. Thresholds are configurable with `RECOMMENDATION_INCREASE_THRESHOLD_PERCENT` and `RECOMMENDATION_REDUCE_THRESHOLD_PERCENT` settings. Recommendations require all 30 historical sales dates and the entire forecast horizon; missing rows are not treated as zero, and incomplete series return `insufficient_data`. These are demand trend signals only: the source data has no on-hand balances, purchase orders, lead times, or costs, so no order quantity or overstock claim is produced.

Example evaluation response:

```json
{
  "forecast_run_id": 1,
  "forecast_cutoff": "2017-12-31",
  "horizon_days": 30,
  "total_predictions": 15000,
  "evaluated_predictions": 14500,
  "unmatched_predictions": 500,
  "coverage_percent": "96.66666666666666666666666667",
  "total_actual_units": 180000,
  "total_predicted_units": "177500.000",
  "mae": "2.5",
  "wape_percent": "8.75",
  "evaluation_status": "partial"
}
```

`total_predictions` includes every stored prediction for the run. Evaluation joins actual sales only when the store, product, and date match and the date is after the training cutoff and within the run horizon. MAE is the mean absolute difference in units across matched predictions. WAPE is summed absolute error divided by total actual units, multiplied by 100; it is null when there are no matches or total actual units are zero. `coverage_percent` is evaluated predictions divided by total predictions × 100 (0 when there are no predictions). Evaluation status is `complete` when all predictions match, `partial` when some match, and `unavailable` when none match or no predictions exist.

Example forecast-predictions response:

```json
{
  "run_id": 1,
  "page": 1,
  "page_size": 50,
  "total_records": 1,
  "total_pages": 1,
  "items": [
    {
      "id": 1,
      "forecast_run_id": 1,
      "store_id": 1,
      "product_id": 1,
      "forecast_date": "2018-01-01",
      "predicted_units": "12.5"
    }
  ]
}
```

Forecast baseline example response:

```json
{
  "run_id": 1,
  "status": "completed",
  "forecast_cutoff": "2017-12-31",
  "horizon_days": 30,
  "series_processed": 1,
  "series_excluded": 0,
  "predictions_created": 30,
  "created_at": "2018-01-01T00:00:00Z",
  "started_at": "2018-01-01T00:00:00Z",
  "completed_at": "2018-01-01T00:00:01Z"
}
```

The baseline uses the mean units sold over the 30 calendar dates ending on the cutoff; forecasts begin the following date. A series is included only when all 30 dates have sales records. Missing records are not treated as zero, and series without a complete window are counted as excluded. This conservative policy avoids fabricating demand, but can exclude sparse or newly observed series. No seasonality, trend, uncertainty interval, or covariates are modeled. Run, predictions, and success log are committed atomically.

The ingestion upload is unauthenticated for local development. Implement real authentication and authorization before exposing it to untrusted clients.

### Swagger from VS Code

Select the backend virtual environment with **Python: Select Interpreter**, open a terminal rooted at `backend/`, activate it with `.\venv\Scripts\Activate.ps1`, and start Uvicorn with the command above. Open `http://127.0.0.1:8000/docs` in a browser or VS Code Simple Browser. Expand **Health** to try the process and readiness checks. Expand **Data Ingestion**, choose **Try it out** for `POST /api/v1/ingestion/sales`, select a CSV with the required four columns, and execute the request. The response shows inserted, updated, rejected, and skipped row counts. The same generated contract is available as JSON at `/openapi.json` and as ReDoc at `/redoc`.

Swagger and ReDoc are enabled for local development. Before production deployment, review whether public documentation should remain enabled and restrict operational endpoints such as ingestion with real authentication and authorization.

## AI Business Assistant — Ollama / Qwen3 4B

The Assistant is a non-streaming, grounded business feature. PostgreSQL remains authoritative. Its flow is:

```mermaid
flowchart TD
  UI[Angular Assistant] --> API[FastAPI chat endpoint]
  API --> V[Validate question and owned conversation]
  V --> I[Controlled intent and context resolution]
  I --> D[Allowlisted SQLAlchemy and existing business services]
  D --> E[Deterministic metrics and bounded evidence]
  E --> P[Async provider interface]
  P --> O[Private Ollama qwen3:4b]
  O --> C[Validate evidence selection]
  C --> A[Backend-rendered answer, sources and limitations]
  A --> UI
```

### Verified local runtime and transport

On 2026-10-26, `/api/version` returned **Ollama 0.40.11** and `/api/tags` listed **`qwen3:4b`**, a Q4_K_M model with 2,497,293,931 on-disk bytes. Both `POST /v1/chat/completions` and native `POST /api/chat` were tested, rather than assuming compatibility. See [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility), [thinking controls](https://docs.ollama.com/capabilities/thinking), and [official AsyncOpenAI usage](https://developers.openai.com/api/reference/python).

The compatible endpoint returned valid visible schema-constrained JSON, but also generated reasoning despite `reasoning_effort=none`, `think=false`, and a non-thinking prompt. A short plain completion exhausted its token budget with reasoning-like content. `/api/show` advertised thinking metadata with only `true` as a value; metadata alone therefore did not establish reliable non-thinking behavior. **Native `/api/chat` with `think:false` plus the selection JSON schema returned valid visible output without a thinking field in the actual probes.** It is the verified default (`AI_OLLAMA_TRANSPORT=native`). The `openai` mode is implemented with **`AsyncOpenAI`**, an explicit timeout, `max_retries=0`, temperature and token limits; use it when compatibility is preferred and reverify thinking/output behavior for the installed model/version. Transports share the same async provider interface. There is no automatic second inference call or silent transport fallback after failure. No paid service, vector database or additional AI framework is used.

### Setup and configuration

Install Ollama using its [official instructions](https://docs.ollama.com/quickstart), start its local server (`ollama serve` if the desktop service is not already running), and run:

```powershell
ollama pull qwen3:4b
ollama list
```

Keep Ollama bound to loopback locally; do not publish port 11434. From `backend/`, install the committed requirements and configure the ignored `.env`:

```ini
AI_ENABLED=true
AI_PROVIDER=ollama
AI_BASE_URL=http://127.0.0.1:11434/v1
AI_MODEL=qwen3:4b
AI_API_KEY=ollama
AI_TIMEOUT_SECONDS=120
AI_MAX_OUTPUT_TOKENS=512
AI_TEMPERATURE=0.2
AI_MAX_CONTEXT_RECORDS=100
AI_MAX_HISTORY_MESSAGES=10
AI_OLLAMA_TRANSPORT=native
AI_CONTEXT_CHAR_LIMIT=8000
AI_NUM_CTX=8192
```

The API key above is only a local placeholder; no actual credentials are required by the inspected local Ollama service. A private authenticated reverse proxy can require a real secret in this backend setting. Neither key nor provider URL/model is sent to Angular. The URL must end in `/v1`; native URLs are derived from its configured prefix, not a hardcoded host. `.env.example` leaves AI disabled until configured. Settings validate ranges, provider/transport, URL, model and credentials at startup. Restart FastAPI after changing settings; cached provider instances use the configured model without loading model weights inside the application.

Additional bounds: `AI_MAX_RETRIEVAL_SERIES=1000` (100–5000), `AI_MAX_CONCURRENT_REQUESTS=1` (1–8), `AI_CONVERSATION_TTL_SECONDS=1800`, `AI_MAX_CONVERSATIONS=128`. Context records are limited to 100, recent history to ten messages, input to 1000 characters, and visible/provider JSON to 64 KiB. The context setting is conservatively enforced as UTF-8 JSON bytes; it is not a tokenizer and must be sized below the model's usable context with room for instructions/output. Oversized or truncated model responses fail safely. Timeouts are 1–300 seconds, output 32–1024 tokens and temperature 0–2. There are no automatic expensive inference retries. Provider backpressure returns `ai_busy` rather than building an unbounded queue.

### API and conversation contract

`POST /api/v1/assistant/chat` requires a random UUID in **`X-Assistant-Session`**. The browser creates it per chat as an in-memory ownership capability. It is **not account authentication or authorization to private business data**. The application currently shares its business dataset with trusted local clients; require authenticated principal-bound ownership/authorization before public deployment.

```json
{
  "message": "What is the forecast for product 10?",
  "conversation_id": null,
  "context": {
    "forecast_run_id": 1,
    "product_id": 10,
    "store_id": null,
    "start_date": null,
    "end_date": null
  }
}
```

Response fields are `answer`, generated `conversation_id`, classified `intent`, resolved `context`, `sources`, `warnings`, UTC `generated_at`, and `provider_used`. Each source has response-local ID (`f1`, etc.), `type`, label, and nullable run/product/store/date identifiers supplied by the backend. An illustrative source shape is `{ "id": "f1", "type": "forecast", "label": "Persisted prediction aggregate", "forecast_run_id": 1, "product_id": 10, "store_id": null, "start_date": "2018-01-01", "end_date": "2018-01-30" }`; these are contract examples, not claimed live metrics. OpenAPI documents the actual Pydantic schemas and required header.

Omitted context fields preserve previous values; explicit null clears nullable fields. Named IDs in the question override the corresponding context. Positive bounded IDs and real ISO dates are validated; historical ranges span at most 365 inclusive days. Multiple product/store/run IDs request clarification. A phrase such as “highest-demand products” asks whether the user means historical actuals or predictions instead of guessing. `backtest_cutoff` and `backtest_horizon_days` (1–30, default 30) are additional optional context fields. A typed question such as “Compare backtests at 2017-11-30 for 7 days for product 10” resolves those controls. A backtest question without a cutoff asks for one because backtests are not persisted.

The bounded TTL-based conversation store retains ten recent user/assistant messages, prior intent and resolved context, and prevents overlapping requests to one conversation. Another session cannot resume an ID. New Chat creates a new ownership capability and clears local context. No chat tables/migrations are added. Restart/expiry loses chat state. Keep one API worker; multi-worker or multi-instance deployment needs shared ownership-aware storage, TTL and distributed locking. HTTP disconnects cancel the awaiting inference task and release its slot where supported, but the separate inference server may still finish computation. Interrupted synchronous database work cannot be forcibly undone; all Assistant reads are read-only.

### Supported questions and evidence

- **Historical:** product trends/totals, highest historical product totals, averages per **observed** date, store comparisons and declining observed-date averages. Global rankings aggregate the complete scoped range in SQL before applying a result limit. Decline compares early/late half-window observed-date averages, excludes missing periods rather than zero-filling, and warns that coverage can differ. Defaults and the 365-day range rule match product analytics. It does not infer causal trends or forecasts from historical comparisons.
- **Forecasts:** persisted product totals, highest predicted demand, selected-run explanations and product comparisons across stores. SQL aggregates all matching prediction rows before ranking; totals never come from one page. Dates/run/horizon and the distinction from actual sales are explicit. A request for future demand uses persisted forecasts, not current-date extrapolation or a new model run.
- **Recommendations:** existing increase/maintain/reduce/insufficient-data classifications, their computed averages/change, reasons and historical coverage. Product/store filters apply before pagination. The existing service is read sequentially up to the retrieval-series budget; context contains at most 100 matching records, and the answer discloses inspected versus total series and selection scope. No first page is presented as a complete ranking, and no inventory/order quantity is inferred.
- **Evaluation:** existing whole-run MAE/WAPE, matched/unmatched predictions and coverage. Product/store filters do not turn a run-level evaluation into subset accuracy. Null metrics remain explicit nulls in evidence and render as unavailable, never fabricated zero error.
- **Backtesting:** the existing leakage-safe trailing-average/seasonal-naive calculation is reused with optional product/store input filters, with its formulas unchanged. Inputs are guarded at 50,000 rows before loading; larger scopes request narrowing, never a partial comparison. Baseline errors, evaluated samples, coverage, holdout dates and assumptions are reported separately from persisted-run evaluation. Lower error on unequal samples does not establish a winning method.
- **General:** curated application methodology and domain explanations are labeled separately from dataset findings. The actual trailing-average baseline is not described as a sophisticated learned model.

`assistant_data`/`assistant_aggregates` use only allowlisted parameterized SQLAlchemy/existing-service operations. The model receives bounded structured evidence with units, source IDs, dates and nulls; Decimal values remain strings without precision loss. All database work runs in the threadpool and its read transaction ends before async inference. The model has no SQL, database connection, filesystem/environment access or executable tools. SQL, secrets, unsupported purchase quantities and unrelated requests yield useful limitations.

**Grounding boundary:** model output is restricted to evidence-ID selection under a strict schema. The backend validates IDs against supplied evidence, constructs the source list, and renders its verified natural-language statements. Arbitrary model prose/numbers/HTML are not accepted as authoritative answers. Questions, history and database text are untrusted; prompt instructions alone are not relied on as the boundary. This trades conversational flexibility for exact numerical consistency. At most eight selected facts are rendered, and warnings disclose retrieval/context truncation. Sources are never fabricated from model-generated citations.

### Errors, health and testing

Existing `error.code`/`error.message` envelopes are reused: disabled/unready/unavailable/busy providers and business data failures (503), timeout (504), malformed or ungrounded output (502), missing records/conversations (404), invalid contexts/context overflow (422), incomplete/busy runs/conversations (409), capacity (429), and disconnected requests (499 where still observable). Upstream bodies, paths and stack traces are not sent to the browser. Unsupported or empty usable evidence returns a limitation response without inference. Expired conversations require New Chat; manual Retry replays the original context.

`/api/v1/health` checks process health, `/api/v1/ready` checks PostgreSQL, and `/api/v1/assistant/ready` checks provider/model discovery. Use the opt-in smoke script (never run automatically in CI):

```powershell
python -m scripts.assistant_smoke --both-transports
python -m scripts.assistant_smoke --api-url http://127.0.0.1:8000/api/v1
```

The API smoke resolves real product/store IDs from persisted predictions rather than assuming IDs equal Kaggle item/store codes. It performs no writes and reports limitations if no completed run exists. Verified local runs returned nonempty sourced general, forecast, evaluation, historical and recommendation answers with follow-up context. Warm native API checks took approximately **0.37–1.12 seconds** for these selected-record questions; initial model/context load and broader questions took longer. The compatibility path returned valid JSON in roughly 4.4 seconds in a short probe but still generated reasoning. These are individual measured runs, not percentile benchmarks or throughput guarantees. Connection-refused, timeout, cancellation, malformed/empty output and context errors are tested with mocked transports; the user's Ollama service was not shut down just to simulate failure.

`ollama ps` reported about **3.9 GB**, 100% GPU placement and an 8192 context on the inspected RTX 3050 (8192 MiB VRAM). `nvidia-smi` showed roughly 4945 MiB total device usage, which includes other GPU allocations, not a model-only requirement. The model file is about 2.5 GB; RAM/VRAM/KV costs depend on context, slots and hardware. Do not infer that a cheapest CPU-only VPS can meet these latencies. Benchmark representative prompts and peak memory/concurrency on the target machine before sizing.

CI uses mocked providers/HTTP transports and SQLite fixtures, not Ollama/GPU or paid APIs. Standard pytest/coverage and Ruff commands below remain applicable. Backend tests cover routing/validation, source integrity, complete aggregates, null metrics, ownership/history, async transports and cancellation. Separate frontend tests mock FastAPI. Missing-model/offline problems: check `/api/tags`, `ollama ps`, configured model/URL and readiness; timeout/empty responses: check load/output/context and the verified native transport; stale chat: New Chat. Logs record only intent, source count, whether inference ran and latency, not raw questions, evidence, answers or credentials.

### Cloud-portable deployment guidance — not deployed

Both a **single VPS** (reverse proxy + Angular assets + FastAPI + private PostgreSQL + Ollama) and a **separate private inference host** are supported by environment configuration. Ollama has Linux/server support; follow its official installation/runtime guidance and persist model files outside ephemeral containers. `AI_BASE_URL` can point at private inference DNS over a secured network without business-code changes. Never publish Ollama or PostgreSQL to the Internet. The included non-root Python 3.13 backend Dockerfile excludes `.env`/caches and starts one worker; container build/runtime was not verified here. Run migrations as a release task, not on every worker startup. For systemd, use a restricted service account, environment file permissions, explicit working directory and separate API/Ollama units.

Before public exposure: authenticated UI/API and principal-bound conversation access; private database networking and least-privilege roles; TLS reverse proxy; explicit origin allowlist if cross-origin access is needed, including `X-Assistant-Session`; body/rate/concurrency limits; reverse-proxy timeout longer than configured inference timeout; redacted logs; monitoring of readiness, request/model latency, rejection/error rates, CPU/RAM and GPU memory; persistent PostgreSQL/model volumes; scheduled encrypted database backups with restore tests. Existing shared application DB credentials also serve ingestion; a separately restricted Assistant role remains recommended. No broad CORS middleware is enabled by this feature; same-origin UI `/api` forwarding is preferred. A session UUID is not authentication. Multi-worker scaling requires shared conversation storage first. No cloud provider, paid model service or deployment is selected.

## Tests and code quality

Database integration tests are opt-in and require a dedicated PostgreSQL database whose name ends in `_test`; never point tests at a normal development database. Set `TEST_DATABASE_URL` to that database URL to enable the PostgreSQL ingestion integration test. GitHub Actions provisions an isolated PostgreSQL service, applies Alembic migrations, and runs this test on every push and pull request. Unit tests use isolated fixtures and do not download data.

```powershell
pytest
pytest --cov=app --cov-report=term-missing --cov-report=html
ruff check .
ruff format --check .
alembic current
```

The coverage command reports total application coverage and missing source lines, including endpoint and service modules. Open `htmlcov/index.html` for the detailed HTML report. CI also uploads `coverage.xml` as a workflow artifact.

Common problems: `ModuleNotFoundError` usually means the wrong VS Code interpreter is selected; connection refused means PostgreSQL is stopped or `DATABASE_URL` is wrong; Alembic configuration errors usually mean commands were run outside `backend/`; invalid Kaggle rows are listed in the CLI summary and cause a non-zero exit code.
