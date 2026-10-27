# End-to-end validation

Validated on **27 October 2026 (Asia/Calcutta)**. Local functional validation passes.
**Public cloud deployment remains NO-GO** pending the security, infrastructure and
data-validation items below. No cloud deployment, commit or push was performed.

This document contains test outcomes and operational measurements only. Actual
business quantities, record identifiers, prompt transcripts, API payloads, database
credentials and machine-specific paths are deliberately excluded. The committed
fixture contains only deterministic synthetic sales.

## Executed results

The initial live validation recorded **417 passing checks, zero unresolved
executed failures, and four blocked/unexecuted scenarios**. That count included
individual regression tests and suite-level quality gates; assertions inside a
test were not counted separately. The packaging reruns below overlap those checks
and must not be added to that total.

| Module | Scenario | Expected result | Actual result | Status | Evidence |
|---|---|---|---|---|---|
| Environment | PostgreSQL, migrations, populated history, saved forecasts, FastAPI, Angular, Ollama and model | Required live services and real records available | Connectivity and readiness succeeded; migrations already at head; existing database/Ollama services reused | Pass | Local `migrations.log`, `listeners.log`, `assistant-smoke.log` |
| Backend APIs | Health, dashboard, products/stores, sales, demand analysis, forecasts, predictions, evaluation, backtesting, recommendations, reports data and assistant | Successful responses plus appropriate validation/not-found errors | 36 live API/data checks passed | Pass | Local `api-results.json` |
| Data consistency | SQL/API/assistant totals, date ranges, IDs, schema, pagination, recommendations, evaluation and CSV | Independent values agree; no invented business facts | 7 checks passed; every returned CSV observation compared; missing metrics correctly unavailable | Pass | Local `consistency-results.json` |
| Live browser | Dashboard, filtering, history, saved predictions, CSV, AI answers, sources, follow-ups, New Chat and responsiveness | Actual data and correct UI state | 11 checks passed using Playwright and installed Edge | Pass | Local `browser-results.json`, screenshots |
| Live Ollama | Native and OpenAI-compatible transports; five assistant questions | Visible structured output and sourced answers | Both transports and all five questions succeeded | Pass | Local `assistant-smoke.log` |
| Provider failures | Refused connection and delayed real-provider response through isolated APIs | 503/504; recovery messages; no invented answer | 2 API and 2 browser fault checks passed; existing Ollama was not stopped | Pass | Local `fault-results.json`, `fault-browser-results.json` |
| Portable suite | Read-only workflows on existing live stack | Data-driven assertions without fixed business IDs | 5 passed; AI-disabled check intentionally skipped on AI-enabled backend | Pass | Local `portable-live.log` |
| Portable synthetic E2E | Disposable test database, real FastAPI/Angular, no Ollama | All default tests, including disabled/offline/timeout cases | **8 passed** on Windows/Edge; final run 13.0 seconds | Pass | Local `portable-synthetic.log` |
| Portable opt-in AI | General source, forecast aggregate, follow-up, reset and missing history | Real inference for answered questions; honest missing-data limitation | **3 passed**, using real configured Ollama | Pass | Local `portable-ollama.log` |
| Backend regression | pytest, including six new seed safety cases | Pass without accessing the normal database from safety tests | **117 passed, 1 skipped**; one dependency deprecation warning | Pass | Local `portable-pytest.log` |
| Angular regression | Existing unit tests | All existing tests pass after tooling dependency addition | **237 passed** across 16 files | Pass | Local `portable-unit.log` |
| Quality/build | Ruff lint/format, Angular lint, production build, E2E TypeScript | Successful exit codes | All passed | Pass | Local `portable-ruff.log`, `portable-format.log`, `portable-lint.log`, `portable-build.log`; `npm run e2e:typecheck` |
| GitHub Actions | Hosted Linux Chromium job | Workflow successfully runs on GitHub | Configuration added; not dispatched or observed in this session | Not executed | [Workflow](../.github/workflows/e2e.yml) |

The original four limitations were: no dedicated PostgreSQL ingestion integration
database; no successful write requests against existing business data for ingestion
or forecast creation; and no matching actuals for saved-run accuracy. A separate
synthetic E2E database now exercises ingestion and forecast creation through the
existing services, but **successful upload/create HTTP workflows are still not
covered by the browser suite**. No normal database writes were made to close those
gaps. The existing PostgreSQL integration test still skips without its own empty
`*_test` database; do not point it at the populated E2E fixture.

### Evidence handling

Raw evidence from this session is retained locally under `validation/phase6/`,
including [the full local report](../validation/phase6/REPORT.md),
[portable synthetic results](../validation/phase6/portable-synthetic.log), and
[Ollama results](../validation/phase6/portable-ollama.log). This entire directory
is ignored by Git and is intentionally absent in clean clones. The links are
local evidence references, not claims of published artifacts. Raw reports and
screenshots can reveal business data and local paths; review/redact before sharing.

The final normal browser run recorded no unexpected HTTP errors or uncaught page
exceptions. Earlier failures came from sandbox temporary-file restrictions and
harness route/selector/render timing mistakes; corrected reruns passed. The first
portable offline fault used too short a timeout for Windows connection refusal;
the fixture now gives refusal five seconds and tests timeout separately at one
second. No application feature or forecasting algorithm was changed.

## Measured local performance

These are single-machine observations, not production capacity guarantees:

| Measurement | Observed result |
|---|---|
| Non-assistant API scenarios | 0.005–0.601 seconds in the initial recorded sample |
| Warm assistant API questions | 0.546–1.189 seconds; five sampled questions |
| Initial native / compatible transport probes | 11.41 / 6.96 seconds, including runtime/model effects |
| Initial general assistant question | 7.16 seconds |
| Browser normal workflow scenarios | Approximately 1.218–1.429 seconds in the final initial-validation run |
| Browser animation frames | Maximum 17.4 ms over 20 sampled intervals |
| Pending-request frame samples | Approximately 12–14 ms during isolated faults |
| Loaded model | Ollama reported 3.9 GB, GPU placement, context 8192 |
| Total GPU use at snapshot | About 4.6 GiB of 8 GiB; includes other allocations |

The original timeout validation used an isolated one-second backend timeout and a
proxy delaying a real Ollama response. The portable CI fault fixture instead uses
a deliberately slow local HTTP provider and real FastAPI timeout handling, so it
requires no GPU. It does **not** claim to test model quality or natural Ollama
stalls. Neither run was a long-duration soak or representative concurrency test.

## Running the portable suite

Use the documented backend Python environment and Node 24/npm 11. From `ui/`:

```powershell
npm ci
npx playwright install chromium
npm run e2e:typecheck
npm run e2e
```

Start FastAPI separately using [the backend instructions](../backend/README.md).
The suite never starts, seeds, resets or migrates a database implicitly. It needs
populated history and a completed forecast with saved predictions. Test fixtures
discover IDs from API responses. The tests read business data; assistant requests
change only in-memory conversations. CSV downloads go into ignored test output.

By default Playwright starts Angular, or reuses an existing local development
server outside CI. Each test gets an isolated browser context. There is one worker
and no automatic retries. Web assertions wait for responses and rendered state;
they do not rely on fixed sleeps.

| Environment variable | Meaning |
|---|---|
| `E2E_BASE_URL` | Browser URL; defaults to `http://localhost:4200` |
| `E2E_API_URL` | Backend base **with trailing slash**; defaults to `http://127.0.0.1:8000/api/v1/` |
| `E2E_EXTERNAL_SERVERS=1` | Disable Angular lifecycle management; required for custom server ports/hosts |
| `E2E_BROWSER_CHANNEL=msedge` | Optional installed Edge; otherwise use Playwright Chromium |
| `E2E_PYTHON` | Backend Python executable; enables isolated real-backend offline/timeout tests |
| `E2E_AI_DISABLED=1` | Enable the disabled-assistant case, only when primary backend has `AI_ENABLED=false` |
| `E2E_CAPTURE_ARTIFACTS=1` | Opt into failure screenshots, video and trace capture; may contain sensitive data |

On Windows, resolve the backend interpreter rather than embedding a machine path:

```powershell
# From ui/, after creating/activating the backend environment described in its README:
$env:E2E_PYTHON = (Get-Command python).Source
# Or select the documented existing environment explicitly:
$env:E2E_PYTHON = (Resolve-Path ../backend/venv/Scripts/python.exe).Path
npm run e2e
```

Without `E2E_PYTHON`, the two isolated fault cases explicitly skip. Without
`E2E_AI_DISABLED=1`, the disabled-assistant case explicitly skips. A missing live
database, saved predictions or an enabled opt-in model fails with a prerequisite
message rather than being counted as a pass.

### Explicit Ollama opt-in

Configure and start Ollama and the backend as described in
[the assistant setup guide](../backend/README.md). Then, from `ui/`:

```powershell
npm run e2e:ollama
```

The cross-platform runner enables `E2E_OLLAMA=1` for that child process and selects
only `@ollama` tests. Both `npm run e2e` and plain `npx playwright test` exclude
those tests by default. Merely having Ollama installed does not opt in. No model
download, GPU service, paid API or automatic fallback is part of normal CI.

### Synthetic PostgreSQL fixture

The [seed script](../backend/scripts/seed_e2e.py) creates 91 days of deterministic
sales for two generated products and two generated stores: 364 sales rows, four
series and a seven-day saved forecast with 28 predictions. These numbers describe
only the synthetic fixture, not actual business records. The holdout dates have
synthetic actuals so evaluation returns measured metrics.

Create a **new empty** loopback PostgreSQL database whose name ends in
`_e2e_test`. Supply its URL via a private process environment; do not put real
credentials in source, command history or documentation. From `backend/`:

```powershell
# DATABASE_URL must already point to the new disposable *_e2e_test database.
python -m alembic upgrade head
$env:E2E_ALLOW_SEED = '1'
python -m scripts.seed_e2e
$env:AI_ENABLED = 'false'
python -m uvicorn app.main:app
```

The seed requires an explicit `DATABASE_URL` environment variable rather than
reading a normal `.env` URL. It rejects remote hosts, non-PostgreSQL targets,
incorrect database names and nonempty application tables. It never deletes or
resets data. Repeated seeding intentionally fails on a populated fixture; reuse
it read-only or create another empty disposable database. Six unit tests verify
the refusal guards. Use a test-only role restricted to the disposable database.

In the UI test process set `E2E_AI_DISABLED=1` and `E2E_PYTHON`, then run the default
suite. Do not set those variables for an AI-enabled live stack unless their
documented preconditions hold.

## GitHub Actions

[E2E workflow](../.github/workflows/e2e.yml) runs on pull requests, pushes and manual
dispatch with read-only repository permissions:

1. Provision a disposable PostgreSQL 16 service using a public, test-only credential.
2. Install Python 3.13 and Node 24 dependencies from committed requirements/lockfile.
3. Apply migrations and seed deterministic synthetic data.
4. Install Chromium and system dependencies, then start FastAPI with AI disabled.
5. Let Playwright start Angular; type-check and run eight non-Ollama browser cases.
6. Upload synthetic-only failure reports/traces/video/logs for seven days.

There is no configured GPU runner or self-hosted inference job. Real Ollama tests
remain explicitly local opt-in. GitHub execution has **not** been observed yet;
the synthetic workflow's service/test sequence was exercised locally on Windows
with installed Edge, not claimed as a hosted Linux run. The next pull request
must confirm the hosted Chromium job.

## Unresolved issues and deployment readiness

* Public authentication and authorization are not implemented; a conversation
  session UUID is not authentication, and ingestion is unauthenticated. Public
  exposure remains blocked.
* Production TLS/reverse proxy, private PostgreSQL/Ollama networking, least-privilege
  roles, resource/rate limits, backup restore, monitoring, container runtime and
  target hardware/concurrency still need validation. Conversation state is
  process-local; multiworker deployment needs shared state.
* Saved-run accuracy cannot be established without matching actual sales. The
  initial historical backtest ran successfully but does not establish business
  acceptance across representative holdouts. Do not fabricate missing actuals.
* Successful ingestion/create HTTP workflows and the existing isolated PostgreSQL
  integration test remain additional coverage work, as explained above.
* `npm audit` during tooling installation reported a high-severity Vite advisory
  and a low-severity Angular build dependency finding in the existing build chain.
  The lockfile changes only add test tooling/type dependencies; no broad automatic
  dependency upgrade was applied. Review/remediate before public deployment.
* Hosted GitHub execution, cross-browser coverage, representative load and soak
  testing remain unverified. All reported timings apply to the observed local run.

Generated reports, captures, downloads, coverage, logs, `.env` secrets, private
keys and authentication state are excluded by `.gitignore`. Captures are disabled
locally unless opted in; CI captures use only the synthetic fixture. Keep real
URLs/passwords in private process environments or an approved secret store.

**Assessment:** ready to review the test tooling changes; local functional tests
pass. Not ready for public deployment. No real business data should be committed
as evidence.
