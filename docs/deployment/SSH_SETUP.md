# SSH and host recovery

The authoritative procedure is [manual provisioning](UPCLOUD_MANUAL_PROVISIONING.md). Current bootstrap has unresolved lockout/rerun risks; do not execute it on the paid host until remediated and locally rehearsed.

Use distinct operator and deployer Ed25519 keys. The operator has full sudo recovery authority; the deployer must have only the root-owned release entrypoint, forced command, no TTY or forwarding and no Docker membership. Protect operator private key with a passphrase; CI receives only its separate deployment key.

Verify host Ed25519 fingerprint through trusted console, then pin the single exact IPv4/key in AIPD_DEPLOY_SSH_KNOWN_HOSTS and fingerprint in SINGLE_DEPLOY_HOST_KEY_FINGERPRINT. Never trust ssh-keyscan alone. Verify effective sshd settings for both users, second-session operator sudo, allowed/disallowed source networks and recovery before closing original access.

Cloud and host firewalls allow22 only from approved operator/runner IPv4 CIDRs,80/443 publicly, diagnostics as reviewed, then inbound drop. No public IPv6, PostgreSQL or Ollama. Use an isolated fixed-egress runner outside the VPS. Host firewall rules must be inspected for pre-existing broad allowances; default deny does not remove them.

Historical Terraform/cloud-init and demand-harden-ssh installation instructions are inactive for this manual path. bootstrap-host.sh installs its own SSH policy; do not assume the historical helper is installed.
