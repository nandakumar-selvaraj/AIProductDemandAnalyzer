# Temporary subdomain and later domain migration

Phase 8A prepares files only. In authorized Phase 8B:

1. Review cost, zone/plan, SSH keys/CIDRs, protected Environment and remote state.
2. Run manual Terraform plan, review its sanitized summary and explicitly approve the
   saved-plan apply. No APP_DOMAIN or ACME_EMAIL is needed for this VPS-only step.
3. **Stop after apply.** Copy the public IPv4 from its summary and send it to your friend
   yourself. No message to your friend is sent automatically.
4. Ask for a temporary hostname's DNS **A** record pointing to that IP. Remove stale A
   records and unsupported AAAA records; this design provisions IPv4 only. Avoid proxy/CDN
   modes for initial direct-IP validation. Allow DNS TTL/propagation to complete.
5. Set DEPLOY_HOST, APP_DOMAIN and ACME_EMAIL in the production Environment. Verify host
   SSH keys independently; prepare private host/backup configuration and fresh database.
6. Manual production deployment validates exact IPv4 resolution on both CI and the VPS
   before Caddy starts/certificates are requested. All returned A records must equal the
   server IPv4; any AAAA record fails the gate. No public HTTP-only application is enabled.
7. Verify publicly trusted HTTPS, login/logout, Admin/Viewer controls and a synthetic CSV
   upload. Ask your friend to test only after the deployment and authentication checks pass.

AUTH_ALLOWED_ORIGINS and TRUSTED_HOSTS are derived by the root release entrypoint from
the active hostname, not independently edited or baked into Angular. Production Angular
uses relative `/api/v1` URLs. Cookies are Secure/HttpOnly/Strict and session expiry stays
30 minutes. Existing local accounts/data are never copied to the fresh production DB.

## Remove the temporary hostname without deleting infrastructure

Use the approved manual `production-deploy` operation `remove-domain`, referencing the
currently active verified build/hostname. It detaches only this app's Caddy site and keeps
the VPS, PostgreSQL database/volume, usage state and shared certificates/other sites.
Then ask your friend to delete the A record. Clear APP_DOMAIN in GitHub to prevent an
accidental redeployment using the retired hostname. Keep the previous non-secret release
record for recovery. Monitoring continues checking DB/API/backups while intentionally
detached; no temporary HTTP workaround or Terraform destroy is involved.

## Move to your own domain later

Purchasing a domain is a separate explicit decision. Configure its A record, update
APP_DOMAIN/ACME_EMAIL and run the approved deployment with verified digests. The same VPS
and database remain; no Terraform input or replacement changes with hostname migration.
For a smooth cutover, keep old DNS controlled until new TLS/authentication is verified,
then remove its record. The entrypoint updates the site's hostname and exact auth origin
together. New hostname cookies are separate; users must log in again. Server-side old
sessions expire/revoke normally; rotate the signing key explicitly if invalidating all
sessions/API tokens is desired. Never copy browser cookies between domains.
