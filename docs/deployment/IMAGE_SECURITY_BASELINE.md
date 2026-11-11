> HISTORICAL AND INACTIVE for the Phase 5.17 dedicated manual deployment. Do not execute Terraform, AWS, S3/KMS or teardown instructions below. Preserve existing resources/state. Prior passes are not current evidence. Use [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [final validation](PHASE_5_17_FINAL_VALIDATION.md).

> Historical pre-remediation findings. Superseded by [current passing security report](IMAGE_SECURITY.md).

# Runtime image security — FAIL

Trivy0.76.1, vulnerability database fetched2026-11-02. These findings block deployment under the configured HIGH/CRITICAL policy. No ignore/unfixed exception was added. Counts are package/advisory pairs; one CVE may affect several packages. Scanner results require applicability review, not an assumption every finding is exploitable.

Command pattern (local Docker socket, no publication/deployment):

```sh
docker run --rm --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock,readonly aquasec/trivy:0.76.1 image --scanners vuln --exit-code 1 --severity HIGH,CRITICAL --format json IMAGE
```

| Image | HIGH | CRITICAL | No fixed version listed | Result |
|---|---:|---:|---:|---|
| demand-phase5-backend-check:latest | 50 | 0 | 45 | FAIL |
| demand-phase5-frontend-check:latest | 68 | 4 | 0 | FAIL |
| postgres:16-alpine | 25 | 1 | 0 | FAIL |
| nginxinc/nginx-unprivileged:1.28-alpine | 68 | 4 | 0 | FAIL |

## Required remediation

Refresh supported upstream bases and runtime packages/toolchains, then rebuild and repeat tests/scans. Backend findings include distro packages with no fixed version listed and Python packages bundled in installer tooling; compare actual installed paths and upstream advisories. Frontend/ingress findings include Nginx/OpenSSL and Alpine libraries. PostgreSQL findings are associated with the image Go helper standard library. Keep PostgreSQL major16 unless a separately reviewed upgrade is justified. Do not bypass the gate with blanket ignores or --ignore-unfixed. Existing production data is untouched.

Full scanner JSON remains under ignored validation/phase5 locally. Sanitized package/advisory evidence follows.

## demand-phase5-backend-check:latest

| Package | Installed | Fixed version reported | Severity | Advisory |
|---|---|---|---|---|
| bsdutils | 1:2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| bsdutils | 1:2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| bsdutils | 1:2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| bsdutils | 1:2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| libacl1 | 2.3.2-2+b1 | Not listed | HIGH | CVE-2026-54369 |
| libblkid1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| libblkid1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| libblkid1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| libblkid1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| liblastlog2-2 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| liblastlog2-2 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| liblastlog2-2 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| liblastlog2-2 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| libmount1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| libmount1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| libmount1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| libmount1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| libncursesw6 | 6.5+20250216-2 | Not listed | HIGH | CVE-2025-69720 |
| libsmartcols1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| libsmartcols1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| libsmartcols1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| libsmartcols1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| libsqlite3-0 | 3.46.1-7+deb13u2 | Not listed | HIGH | CVE-2026-119373 |
| libsystemd0 | 257.13-1~deb13u1 | Not listed | HIGH | CVE-2026-16742 |
| libtinfo6 | 6.5+20250216-2 | Not listed | HIGH | CVE-2025-69720 |
| libudev1 | 257.13-1~deb13u1 | Not listed | HIGH | CVE-2026-16742 |
| libuuid1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| libuuid1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| libuuid1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| libuuid1 | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| login | 1:4.16.0-2+really2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| login | 1:4.16.0-2+really2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| login | 1:4.16.0-2+really2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| login | 1:4.16.0-2+really2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| mount | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| mount | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| mount | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| mount | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| ncurses-base | 6.5+20250216-2 | Not listed | HIGH | CVE-2025-69720 |
| ncurses-bin | 6.5+20250216-2 | Not listed | HIGH | CVE-2025-69720 |
| perl-base | 5.40.1-6+deb13u1 | Not listed | HIGH | CVE-2026-9538 |
| util-linux | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-76642 |
| util-linux | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78408 |
| util-linux | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78409 |
| util-linux | 2.41.5-0+deb13u1 | Not listed | HIGH | CVE-2026-78410 |
| msgpack | 1.1.2 | 1.2.3 | HIGH | CVE-2026-114613 |
| msgpack | 1.1.2 | 1.2.1 | HIGH | GHSA-6v7p-g79w-8964 |
| setuptools | 70.3.0 | 78.1.1 | HIGH | CVE-2025-47273 |
| urllib3 | 2.7.0 | 2.8.0 | HIGH | CVE-2026-97687 |
| urllib3 | 2.7.0 | 2.8.0 | HIGH | CVE-2026-97689 |

## demand-phase5-frontend-check:latest

| Package | Installed | Fixed version reported | Severity | Advisory |
|---|---|---|---|---|
| brotli-libs | 1.2.0-r0 | 1.2.1-r0 | CRITICAL | CVE-2026-111497 |
| c-ares | 1.34.6-r0 | 1.34.8-r0 | HIGH | CVE-2026-33630 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-11352 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-11586 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-12064 |
| curl | 8.17.0-r1 | 8.20.0-r0 | HIGH | CVE-2026-5773 |
| curl | 8.17.0-r1 | 8.20.0-r0 | HIGH | CVE-2026-6276 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8286 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8458 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8925 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8927 |
| curl | 8.17.0-r1 | 8.23.0-r0 | HIGH | CVE-2026-92392 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-9547 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | CRITICAL | CVE-2026-31789 |
| libcrypto3 | 3.5.5-r0 | 3.5.8-r0 | HIGH | CVE-2026-14456 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28387 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28388 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28389 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28390 |
| libcrypto3 | 3.5.5-r0 | 3.5.7-r0 | HIGH | CVE-2026-45447 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-11352 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-11586 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-12064 |
| libcurl | 8.17.0-r1 | 8.20.0-r0 | HIGH | CVE-2026-5773 |
| libcurl | 8.17.0-r1 | 8.20.0-r0 | HIGH | CVE-2026-6276 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8286 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8458 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8925 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8927 |
| libcurl | 8.17.0-r1 | 8.23.0-r0 | HIGH | CVE-2026-92392 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-9547 |
| libexpat | 2.7.4-r0 | 2.8.1-r0 | HIGH | CVE-2026-45186 |
| libexpat | 2.7.4-r0 | 2.8.4-r0 | HIGH | CVE-2026-66046 |
| libexpat | 2.7.4-r0 | 2.8.4-r0 | HIGH | CVE-2026-76641 |
| libexpat | 2.7.4-r0 | 2.8.4-r0 | HIGH | CVE-2026-76956 |
| libexpat | 2.7.4-r0 | 2.8.4-r0 | HIGH | CVE-2026-76957 |
| libexpat | 2.7.4-r0 | 2.9.0-r0 | HIGH | CVE-2026-77214 |
| libexpat | 2.7.4-r0 | 2.8.5-r0 | HIGH | CVE-2026-93990 |
| libpng | 1.6.54-r0 | 1.6.55-r0 | HIGH | CVE-2026-25646 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | CRITICAL | CVE-2026-31789 |
| libssl3 | 3.5.5-r0 | 3.5.8-r0 | HIGH | CVE-2026-14456 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28387 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28388 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28389 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28390 |
| libssl3 | 3.5.5-r0 | 3.5.7-r0 | HIGH | CVE-2026-45447 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-53612 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-53613 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-53614 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-76642 |
| libuuid | 2.41.2-r0 | 2.41.6-r1 | HIGH | CVE-2026-78408 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-78410 |
| libxml2 | 2.13.9-r0 | 2.13.9-r1 | HIGH | CVE-2026-6732 |
| musl | 1.2.5-r21 | 1.2.5-r23 | HIGH | CVE-2026-40200 |
| musl-utils | 1.2.5-r21 | 1.2.5-r23 | HIGH | CVE-2026-40200 |
| nghttp2-libs | 1.68.0-r0 | 1.68.1 | HIGH | CVE-2026-27135 |
| nginx | 1.28.2-r1 | 1.28.3-r1 | CRITICAL | CVE-2026-42945 |
| nginx | 1.28.2-r1 | 1.28.3-r0 | HIGH | CVE-2026-27651 |
| nginx | 1.28.2-r1 | 1.28.3-r0 | HIGH | CVE-2026-27654 |
| nginx | 1.28.2-r1 | 1.28.3-r0 | HIGH | CVE-2026-32647 |
| nginx | 1.28.2-r1 | 1.28.3-r4 | HIGH | CVE-2026-42055 |
| nginx | 1.28.2-r1 | 1.28.3-r6 | HIGH | CVE-2026-42533 |
| nginx | 1.28.2-r1 | 1.28.3-r1 | HIGH | CVE-2026-42946 |
| nginx | 1.28.2-r1 | 1.28.3-r3 | HIGH | CVE-2026-49975 |
| nginx | 1.28.2-r1 | 1.28.3-r6 | HIGH | CVE-2026-60005 |
| nginx | 1.28.2-r1 | 1.28.3-r2 | HIGH | CVE-2026-9256 |
| pcre2 | 10.47-r0 | 10.49-r0 | HIGH | CVE-2026-103111 |
| pcre2 | 10.47-r0 | 10.48-r0 | HIGH | CVE-2026-86145 |
| pcre2 | 10.47-r0 | 10.48-r0 | HIGH | CVE-2026-89157 |
| pcre2 | 10.47-r0 | 10.48-r0 | HIGH | CVE-2026-89161 |
| tiff | 4.7.1-r0 | 4.7.2-r0 | HIGH | CVE-2026-4775 |
| zlib | 1.3.1-r2 | 1.3.2-r0 | HIGH | CVE-2026-22184 |

## postgres:16-alpine

| Package | Installed | Fixed version reported | Severity | Advisory |
|---|---|---|---|---|
| stdlib | v1.24.6 | 1.24.13, 1.25.7, 1.26.0-rc.3 | CRITICAL | CVE-2025-68121 |
| stdlib | v1.24.6 | 1.24.12, 1.25.6 | HIGH | CVE-2025-61726 |
| stdlib | v1.24.6 | 1.24.11, 1.25.5 | HIGH | CVE-2025-61729 |
| stdlib | v1.24.6 | 1.26.10, 1.27.3 | HIGH | CVE-2026-111943 |
| stdlib | v1.24.6 | 1.25.8, 1.26.1 | HIGH | CVE-2026-25679 |
| stdlib | v1.24.6 | 1.25.11, 1.26.4 | HIGH | CVE-2026-27145 |
| stdlib | v1.24.6 | 1.25.9, 1.26.2 | HIGH | CVE-2026-32280 |
| stdlib | v1.24.6 | 1.25.9, 1.26.2 | HIGH | CVE-2026-32281 |
| stdlib | v1.24.6 | 1.25.9, 1.26.2 | HIGH | CVE-2026-32283 |
| stdlib | v1.24.6 | 1.25.10, 1.26.3 | HIGH | CVE-2026-33811 |
| stdlib | v1.24.6 | 1.25.10, 1.26.3 | HIGH | CVE-2026-33814 |
| stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | HIGH | CVE-2026-33818 |
| stdlib | v1.24.6 | 1.25.10, 1.26.3 | HIGH | CVE-2026-39820 |
| stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | HIGH | CVE-2026-39821 |
| stdlib | v1.24.6 | 1.25.12, 1.26.5, 1.27.0-rc.2 | HIGH | CVE-2026-39822 |
| stdlib | v1.24.6 | 1.25.10, 1.26.3 | HIGH | CVE-2026-39836 |
| stdlib | v1.24.6 | 1.25.10, 1.26.3 | HIGH | CVE-2026-42499 |
| stdlib | v1.24.6 | 1.25.11, 1.26.4 | HIGH | CVE-2026-42504 |
| stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | HIGH | CVE-2026-56853 |
| stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | HIGH | CVE-2026-56858 |
| stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | HIGH | CVE-2026-56859 |
| stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | HIGH | CVE-2026-56860 |
| stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | HIGH | CVE-2026-56862 |
| stdlib | v1.24.6 | 1.26.9, 1.27.2 | HIGH | CVE-2026-78667 |
| stdlib | v1.24.6 | 1.26.9, 1.27.2 | HIGH | CVE-2026-78669 |
| stdlib | v1.24.6 | 1.26.9, 1.27.2 | HIGH | CVE-2026-97031 |

## nginxinc/nginx-unprivileged:1.28-alpine

| Package | Installed | Fixed version reported | Severity | Advisory |
|---|---|---|---|---|
| brotli-libs | 1.2.0-r0 | 1.2.1-r0 | CRITICAL | CVE-2026-111497 |
| c-ares | 1.34.6-r0 | 1.34.8-r0 | HIGH | CVE-2026-33630 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-11352 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-11586 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-12064 |
| curl | 8.17.0-r1 | 8.20.0-r0 | HIGH | CVE-2026-5773 |
| curl | 8.17.0-r1 | 8.20.0-r0 | HIGH | CVE-2026-6276 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8286 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8458 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8925 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8927 |
| curl | 8.17.0-r1 | 8.23.0-r0 | HIGH | CVE-2026-92392 |
| curl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-9547 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | CRITICAL | CVE-2026-31789 |
| libcrypto3 | 3.5.5-r0 | 3.5.8-r0 | HIGH | CVE-2026-14456 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28387 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28388 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28389 |
| libcrypto3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28390 |
| libcrypto3 | 3.5.5-r0 | 3.5.7-r0 | HIGH | CVE-2026-45447 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-11352 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-11586 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-12064 |
| libcurl | 8.17.0-r1 | 8.20.0-r0 | HIGH | CVE-2026-5773 |
| libcurl | 8.17.0-r1 | 8.20.0-r0 | HIGH | CVE-2026-6276 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8286 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8458 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8925 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-8927 |
| libcurl | 8.17.0-r1 | 8.23.0-r0 | HIGH | CVE-2026-92392 |
| libcurl | 8.17.0-r1 | 8.22.0-r0 | HIGH | CVE-2026-9547 |
| libexpat | 2.7.4-r0 | 2.8.1-r0 | HIGH | CVE-2026-45186 |
| libexpat | 2.7.4-r0 | 2.8.4-r0 | HIGH | CVE-2026-66046 |
| libexpat | 2.7.4-r0 | 2.8.4-r0 | HIGH | CVE-2026-76641 |
| libexpat | 2.7.4-r0 | 2.8.4-r0 | HIGH | CVE-2026-76956 |
| libexpat | 2.7.4-r0 | 2.8.4-r0 | HIGH | CVE-2026-76957 |
| libexpat | 2.7.4-r0 | 2.9.0-r0 | HIGH | CVE-2026-77214 |
| libexpat | 2.7.4-r0 | 2.8.5-r0 | HIGH | CVE-2026-93990 |
| libpng | 1.6.54-r0 | 1.6.55-r0 | HIGH | CVE-2026-25646 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | CRITICAL | CVE-2026-31789 |
| libssl3 | 3.5.5-r0 | 3.5.8-r0 | HIGH | CVE-2026-14456 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28387 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28388 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28389 |
| libssl3 | 3.5.5-r0 | 3.5.6-r0 | HIGH | CVE-2026-28390 |
| libssl3 | 3.5.5-r0 | 3.5.7-r0 | HIGH | CVE-2026-45447 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-53612 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-53613 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-53614 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-76642 |
| libuuid | 2.41.2-r0 | 2.41.6-r1 | HIGH | CVE-2026-78408 |
| libuuid | 2.41.2-r0 | 2.41.6-r0 | HIGH | CVE-2026-78410 |
| libxml2 | 2.13.9-r0 | 2.13.9-r1 | HIGH | CVE-2026-6732 |
| musl | 1.2.5-r21 | 1.2.5-r23 | HIGH | CVE-2026-40200 |
| musl-utils | 1.2.5-r21 | 1.2.5-r23 | HIGH | CVE-2026-40200 |
| nghttp2-libs | 1.68.0-r0 | 1.68.1 | HIGH | CVE-2026-27135 |
| nginx | 1.28.2-r1 | 1.28.3-r1 | CRITICAL | CVE-2026-42945 |
| nginx | 1.28.2-r1 | 1.28.3-r0 | HIGH | CVE-2026-27651 |
| nginx | 1.28.2-r1 | 1.28.3-r0 | HIGH | CVE-2026-27654 |
| nginx | 1.28.2-r1 | 1.28.3-r0 | HIGH | CVE-2026-32647 |
| nginx | 1.28.2-r1 | 1.28.3-r4 | HIGH | CVE-2026-42055 |
| nginx | 1.28.2-r1 | 1.28.3-r6 | HIGH | CVE-2026-42533 |
| nginx | 1.28.2-r1 | 1.28.3-r1 | HIGH | CVE-2026-42946 |
| nginx | 1.28.2-r1 | 1.28.3-r3 | HIGH | CVE-2026-49975 |
| nginx | 1.28.2-r1 | 1.28.3-r6 | HIGH | CVE-2026-60005 |
| nginx | 1.28.2-r1 | 1.28.3-r2 | HIGH | CVE-2026-9256 |
| pcre2 | 10.47-r0 | 10.49-r0 | HIGH | CVE-2026-103111 |
| pcre2 | 10.47-r0 | 10.48-r0 | HIGH | CVE-2026-86145 |
| pcre2 | 10.47-r0 | 10.48-r0 | HIGH | CVE-2026-89157 |
| pcre2 | 10.47-r0 | 10.48-r0 | HIGH | CVE-2026-89161 |
| tiff | 4.7.1-r0 | 4.7.2-r0 | HIGH | CVE-2026-4775 |
| zlib | 1.3.1-r2 | 1.3.2-r0 | HIGH | CVE-2026-22184 |

