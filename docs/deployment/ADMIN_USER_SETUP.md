# Manual administrator — NOT CREATED

Verified command: `python -m scripts.manage_users create --email ... --role admin`. Existing image includes script. It prompts password/confirmation without echo, enforces >=12 characters, uses existing Argon2id, rejects duplicate email, logs no password. Never invoked by Terraform/cloud-init/CI.

Only after approved deployment, migrations and HTTPS, use interactive operator SSH and an authorized root shell:

```sh
cd /opt/demand
DC=(docker compose --env-file /etc/demand/runtime.env --env-file /var/lib/demand/releases/active.env -f /opt/demand/compose.prod.yml)
"${DC[@]}" run --rm --no-deps migrate python -m scripts.manage_users create --email "admin@example.com" --role admin
```

Replace example email. Enter password only at prompts; no --password-stdin for production procedure and no password arguments/logs. The `migrate` service intentionally supplies owner DATABASE_URL: `exec backend` would use demand_app, which existing migrations deny INSERT on auth_users. Normal migration execution creates no administrator.

Reset/recovery via same owner service:

```sh
"${DC[@]}" run --rm --no-deps migrate python -m scripts.manage_users reset-password --email "admin@example.com"
```

Reset/disable/set-role revoke sessions and API tokens. Recover using operator/console and owner credentials, never public registration/database reset. Duplicate email is rejected; distinct administrator accounts remain possible. Volume preserves all accounts.

Verify valid/invalid login, Secure/HttpOnly cookie, admin writes, viewer denial, expired/invalid/missing JWT rejection, restore/expiry and logout revocation. Login issues a cookie plus session metadata, not JWT JSON. Record outcomes only. All production user creation/login checks NOT TESTED; these commands were not executed.
