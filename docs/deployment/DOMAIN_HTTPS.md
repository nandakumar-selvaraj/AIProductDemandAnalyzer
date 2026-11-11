> Phase 5.17: follow [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md) and [current audit stop gates](PHASE_5_17_FINAL_VALIDATION.md). Commands below are future separately authorized operations, not part of this audit. Active backups use [encrypted SFTP/Restic](BACKUP_RESTORE.md); no dedicated Terraform/S3/KMS is required.

# Domain and HTTPS

Stage A: public-IP operational inspection only. `nginx.stage-a.conf` allows ingress health and ACME challenge; app/login paths return503. No credentials over HTTP and no assumed IP certificate. API checks may run privately over operator SSH.

After explicit authorization and subdomain supply:

1. Configure A to VPS, remove stale AAAA unless IPv6 deliberately configured. Verify authoritative/public DNS matches expected IP. Set exact runtime HTTPS origins/hosts.
2. Start Stage A ingress with reviewed bootstrap digests (Compose guide). On host obtain certificate: `certbot certonly --webroot -w /var/lib/letsencrypt -d YOUR_SUBDOMAIN --email YOUR_EMAIL --agree-tos`. Rehearse staging first; production issuance requires approval. Not executed now.
3. Create `/etc/demand/tls` root:101 mode0750. Copy fullchain root:101 mode0644 and private key root:101 mode0640. Verify approved ingress UID/GID101. Container sees only TLS copies, not all host certificate keys.
4. Replace only DOMAIN in `/opt/demand/nginx.tls.conf` with validated hostname; install as nginx.conf. Write hostname alone to root-only `/etc/demand/domain`. Test nginx -t in approved image. Dynamic Docker DNS permits config testing before app services exist.
5. Using bootstrap env, recreate only nginx with --no-deps. Verify HTTP redirect and trusted HTTPS hostname/certificate. API can remain unavailable before app startup. Create root-only `/etc/demand/tls-ready` only after certificate/config verification; this marker does not claim application readiness.
6. Dispatch separately approved application workflow. Pre-created external DB volume/runtime config are required. First release migrates, compares heads, waits readiness and verifies API/SPA through trusted local HTTPS with public hostname.
7. Externally verify public HTTPS, cookies/CSRF, SPA deep links, API routing, caching/security headers and certificate renewal.

Install root-owned `deploy/single/renew-certificate.sh` in `/etc/letsencrypt/renewal-hooks/deploy/`. It copies renewed cert/key with restricted permissions, tests config and reloads Nginx using active (or bootstrap) env. Enable packaged certbot.timer; test `certbot renew --dry-run` and hook/reload separately. Monitor failures/expiry before calling renewal operational.

Public production Swagger remains denied by existing app policy. Public authentication is NOT READY until external TLS/cookie acceptance passes. No DNS/certificate/deployment action performed now.
