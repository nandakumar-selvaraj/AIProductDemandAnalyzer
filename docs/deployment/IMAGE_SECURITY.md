# Runtime image security — PASS

Remediation validated locally on 2026-11-02. All four dedicated production runtime images have zero HIGH/CRITICAL findings under Trivy 0.76.1. No vulnerabilities were ignored, no severity was downgraded, and no scanner metadata was removed. Historical findings are retained in [the baseline report](IMAGE_SECURITY_BASELINE.md).

| Runtime | Previous findings | Current HIGH | Current CRITICAL | Result |
|---|---:|---:|---:|---|
| demand-phase5-backend-check:latest | 50 | 0 | 0 | PASS |
| demand-phase5-frontend-check:latest | 72 | 0 | 0 | PASS |
| demand-phase5-postgres-check:latest | 26 | 0 | 0 | PASS |
| nginx/nginx-unprivileged:stable-alpine | 72 | 0 | 0 | PASS |

## Changes

- Backend: supported digest-pinned Python 3.13 Alpine base replaces the affected Debian runtime. All 43 locked application package versions remain unchanged and use binary wheels. The full unused pip/ensurepip installer tooling is absent from the final immutable runtime; a separate build/test target retains installers for validation only. This removes unused executable code, not scan evidence.
- Frontend/ingress: maintained Nginx 1.30.6 unprivileged image from its current nginx/nginx-unprivileged namespace replaces the obsolete 1.28 image. The approved ingress reference is pinned in deploy/single/images.json and the frontend Dockerfile.
- Database: deploy/postgres/Dockerfile derives from the pinned official PostgreSQL 16.15 Alpine image. It replaces obsolete Go gosu with pinned Alpine su-exec 0.3-r0, removes the obsolete gosu/compatibility binary paths, and changes only the official entrypoint privilege-drop invocation. PostgreSQL binaries, major version, data directory, initialization/password behavior and volume persistence remain intact. Actual initialization, migrations, grants, persistence and restore are regression tested.
- Dedicated workflow builds/scans the repaired PostgreSQL image and passes its immutable GHCR digest. Transport/controller/restore allowlists accept the repaired repository and current Nginx namespace. The old vulnerable upstream PostgreSQL digest is not accepted as a dedicated release.

## Reproduce locally

```sh
docker build -t demand-phase5-backend-check ./backend
docker build -t demand-phase5-frontend-check ./ui
docker build -t demand-phase5-postgres-check ./deploy/postgres
python infra/scan_images.py demand-phase5-backend-check:latest demand-phase5-frontend-check:latest demand-phase5-postgres-check:latest nginx/nginx-unprivileged:stable-alpine
```

The local helper resolves each reference to its immutable local image ID before scanning, uses --scanners vuln --exit-code 1 --severity HIGH,CRITICAL, and returns failure if any image has findings. Raw reports and DB cache are ignored local validation artifacts at validation/phase5-remediation/. Production workflow scans immutable registry digests with the same HIGH/CRITICAL failure policy. Development/build/test images with installers are not deployed as runtimes.

## Exact scanned local identities

- demand-phase5-backend-check:latest: `sha256:ac39179457575d13c8d386dbb119d9682fdd2ecb09c978396362e85c2a28fc1e`
- demand-phase5-frontend-check:latest: `sha256:fc5185f720acec88da357c6310e386547ec2203c3fbbe2315f914d5994521e29`
- demand-phase5-postgres-check:latest: `sha256:2e4b6505b165adc3cb1c158771d6fe77afa79412e08af8a495fc66c7099c63e0`
- nginx/nginx-unprivileged:stable-alpine: `sha256:44e74ca483234093081138b6d7b6f561d55557756a2deefc3a5056148defeb99`

## Scope and operational limits

PASS applies to these four dedicated runtime artifacts and the vulnerability database used on this date. Rescan every future release: zero current findings is not a permanent security guarantee. Existing shared-portfolio deployment remains a separate legacy path; its other upstream image references were not approved or deployed by this task. No UpCloud resources, real credentials or production deployment were used.

Primary upstream references: [Python official image](https://hub.docker.com/_/python), [Nginx current namespace and digest guidance](https://github.com/nginx/docker-nginx-unprivileged), [official PostgreSQL Alpine template](https://github.com/docker-library/postgres/blob/master/Dockerfile-alpine.template).
