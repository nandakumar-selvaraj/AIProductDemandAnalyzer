# Acceptance — Phase 5.17

Current evidence and recommendation: [Phase 5.17.1 remediation](PHASE_5_17_1_SECURITY_REMEDIATION.md). Earlier preparation reports are historical; their passes do not establish current image security, workflow success or live readiness.

Manual provisioning is NO-GO until a disposable Ubuntu VM passes fresh provisioning, failure recovery, Docker restart and reboot, relevant hosted CI is green, and the owner approves the quote. Application deployment is separately blocked on encrypted off-server restore acceptance, protected workflow settings, fixed-egress runner, same-SHA CI/publication, runtime secrets, DNS/TLS and owner authorization.

| Gate | Required acceptance |
| --- | --- |
| Host | Approved quote/inventory; exact Ubuntu/architecture; two operator sessions; tested console recovery; effective SSH/sudo; provider, nftables and Docker filtering; safe rerun/reboot |
| Delivery | Same-SHA backend/E2E/Docker/single validation and image publication; immutable scanned digests; independent protected approval; pinned SSH |
| Backup | Separate SFTP failure domain; password escrow; encrypted snapshot; full integrity check; exact snapshot/schema/business-data restore; failed drill invalidates acceptance; measured RPO/RTO |
| App/database | Actual migrations/readiness, owner/runtime separation, auth/CSRF/role/expiration behavior, uploads/forecasts, restart persistence and compatible rollback |
| HTTPS | Correct A/no stale AAAA, trusted certificate, redirect/no plaintext login, SPA/API routing, secure cookies, renewal/alerts |
| Operations | Disk/memory headroom, timers/failure alerts, reviewed retention, documented recovery and current cost |

All real cloud, GitHub-setting, off-server recovery, DNS/TLS and production-admin checks are NOT TESTED. No resources, administrators or storage were created or deleted. Dedicated Terraform/S3/KMS acceptance is inactive; no such backend is needed.
