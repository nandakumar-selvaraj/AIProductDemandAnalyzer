# Existing authentication security assessment

No authentication redesign was made.

| Boundary | Existing behavior |
|---|---|
| Login | POST /api/v1/auth/login, generic denial, bounded password, configurable global rate cap and Argon2 concurrency gate |
| Password | Argon2id time3, memory65536 KiB, parallelism2, rehash on login |
| JWT | HS256 allowlist; >=64-character configured secret; required signature/issuer/audience/expiry/sub/jti/iat/nbf checks |
| Browser | Secure __Host-demand_session HttpOnly SameSite=Strict Path=/ cookie, no JWT JSON/local storage |
| CSRF | Exact Origin and custom login header; Origin + HMAC session token for browser mutations |
| Authorization | DB user active status/live role/session or API token revocation checked per request |
| Logout | Revokes database browser session and removes cookie; corresponding JWT is rejected server-side |
| Angular | /me restoration, in-memory CSRF/session state, expiry timer, guards/interceptor/redirects, cross-tab logout |
| API Bearer | Separate purpose/audience/revocation table, owner CLI issuance, max15 minutes; browser token cannot substitute |

Middleware defaults private. Admin writes include ingestion/forecast creation. Viewers may read reviewed analytics/predictions/recommendations and use evaluation/backtesting/assistant per existing allowlist. Other methods/routes deny by default. No new admin HTTP endpoint. Public demo and AI disabled here.

Production docs/redoc/openapi are denied intentionally. Swagger Bearer acceptance can run in local test configuration with owner-issued API tokens. Public production Swagger is BLOCKED by existing policy unless a separate access design is approved; never weaken ENVIRONMENT/auth to expose it.

Rate limit is in-process/global per worker; deployment uses one Uvicorn worker. Backend ignores proxy headers. Do not claim per-client-IP admission or distributed lockout. Increasing worker count requires shared admission design.

HTTPS must pass before public login. Stage A serves no app over HTTP. Production TLS/cookie/CSRF/live account checks remain NOT TESTED. Existing tests validate auth behavior locally; see acceptance report and future rotation runbook.
