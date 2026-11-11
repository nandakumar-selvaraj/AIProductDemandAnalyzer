# Active dedicated configuration — Phase 5.17

No secrets were read, generated or installed; no GitHub settings were changed.

| Location | Name | Purpose |
| --- | --- | --- |
| Protected aiproductdemand-production Environment secret | AIPD_DEPLOY_SSH_PRIVATE_KEY | Distinct unencrypted OpenSSH Ed25519 deployer key; never operator key |
| Same Environment secret | AIPD_DEPLOY_SSH_KNOWN_HOSTS | One IPv4 ssh-ed25519 KEY line verified against console |
| Same Environment variable | SINGLE_DEPLOY_HOST | Approved public IPv4 |
| Same Environment variable | SINGLE_DEPLOY_HOST_KEY_FINGERPRINT | Independently console-verified SHA256 fingerprint |
| Repository/organization configuration variable | SINGLE_DEPLOY_RUNNER_LABEL | Fixed-egress isolated runner label available during runner selection |
| Automatic workflow token | GITHUB_TOKEN | GitHub read checks; GHCR write in publication job only |

Owner-approved SSH CIDRs are configured in UpCloud and the host firewall, not Terraform inputs. Do not create same-named repository/organization fallback secrets; audit scopes before release.

Host-only /etc/demand/runtime.env must be root:root 0600. Use deploy/single/runtime.env.example: separate POSTGRES_PASSWORD and APP_DB_PASSWORD, JWT_SIGNING_SECRET, credential-bearing DATABASE_URL and MIGRATION_DATABASE_URL, exact HTTPS origins/trusted hosts. Use at least 64 random JWT characters, correctly encoded URL credentials and safe Compose quoting. Never put secrets in Angular, images, artifacts or logs. AI remains disabled.

Backup files /etc/demand/backup.env, restic-password, backup-key and backup-known-hosts must all be root:root 0600. Use the supplied SFTP example, separate off-server public IPv4, restricted SFTP account and independently verified Ed25519 pin. Escrow encryption password and recovery configuration independently of the VPS. See [backup/recovery](BACKUP_RESTORE.md).

HISTORICAL AND INACTIVE: AIPD_UPCLOUD_TOKEN, AIPD_TF_STATE_*, dedicated SINGLE_UPCLOUD_*, SINGLE_STORAGE_TIER, Terraform public-key variables and S3/KMS state configuration. Do not add these for manual provisioning. Preserve any existing state/credentials pending separately approved inventory and retirement. Legacy shared credentials are outside this procedure.

Rotation requires maintenance planning: verify alternate SSH access before removing keys, update database roles and URLs together, revoke sessions when replacing JWT material. The initializer does not rotate existing roles.

Runner-selection scope: [GitHub variables reference](https://docs.github.com/en/actions/reference/workflows-and-actions/variables).
