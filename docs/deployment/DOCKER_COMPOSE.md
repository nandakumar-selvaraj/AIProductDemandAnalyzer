> Phase 5.17: follow [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [current audit stop gates](PHASE_5_17_FINAL_VALIDATION.md). Commands below are future separately authorized operations, not part of this audit. Active backups use [encrypted SFTP/Restic](BACKUP_RESTORE.md); no dedicated Terraform/S3/KMS is required.

# Production Compose

Install `compose.prod.yml` as `/opt/demand/compose.prod.yml` with root-owned `init-db.sh` and `nginx.conf`. Relative mounts target that installed directory, not repository root. Backend/UI Dockerfiles are reused. Angular `npm ci`, production build and `dist/ui/browser` output are verified.

Services: PostgreSQL16, one-shot owner migration, non-root single-worker Uvicorn `app.main:app`, Angular static Nginx, unprivileged Nginx ingress. No reload/debug. Rotated logs, CPU/memory/PID limits, capability drops, read-only app filesystems, tmpfs and graceful API stop configured. Healthy DB precedes migration; successful migration precedes backend; readiness checks actual DB connectivity.

Create `demand-single-database` volume exactly once after approval. `external: true` prevents silent recreation if missing and normal Compose volume removal. Server destruction still destroys its local data: off-host backup required. Never run down -v, volume rm/prune or reset on deployment.

Future authorized operator root shell only:

```sh
cd /opt/demand
docker volume create demand-single-database
DC=(docker compose --env-file /etc/demand/runtime.env --env-file /etc/demand/bootstrap-images.env -f /opt/demand/compose.prod.yml)
"${DC[@]}" config --quiet
"${DC[@]}" up -d --no-deps nginx
```

Install reviewed BACKEND_IMAGE/FRONTEND_IMAGE/POSTGRES_IMAGE/NGINX_IMAGE digests in bootstrap-images.env, root:0600. Stage A ingress blocks application/login and supports ACME only. Successful releases use `/var/lib/demand/releases/active.env`. See HTTPS runbook before deployment.

Runtime backend never receives owner migration URL. Owner-configured migration service is used only for controlled migration/manual management. Docker daemon/root access remains operator/restricted-helper only. No commands above were executed against production.

Initial backup prerequisite, only after separate runtime/storage authorization: using the reviewed DC array, run its Compose command with arguments up -d --no-deps --wait db. This starts the database only, not migration/backend/admin creation. Complete exact-snapshot SFTP restore acceptance and timer setup before release; current backup findings must first be remediated.
