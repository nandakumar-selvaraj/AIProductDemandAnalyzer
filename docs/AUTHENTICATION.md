# JWT authentication and role-based authorization

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
Every authenticated unsafe method (including analytical POSTs and logout) requires both
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
is no Bearer fallback or second production bypass. Use an admin browser session for HTTP
operations and the database-owner CLI for provisioning/migrations. Remove old operator
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
