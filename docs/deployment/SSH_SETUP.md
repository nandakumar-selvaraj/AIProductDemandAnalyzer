# SSH and host recovery

Use the three-stage [manual provisioning procedure](UPCLOUD_MANUAL_PROVISIONING.md). Keep the initial access channel, an independent verified operator session and an authenticated provider console available while changing SSH and firewall policy. The operator login proof binds the prepared Ed25519 public key, approved source, host identity and current sudo session. The recovery proof requires a local root console.

Use distinct Ed25519 identities. The operator has recovery sudo. The deployer has only the fixed `/usr/local/sbin/demand-release` command, restricted key options, no forwarding or TTY, and no Docker group access.

Verify the host key out of band. Pin the single exact IPv4 and key in `AIPD_DEPLOY_SSH_KNOWN_HOSTS` and the independently obtained fingerprint in `SINGLE_DEPLOY_HOST_KEY_FINGERPRINT`. Compare the live fingerprint with the console value before entering credentials or confirming an SSH identity. Repeat after a reviewed host rebuild or key rotation.

If a stage fails, retain authenticated sessions. Inspect the effective configuration at the console, keep both network policies scoped to approved operator sources, and use the saved baseline and owner recovery procedure. Before authorizing provisioning, rehearse SSH and console recovery at reboot and after failed candidate activation.
