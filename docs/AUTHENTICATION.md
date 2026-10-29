# JWT authentication and role-based authorization

## Phase 7C: restricted Swagger and API tokens

Browser login still returns only user, expiry and CSRF metadata; JWTs remain HttpOnly
cookies. New browser tokens carry `purpose=browser`; existing sessions remain valid until
their original expiry. Angular never receives an API token.

API tokens use `purpose=api`, audience `<JWT_AUDIENCE>:api`, the configured issuer/HS256
key, and a separate `auth_api_tokens` revocation record. Every request checks signature,
claim types, purpose, issuer, audience, JWT/database expiry, user status, current role and
revocation. Lifetime is 1–15 minutes (default 10). No refresh/public minting endpoint exists.
Browser JWTs cannot authenticate as Bearer tokens, and API tokens cannot authenticate as
cookies. Requests carrying both credentials are rejected. Token-only requests do not use
browser CSRF; cookie requests retain all Origin/CSRF checks. API tokens cannot use browser
`/auth/me` or `/auth/logout`. Admin/Viewer authorization and AI quotas apply equally.

Use the **database-owner** CLI in the same trusted environment as the API. For restricted
local development, from `backend`, with AUTH_ENABLED=true and the same signing settings:

```sh
umask 077
python -m alembic upgrade head
python -m scripts.manage_api_tokens issue --email "$DEVELOPER_EMAIL" \
  --minutes 10 --output /private/operator/api.token
python -m scripts.manage_api_tokens revoke --email "$DEVELOPER_EMAIL"
```

The output directory must already exist and be private. Issuance exclusively creates a
new file with POSIX mode 0600, refuses overwrites, and never prints the credential. On
Windows, use an operator-only directory ACL; POSIX mode bits do not configure Windows ACLs.
Never commit the file, put tokens in URLs, command arguments, logs/tickets, or persistent
browser storage. Delete the file after use. Revoke ends all API tokens for the named user
without ending browser sessions. Password reset, role change and disable revoke both.
Rows store identifiers/expiry, never JWT contents. Key rotation invalidates both flows.

Open `/docs` on a loopback-bound development API or through an approved SSH tunnel to
an isolated operations instance. Use a separate cookie-free browser profile. Click
**Authorize**, enter the token under **ApiBearer**, and execute protected operations.
Swagger authorization stays in memory (`persistAuthorization=false`); close the tab and
revoke afterwards. Do not manually authorize BrowserSession. Swagger uses its existing
CDN assets; the restricted browser needs access to that CDN.

Direct production FastAPI requests return 404 for `/docs`, `/redoc`, `/openapi.json` and
its API root `/`. Caddy also explicitly rejects documentation paths, while the public
site root continues serving Angular. There is no production docs-enable flag. Never switch a public production API to development
to access Swagger. Owner CLI access is equivalent to administrative server access: keep
owner credentials out of the running API and restrict operator access.

Migration `0003_api_tokens` is additive: it preserves business data/browser sessions,
adds the separate token table/index, grants runtime SELECT only, and denies all access
to the demo reader. Only the owner CLI issues/revokes tokens. OpenAPI declares cookie
and Bearer alternatives on protected business operations and cookie-only auth endpoints.

## Phase 7C: Data Management navigation and ingestion

**Management → Data Management** (`/data-management`) is Admin-only with authentication
enabled. Viewers redirect to dashboard; anonymous users redirect to login. Server RBAC
independently rejects Viewer/anonymous uploads. The existing unauthenticated loopback
development profile remains available; production cannot disable authentication.

The page loads Admin-only `/api/v1/ingestion/config` and posts FormData to the existing
`/api/v1/ingestion/sales` endpoint through the cookie/CSRF interceptor. The effective UI
limit is the lesser of the CSV limit and request limit minus 1 KiB multipart allowance.
Extension, empty-file and size checks improve feedback; server content/size validation
remains authoritative. No Kaggle credentials or automatic downloads are involved. Split
large datasets below configured bounds rather than removing server/proxy limits.

Required schema: `date,store,item,sales`. Kaggle 2013–2017 records are labelled historical
demo data. The last valid duplicate wins, existing totals are updated, valid rows commit
together, and rejected rows are reported. The page shows only its latest upload result;
ingestion history is not persisted. Progress is determinate when supported by the browser
transport (Angular Fetch may show indeterminate progress). Double submissions are blocked.
Logout/expiry/navigation cancels waiting and clears results; already admitted server work
may finish. Check sales before retrying an interrupted import.

The sections below describe the earlier browser-auth implementation; Phase 7C supersedes
the earlier statement that no Bearer flow exists. Legacy OPERATOR_TOKEN remains ignored.

Implemented on top of ce6515a. No UpCloud/cloud deployment or real account provisioning
was performed. All validation users/databases were synthetic and disposable.

## Architecture and lifecycle

Production requires AUTH_ENABLED=true, a random JWT_SIGNING_SECRET of at least 64
characters, exact HTTPS AUTH_ALLOWED_ORIGINS, explicit issuer/audience and trusted hosts.
Generate a secret using `openssl rand -hex 32` and store only in the restricted server env
file/secret manager. The API's runtime container gets the signing key; Angular gets none.
The supported algorithm allowlist is exactly HS256, never inferred from a token header.

POST /api/v1/auth/login accepts email/password JSON and returns user id/email/role,
expires_at and a session-bound CSRF value. The access JWT itself is returned ONLY in a
`__Host-demand_session` cookie: HttpOnly, Secure, SameSite=Strict, Path=/, no Domain,
default lifetime 30 minutes. JWT payloads contain subject UUID, random jti, issuer,
audience, issued-at, not-before and expiry. Required claims, types, signature, algorithm,
issuer/audience, time bounds and subject format are checked on the server.

Every protected request additionally queries the revocable session and current user:
missing/revoked/expired session, mismatched subject, disabled user or invalid current role
is rejected. Role claims from a browser are not trusted. Logout marks that session revoked
and deletes the cookie using matching attributes. Replaying a captured cookie after
logout fails. Password reset, role change and disabling a user revoke all their sessions.
No refresh token is issued; expiry requires login. Key rotation invalidates all JWTs.
Already admitted in-flight work may finish when a later logout revokes the session.

GET /api/v1/auth/me restores user/expiry/CSRF state after refresh without exposing the JWT.
Sensitive API responses and frontend HTML use Cache-Control: no-store. Authentication
validation errors omit submitted input, including in development. Audit logs record
accept/deny/revoke events and internal user IDs, never passwords, JWTs or CSRF values.

Argon2id uses a unique library-generated salt, 64 MiB memory, three iterations and two
lanes. Hashes can be upgraded after successful verification. Unknown/disabled/wrong-password
responses are generic; unknown users still perform a dummy hash verification. A global
login allowance of ten requests/minute and a two-verification concurrency gate bound
brute-force/Argon2 resource use. All request bodies are bounded; login is capped at 4 KiB.
These global limits deliberately trade availability for bounded resource use. They are
single-worker controls; use a shared limiter before adding replicas or workers.

## CSRF

Login requires an exact approved Origin plus X-Requested-With: AIProductDemandAnalyzer.
Every cookie-authenticated unsafe method (including analytical POSTs and logout) requires both
an approved Origin and X-CSRF-Token matching the HMAC derived from the current server
session identifier and signing key. CSRF is returned by login/me and held only in memory.
No CORS wildcard/credentialed cross-origin access is enabled; SameSite is additional
defense rather than the only CSRF check. Missing/foreign Origin is rejected on login and
session-authenticated unsafe requests, including command-line requests unless explicitly
supplied. Public fixed-question demo AI remains separate, bounded and stateless.

## Authorization matrix

| Operation | Admin | Viewer | Anonymous |
|---|---|---|---|
| Dashboard, catalog, sales, predictions, recommendations, reports | Yes | Yes | Only explicit synthetic public-demo allowlist |
| GET forecast evaluation | Yes | Yes | Synthetic public demo only |
| POST evaluation and bounded backtesting | Yes + CSRF | Yes + CSRF | No |
| Free-form assistant chat/readiness | Yes + limits | Yes + limits | No |
| CSV ingestion, forecast creation | Yes + CSRF | No (403) | No (401) |
| Login | Approved Origin/header + credentials | Same | Same |
| me/logout | Current valid session (logout + CSRF) | Same | No |
| User provisioning/disable/reset/role change | Owner CLI only | No | No |
| Unknown/new unsafe API routes | Denied until explicitly reviewed | Denied | Denied |

Roles live on auth_users with a database constraint accepting only admin/viewer. These
are application roles, distinct from PostgreSQL owner/runtime/reader identities.
Analytical POSTs were reviewed explicitly: evaluate_forecast and run_backtest read
business data, so a viewer can use them without receiving write permission. Existing
forecasting algorithms were not changed. Authenticated viewers in public-demo deployments
still use the demo reader connection. Auth itself always uses the private runtime DB.
Assistant conversation ownership includes authenticated user and server-session identity,
preventing another account from reusing a client-supplied conversation capability.

## Operator-token transition

The previous OPERATOR_TOKEN does not authorize HTTP requests anymore. Its legacy setting
is accepted for environment-file compatibility only and ignored by authorization. There
is no legacy Bearer fallback. Phase 7C's purpose-separated API tokens are independently
revocable and enforce the same RBAC. Use the database-owner CLI for provisioning/migrations. Remove old operator
secrets from deployment configuration after this transition. Production cannot disable
authentication; AUTH_ENABLED=false is rejected there.

## Schema and migration

Revision `0002_authentication` follows `0001_initial` and only adds auth_users/auth_sessions
plus indexes: unique normalized email, session expiry and user/expiry. It does not reset
sales, forecasts, inventory or recommendations. Every user has a UUID; session jti is a
random 256-bit identifier. JWTs/plain passwords are never stored in either table.

The migration removes demo-reader access to auth tables, removes broad future-table
reader defaults, grants only existing business tables to the demo reader, and restricts
the runtime role's auth_users privileges to SELECT and password-hash rehash updates.
The owner CLI alone creates users or changes roles/active state. Runtime can create and
revoke sessions. Existing custom PostgreSQL role names require equivalent reviewed ACLs;
the migration's role changes target the role names configured by this repository.
Do not use blanket GRANT SELECT ON ALL TABLES for the demo reader after restoring.

Apply with the owner migration job, then provision accounts. On a fresh synthetic demo,
seed the empty business database before creating users (the seed intentionally rejects
nonempty application tables). Existing development databases were not upgraded by this
implementation. Test migrations were applied only to newly created databases.

## Secure provisioning

Supply an email explicitly; no default usernames/passwords/accounts are created:

```sh
docker compose --env-file .env.production -f compose.production.yml run --rm migrate
# Both prompt for a password twice using getpass; use independent strong passwords.
docker compose --env-file .env.production -f compose.production.yml run --rm migrate \
  python -m scripts.manage_users create --email "$ADMIN_EMAIL" --role admin
docker compose --env-file .env.production -f compose.production.yml run --rm migrate \
  python -m scripts.manage_users create --email "$DEMO_VIEWER_EMAIL" --role viewer
```

For automation, `--password-stdin` reads one line from an approved secret manager through
stdin; do not put a password in command arguments, source code, logs or shell history.
Passwords must be at least 12 characters and at most 1024 UTF-8 bytes. Email is normalized
to lowercase. CLI commands also support disable, reset-password, set-role and
purge-sessions (expired records only). They require the owner DB credentials, which the
running API does not receive. Run session cleanup periodically after deployment approval.
A shared demo viewer account is restricted, not a substitute for individual attribution.
Never grant admin to potential clients or import private data into the demo database.

## Angular/session behavior

Protected workspace routes restore /auth/me before activation and redirect to /login
when unauthenticated. Successful login navigates to /dashboard. Auth user, CSRF and expiry
are in memory; no JWT or credentials are stored in localStorage/sessionStorage or a
JavaScript-readable cookie. The login form clears the password after each attempt.

A timer using the server expiry clears the session and redirects proactively. Every API
still checks server expiry/revocation. A protected API 401 clears state and redirects;
403 is surfaced as an authorization error without logout. Logout waits for server
revocation before clearing local state; network failure is shown and can be retried.
Tabs synchronize successful logout through BroadcastChannel without transferring tokens.
Timers/listeners are cleaned on destruction/session replacement. Page-hide clears
sensitive rendered state, and a restored back-forward-cache page revalidates /me before
showing protected content. Guards, no-store and hidden unauthenticated content prevent
Back after logout from revealing the old protected page.

Admin write controls are visible only for admin; viewers retain analytical backtesting,
evaluation and assistant access. Explicit `/demo` and its products, demand-analysis, forecasts, reports and ai-assistant subroutes
are the anonymous synthetic showcase, still enforced by the API's dedicated demo mode.
They do not grant access to protected workspace routes.

Local legacy development remains opt-in for auth to preserve existing workflows:
backend AUTH_ENABLED=true with a random JWT_SIGNING_SECRET, approved http loopback origin,
and `ng serve --configuration authentication`. Local cookies are HttpOnly/Strict but not
Secure over loopback HTTP; production cookies are always Secure. The default development
profile remains unchanged. Never deploy that development profile to a public host.

## Validation and remaining gates

Local backend, frontend, migration and browser validation results are recorded in
PRODUCTION_READINESS.md. Run from backend:

```sh
python -m pytest tests -q
python -m scripts.validate_local --postgres-only
python -m scripts.validate_local --auth-e2e
```

The local runner provisions random synthetic users in a newly created loopback DB,
starts isolated API/UI servers, tests auth and then removes only its own resources.
CI runs this path with Chromium; local validation used Edge. The disposable Docker
workflow also provisions users and runs production-cookie browser tests, but Docker
Engine is unavailable locally and that workflow is not claimed as passed.

Before launch: run container/restore/ACL checks, scan/pin images and dependencies,
configure HTTPS origins/secrets, approve password distribution and recovery procedures,
measure memory under concurrent login/forecast work, and add external traffic monitoring.
No MFA, SSO, password-reset email or refresh tokens are introduced. Add a distributed
limiter before horizontal scaling; forwarded client IP headers are not trusted for quotas.

References: [PyJWT claims validation](https://pyjwt.readthedocs.io/en/latest/usage.html),
[Argon2id API](https://argon2-cffi.readthedocs.io/en/stable/api.html),
[OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).


Suggested commit: `feat: add revocable JWT sessions and admin-viewer authorization`

Primary files: backend/app/models/auth.py, services/auth_service.py, endpoints/auth.py,
core/config.py and security.py, 0002_authentication Alembic revision, manage_users CLI,
assistant session ownership, Angular auth service/interceptor/guard/login and shell,
environment profiles, production Compose/env, Docker validation/ACL checks, E2E workflow,
backend/Angular/browser tests, and production/deployment/recovery documentation.
