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

## Tests and code quality

Use a dedicated test database before adding database-backed integration tests; never point tests at a normal development database. Current unit and health tests use fixtures and do not download data.

```powershell
pytest
ruff check .
ruff format --check .
```

Common problems: `ModuleNotFoundError` usually means the wrong VS Code interpreter is selected; connection refused means PostgreSQL is stopped or `DATABASE_URL` is wrong; Alembic configuration errors usually mean commands were run outside `backend/`; invalid Kaggle rows are listed in the CLI summary and cause a non-zero exit code.
