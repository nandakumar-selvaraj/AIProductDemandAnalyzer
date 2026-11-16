"""Staged owner-run provisioning for the dedicated Ubuntu host."""

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import re
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path("/opt/demand")
ETC = Path("/etc/demand")
STATE = Path("/var/lib/demand")
SSH = Path("/etc/ssh/sshd_config")
DROPIN = SSH.parent / "sshd_config.d/00-demand-manual.conf"
DOCKER = Path("/etc/docker/daemon.json")
SUDO = Path("/etc/sudoers.d/demand")
SUDO_POLICY = b"""operator ALL=(ALL) NOPASSWD: ALL
deployer ALL=(root) NOPASSWD: /usr/local/sbin/demand-release ""
"""
SSH_POLICY = b"""PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
PermitUserEnvironment no
AllowUsers operator deployer
DisableForwarding yes
PermitTunnel no
MaxAuthTries 3
Match User deployer
  PermitTTY no
  ForceCommand /usr/bin/sudo -n /usr/local/sbin/demand-release
Match all
"""
DOCKER_POLICY = b"""{"log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"3"},"ipv6":false,"userland-proxy":false}
"""
DOCKER_UNIT = b"""[Unit]
Requires=demand-firewall.service
After=demand-firewall.service
"""
DEPLOY_COMMAND = 'restrict,command="/usr/bin/sudo -n /usr/local/sbin/demand-release" '


def run(*args):
    result = subprocess.run(args, capture_output=True, check=False, timeout=1200)
    if result.returncode:
        raise RuntimeError(f"Host check or command failed: {Path(args[0]).name}")
    return result.stdout


def reject(message):
    raise ValueError(message)


def trusted(path, *, directory=False, uid=0):
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, uid):
            reject(f"Unsafe parent: {parent}")
        if info.st_mode & 0o022:
            reject(f"Writable parent: {parent}")
    info = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid != uid or info.st_mode & 0o022:
        reject(f"Unsafe owner, type or permissions: {path}")
    if not directory and info.st_nlink != 1:
        reject(f"Unexpected hard link: {path}")
    return info


def source(path):
    if ".." in path.parts:
        reject("Source paths must be canonical")
    trusted(path.absolute())
    return path.read_bytes()


def atomic(path, content, mode=0o600, uid=0, gid=0):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        staged = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), uid, gid)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def managed(path, content, mode=0o600):
    if os.path.lexists(path):
        info = trusted(path)
        if path.read_bytes() != content or stat.S_IMODE(info.st_mode) != mode:
            reject(f"Existing configuration differs: {path}")
    else:
        atomic(path, content, mode)


def directory(path, mode=0o700):
    trusted(path.parent, directory=True)
    path.mkdir(mode=mode, exist_ok=True)
    info = trusted(path, directory=True)
    if stat.S_IMODE(info.st_mode) != mode:
        reject(f"Unexpected directory permissions: {path}")


def ensure_parent(path):
    parent = path.parent
    missing = []
    while not os.path.lexists(parent):
        missing.append(parent)
        parent = parent.parent
    trusted(parent, directory=True)
    for directory_path in reversed(missing):
        directory(directory_path, mode=0o755)


def key(path):
    parts = source(path).decode().strip().split()
    if len(parts) < 2 or parts[0] != "ssh-ed25519":
        reject("An Ed25519 public key is required")
    blob = base64.b64decode(parts[1], validate=True)
    if len(blob) != 51 or not blob.startswith(b"\0\0\0\x0bssh-ed25519\0\0\0\x20"):
        reject("Invalid Ed25519 key")
    return " ".join(parts[:2]), fingerprint(blob)


def fingerprint(blob):
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip(
        "="
    )


def networks(values):
    parsed = [ipaddress.IPv4Network(value, strict=True) for value in values]
    if (
        not 0 < len(parsed) <= 20
        or any(
            net.prefixlen < 24
            or not net.network_address.is_global
            or not net.broadcast_address.is_global
            or net.network_address.is_multicast
            for net in parsed
        )
        or any(a.overlaps(b) for i, a in enumerate(parsed) for b in parsed[i + 1 :])
    ):
        reject("Use distinct approved public IPv4 CIDRs, /24 or narrower")
    return sorted(parsed)


def firewall_policy(cidrs):
    ranges = ", ".join(map(str, networks(cidrs)))
    return f"""table inet demand_ingress {{
 chain input {{
  type filter hook input priority -10; policy drop;
  meta nfproto ipv6 drop
  iifname "lo" accept
  ct state invalid drop
  ct state established,related accept
  ip saddr {{ {ranges} }} tcp dport 22 ct state new accept
  tcp dport {{ 80, 443 }} ct state new accept
  icmp type {{ destination-unreachable, time-exceeded, parameter-problem }} accept
 }}
 chain forward {{
  type filter hook forward priority -10; policy drop;
  meta nfproto ipv6 drop
  ct state invalid drop
  ct state established,related accept
  iifname "docker0" accept
  iifname "br-*" accept
  oifname "br-*" tcp dport 8080 ct status dnat ct original proto-dst 80 accept
  oifname "br-*" tcp dport 8443 ct status dnat ct original proto-dst 443 accept
 }}
}}
""".encode()


def identity():
    machine = source(Path("/etc/machine-id")).decode().strip()
    if not re.fullmatch(r"[0-9a-f]{32}", machine):
        reject("Missing initialized machine identity")
    return {
        "machine": machine,
        "host_key": key(Path("/etc/ssh/ssh_host_ed25519_key.pub"))[1],
    }


def initial(create):
    os_release = source(Path("/usr/lib/os-release")).decode()
    if (
        os.geteuid() != 0
        or not re.search(r"^ID=ubuntu$", os_release, re.M)
        or not re.search(r'^VERSION_ID="24\.04"$', os_release, re.M)
        or run("dpkg", "--print-architecture").strip() != b"amd64"
    ):
        reject("Root on Ubuntu 24.04 amd64 is required")
    for path in (HERE, Path("/home")):
        trusted(path, directory=True)
    for path in (ETC, STATE, BASE):
        if create:
            directory(path)
        else:
            trusted(path, directory=True)
    run("sshd", "-t")
    run("visudo", "-c")


def ssh_digest():
    paths = [SSH, *sorted(DROPIN.parent.glob("*.conf"))]
    return hashlib.sha256(b"\0".join(source(path) for path in paths)).hexdigest()


def account(user, public_key, *, create):
    import grp
    import pwd

    home = Path("/home") / user
    primary = "demand-" + user
    if create:
        run("groupadd", primary)
        run("useradd", "--create-home", "--gid", primary, "--shell", "/bin/bash", user)
    record = pwd.getpwnam(user)
    if grp.getgrgid(record.pw_gid).gr_name != primary:
        reject("Unexpected primary group")
    if (
        record.pw_dir != str(home)
        or record.pw_shell != "/bin/bash"
        or record.pw_uid < 1000
    ):
        reject("Unexpected account details")
    if run("id", "-G", user).split() != [str(record.pw_gid).encode()]:
        reject("Unexpected supplementary groups")
    if run("passwd", "-S", user).split()[1] != b"L":
        reject("Managed accounts must have locked passwords")
    trusted(home, directory=True, uid=record.pw_uid)
    ssh = home / ".ssh"
    auth = ssh / "authorized_keys"
    content = (
        (DEPLOY_COMMAND if user == "deployer" else "") + public_key + "\n"
    ).encode()
    if create:
        ssh.mkdir(mode=0o700)
        os.chown(ssh, record.pw_uid, record.pw_gid)
        atomic(auth, content, uid=record.pw_uid, gid=record.pw_gid)
    if (
        stat.S_IMODE(trusted(ssh, directory=True, uid=record.pw_uid).st_mode) != 0o700
        or stat.S_IMODE(trusted(auth, uid=record.pw_uid).st_mode) != 0o600
        or auth.read_bytes() != content
    ):
        reject("Managed SSH authorization changed")


def record(name):
    return json.loads(source(STATE / name))


def save(name, value):
    target = STATE / name
    if os.path.lexists(target):
        trusted(target)
    atomic(target, json.dumps(value, sort_keys=True).encode())


def prepare(operator, deployer, cidrs):
    import pwd

    operator_key, operator_fp = key(operator)
    deployer_key, _ = key(deployer)
    if operator_key == deployer_key:
        reject("Operator and deployer keys must differ")
    settings = {
        **identity(),
        "operator": operator_key,
        "operator_fp": operator_fp,
        "deployer": deployer_key,
        "cidrs": list(map(str, networks(cidrs))),
        "sshd": ssh_digest(),
    }
    if (STATE / "host-ready").exists() or os.path.lexists(DROPIN):
        reject("Use check for a provisioned host")
    if (STATE / "prepared.json").exists():
        if record("prepared.json") != settings:
            reject("Prepared host no longer matches the approved inputs")
        for name in ("operator", "deployer"):
            account(name, settings[name], create=False)
        if source(SUDO) != SUDO_POLICY:
            reject("Prepared sudoers changed")
    else:
        if os.path.lexists(SUDO) or (STATE / "prepare-in-progress.json").exists():
            reject("Interrupted or customized preparation needs console review")
        for name in ("operator", "deployer"):
            try:
                pwd.getpwnam(name)
            except KeyError:
                pass
            else:
                reject("Existing operator or deployer needs separate owner review")
            if os.path.lexists(Path("/home") / name):
                reject("An unexpected home already exists")
            if (
                subprocess.run(
                    ["getent", "group", "demand-" + name], capture_output=True
                ).returncode
                != 2
            ):
                reject("An unexpected account group already exists")
        save("prepare-in-progress.json", settings)
        for name in ("operator", "deployer"):
            account(name, settings[name], create=True)
        with tempfile.TemporaryDirectory(dir=STATE) as folder:
            policy = Path(folder) / "sudoers"
            atomic(policy, SUDO_POLICY, 0o440)
            run("visudo", "-cf", str(policy))
        managed(SUDO, SUDO_POLICY, 0o440)
        run("visudo", "-c")
        save("prepared.json", settings)
    save(
        "challenge.json",
        {"issued": time.time_ns() // 1000, "nonce": secrets.token_hex(16)},
    )
    print("Preparation complete. Open a new operator SSH session and verify from it.")
    print("Challenge: " + record("challenge.json")["nonce"])
    print("Console host key fingerprint: " + settings["host_key"])


def challenge(nonce):
    prepared = record("prepared.json")
    ticket = record("challenge.json")
    if (
        not secrets.compare_digest(ticket["nonce"], nonce)
        or not 0 <= time.time_ns() // 1000 - ticket["issued"] <= 1800 * 10**6
        or identity() != {k: prepared[k] for k in ("machine", "host_key")}
        or ssh_digest() != prepared["sshd"]
        or source(SUDO) != SUDO_POLICY
    ):
        reject("Preparation challenge expired or host configuration changed")
    for name in ("operator", "deployer"):
        account(name, prepared[name], create=False)
    run("visudo", "-c")
    return prepared, ticket


def ancestors():
    pid = os.getppid()
    while pid > 1:
        entry = Path("/proc") / str(pid)
        status = (entry / "status").read_text()
        uid = int(re.search(r"^Uid:[ \t]+(\d+)", status, re.M)[1])
        yield pid, (entry / "comm").read_text().strip(), uid
        pid = int(re.search(r"^PPid:\s+(\d+)$", status, re.M)[1])


def operator_peer(processes, journal, expected_key, cidrs, issued):
    pids = {
        pid
        for pid, name, uid in processes
        if uid == 0 and name in {"sshd", "sshd-session"}
    }
    for entry in journal:
        message = entry.get("MESSAGE", "")
        match = re.fullmatch(
            r"Accepted publickey for operator from ([0-9.]+) port [0-9]+ ssh2: ED25519 (SHA256:\S+)",
            message,
        )
        if (
            entry.get("_PID", "").isdigit()
            and int(entry["_PID"]) in pids
            and entry.get("_UID") == "0"
            and int(entry.get("__REALTIME_TIMESTAMP", "0")) > issued
            # journald may omit executable metadata for sandboxed SSH processes.
            and entry.get("_EXE", "/usr/sbin/sshd")
            in {"/usr/sbin/sshd", "/usr/lib/openssh/sshd-session"}
            and match
        ):
            peer = ipaddress.IPv4Address(match[1])
            if match[2] == expected_key and any(peer in net for net in networks(cidrs)):
                return str(peer)
    reject("Open a fresh, approved-source SSH connection using the prepared key")


def verify(nonce):
    prepared, ticket = challenge(nonce)
    if os.environ.get("SUDO_USER") != "operator":
        reject("Invoke verify using sudo from the new operator session")
    logs = run(
        "journalctl",
        "-b",
        "--since",
        f"@{ticket['issued'] // 10**6}",
        "-o",
        "json",
        "--no-pager",
        "_COMM=sshd",
        "_COMM=sshd-session",
    )
    peer = operator_peer(
        ancestors(),
        (json.loads(line) for line in logs.splitlines()),
        prepared["operator_fp"],
        prepared["cidrs"],
        ticket["issued"],
    )
    save("operator-proof.json", {**ticket, "peer": peer})
    print("Independent operator public-key login and sudo verified.")


def require_console():
    if not re.fullmatch(r"/dev/tty(?:[0-9]+|S[0-9]+)", os.ttyname(0)) or any(
        name.startswith("sshd") for _, name, _ in ancestors()
    ):
        reject("Verify recovery from the authenticated out-of-band console")


def recovery(nonce):
    _, ticket = challenge(nonce)
    require_console()
    save("console-proof.json", ticket)
    print("Console root recovery verified. Keep this console open.")


def effective(config=None, peer="127.0.0.1"):
    for user in ("operator", "deployer", "root"):
        flags = ["-f", str(config)] if config is not None else []
        result = run("sshd", "-T", *flags, "-C", f"user={user},host={peer},addr={peer}")
        lines = result.decode().splitlines()
        required = {
            "permitrootlogin no",
            "passwordauthentication no",
            "kbdinteractiveauthentication no",
            "pubkeyauthentication yes",
            "authenticationmethods publickey",
            "permituserenvironment no",
            "disableforwarding yes",
            "permittunnel no",
        }
        if not required <= set(lines) or {
            line for line in lines if line.startswith("allowusers ")
        } != {"allowusers operator", "allowusers deployer"}:
            reject("Effective SSH policy differs from the candidate")
        if user == "operator" and (
            "forcecommand none" not in lines
            or not any(
                line.startswith("authorizedkeysfile ")
                and ".ssh/authorized_keys" in line.split()[1:]
                for line in lines
            )
        ):
            reject("Operator login would no longer use the verified key")
        if user == "deployer" and not {
            "permittty no",
            "forcecommand /usr/bin/sudo -n /usr/local/sbin/demand-release",
        } <= set(lines):
            reject("Deployer is not restricted")


def ssh_activate(peer):
    original = source(SSH)
    if any(
        re.match(rb"^\s*Match\b", line, re.I)
        for path in [SSH, *DROPIN.parent.glob("*.conf")]
        for line in source(path).splitlines()
    ):
        reject("Existing conditional sshd policy requires separate maintenance")
    if b"Include /etc/ssh/sshd_config.d/*.conf" not in original.splitlines():
        reject("Unsupported sshd Include layout")
    with tempfile.TemporaryDirectory(dir=STATE) as folder:
        candidate = Path(folder) / "sshd_config"
        fragment = Path(folder) / "demand.conf"
        atomic(fragment, SSH_POLICY)
        includes = sorted([*DROPIN.parent.glob("*.conf"), DROPIN])
        included = "\n".join(
            f"Include {fragment if path == DROPIN else path}" for path in includes
        )
        atomic(
            candidate,
            original.replace(
                b"Include /etc/ssh/sshd_config.d/*.conf", included.encode(), 1
            ),
        )
        run("sshd", "-t", "-f", str(candidate))
        effective(candidate, peer)
    managed(STATE / "sshd-before.conf", original)
    managed(DROPIN, SSH_POLICY, 0o644)
    try:
        run("sshd", "-t")
        effective(peer=peer)
        run("systemctl", "reload", "ssh")
    except BaseException:
        if source(DROPIN) == SSH_POLICY:
            DROPIN.unlink()
            run("sshd", "-t")
            run("systemctl", "reload", "ssh")
        raise


def packages(*names):
    run("apt-get", "-o", "DPkg::Options::=--force-confold", "install", "-y", *names)


def fresh_host():
    for name in (
        "docker",
        "dockerd",
        "containerd",
        "podman",
    ):
        if any(
            (Path(folder) / name).exists()
            for folder in ("/usr/bin", "/usr/local/bin", "/snap/bin")
        ):
            reject("Existing container installation needs separate maintenance")
    for path in (
        DOCKER,
        Path("/var/lib/docker"),
        Path("/etc/apt/keyrings/docker.asc"),
        Path("/etc/apt/sources.list.d/demand-docker.list"),
        Path("/etc/apt/sources.list.d/docker.list"),
        Path("/etc/apt/sources.list.d/docker.sources"),
    ):
        if os.path.lexists(path):
            reject("Existing Docker data or configuration needs separate maintenance")
    if (STATE / "finalize-in-progress.json").exists():
        reject("Interrupted finalization needs console review")
    # Reject active legacy firewall policy wholesale. Never remove rules owned by another tool.
    if Path("/etc/ufw/ufw.conf").exists() and not re.search(
        rb"^ENABLED=no\s*$", source(Path("/etc/ufw/ufw.conf")), re.M
    ):
        reject("Existing UFW policy needs separate console maintenance")
    for command in ("iptables-save", "ip6tables-save"):
        result = run(command)
        if any(
            line.startswith(b"-A ")
            or (line.startswith(b":") and b" ACCEPT " not in line)
            for line in result.splitlines()
        ):
            reject("Existing iptables policy needs separate console maintenance")
    routes = json.loads(run("ip", "-j", "-4", "route", "show", "default"))
    if not routes or any(
        not route.get("dev") or route["dev"].startswith(("docker", "br-"))
        for route in routes
    ):
        reject("Unsupported default route for a dedicated IPv4 host")


def assets():
    mapping = {
        BASE / "compose.prod.yml": (HERE.parents[1] / "compose.prod.yml", 0o600),
        BASE / "nginx.stage-a.conf": (HERE / "nginx.stage-a.conf", 0o644),
        BASE / "nginx.tls.conf": (HERE / "nginx.tls.conf", 0o644),
        BASE / "init-db.sh": (HERE / "init-db.sh", 0o644),
        BASE / "release.py": (HERE / "release.py", 0o600),
        BASE / "backup_state.py": (HERE / "backup_state.py", 0o600),
        Path("/usr/local/sbin/demand-release"): (HERE / "release-entry.sh", 0o700),
        Path("/etc/letsencrypt/renewal-hooks/deploy/demand"): (
            HERE / "renew-certificate.sh",
            0o700,
        ),
    }
    for name in (
        "backup-common",
        "backup-preflight",
        "backup",
        "restore-verify",
        "backup-retention",
        "docker-firewall",
        "host-check",
        "host-monitor",
    ):
        mapping[BASE / (name + ".sh")] = (HERE / (name + ".sh"), 0o700)
    for name in ("alert", "backup", "firewall", "monitor"):
        unit = f"demand-{name}.service"
        mapping[Path("/etc/systemd/system") / unit] = (HERE / "systemd" / unit, 0o644)
    for name in ("backup", "monitor"):
        unit = f"demand-{name}.timer"
        mapping[Path("/etc/systemd/system") / unit] = (HERE / "systemd" / unit, 0o644)
    return {dest: (source(src), mode) for dest, (src, mode) in mapping.items()}


def verify_proofs(prepared, ticket):
    console = record("console-proof.json")
    operator = record("operator-proof.json")
    if (
        console != ticket
        or {k: operator.get(k) for k in ticket} != ticket
        or not any(
            ipaddress.IPv4Address(operator["peer"]) in net
            for net in networks(prepared["cidrs"])
        )
    ):
        reject("Both current verification receipts are required")
    return operator["peer"]


def finalize(nonce):
    prepared, ticket = challenge(nonce)
    peer = verify_proofs(prepared, ticket)
    fresh_host()
    files = assets()
    static = {
        ETC / "firewall.nft": (firewall_policy(prepared["cidrs"]), 0o600),
        Path("/etc/systemd/system/docker.service.d/demand.conf"): (DOCKER_UNIT, 0o644),
        Path("/etc/systemd/system/docker.socket.d/demand.conf"): (DOCKER_UNIT, 0o644),
        Path("/etc/systemd/journald.conf.d/demand.conf"): (
            b"[Journal]\nStorage=persistent\nSystemMaxUse=200M\n",
            0o644,
        ),
        Path("/etc/apt/apt.conf.d/99-demand-security-updates"): (
            b'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n',
            0o644,
        ),
    }
    files.update(static)
    files[BASE / "nginx.conf"] = (files[BASE / "nginx.stage-a.conf"][0], 0o644)
    for path in files:
        if os.path.lexists(path):
            reject(f"Existing managed target requires review: {path}")
    save("finalize-in-progress.json", {"peer": peer})
    run("apt-get", "update")
    packages(
        "nftables",
        "ca-certificates",
        "curl",
        "gnupg",
        "restic",
        "certbot",
        "unattended-upgrades",
    )
    if run("nft", "list", "tables").strip():
        reject("An existing nftables policy requires console review")
    if (
        subprocess.run(
            ["systemctl", "is-enabled", "--quiet", "nftables.service"]
        ).returncode
        == 0
    ):
        reject("Disable the separate nftables loader in reviewed maintenance")
    for path in files:
        ensure_parent(path)
    directory(STATE / "releases")
    with tempfile.TemporaryDirectory(dir=STATE) as folder:
        candidate = Path(folder) / "firewall.nft"
        atomic(candidate, files[ETC / "firewall.nft"][0])
        run("nft", "--check", "--file", str(candidate))
    for path, (content, mode) in files.items():
        managed(path, content, mode)
    run("systemd-analyze", "verify", "/etc/systemd/system/demand-firewall.service")
    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "--now", "demand-firewall.service")
    # Docker package scripts may start Docker. The firewall is already loaded and a required unit.
    with tempfile.TemporaryDirectory(dir=STATE) as folder:
        vendor_key = Path(folder) / "docker.asc"
        run(
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--proto",
            "=https",
            "--tlsv1.2",
            "https://download.docker.com/linux/ubuntu/gpg",
            "-o",
            str(vendor_key),
        )
        listing = run("gpg", "--batch", "--show-keys", "--with-colons", str(vendor_key))
        primary, fingerprints = False, []
        for row in listing.decode().splitlines():
            fields = row.split(":")
            if fields[0] in {"pub", "sub"}:
                primary = fields[0] == "pub"
            if primary and fields[0] == "fpr":
                fingerprints.append(fields[9])
                primary = False
        if fingerprints != ["9DC858229FC7DD38854AE2D88D81803C0EBFCD88"]:
            reject("Docker vendor key failed fingerprint verification")
        keyring = Path("/etc/apt/keyrings")
        ensure_parent(keyring / "docker.asc")
        managed(keyring / "docker.asc", source(vendor_key), 0o644)
    managed(
        Path("/etc/apt/sources.list.d/demand-docker.list"),
        b"deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable\n",
        0o644,
    )
    run("apt-get", "update")
    packages(
        "docker-ce",
        "docker-ce-cli",
        "containerd.io",
        "docker-buildx-plugin",
        "docker-compose-plugin",
    )
    ensure_parent(DOCKER)
    with tempfile.TemporaryDirectory(dir=STATE) as folder:
        candidate = Path(folder) / "daemon.json"
        atomic(candidate, DOCKER_POLICY)
        run("dockerd", "--validate", "--config-file", str(candidate))
    managed(DOCKER, DOCKER_POLICY, 0o644)
    run("systemctl", "enable", "docker.service")
    run("systemctl", "restart", "docker.service")
    run("docker", "compose", "version")
    run("systemctl", "enable", "--now", "apt-daily.timer", "apt-daily-upgrade.timer")
    run("visudo", "-c")
    # Require the same prepared configuration and proofs immediately before replacing sshd policy.
    verify_proofs(*challenge(nonce))
    ssh_activate(peer)
    save("host-ready", {"peer": peer})
    print(
        "Host provisioning completed. Keep console open and test a new operator connection."
    )


def check():
    state = record("host-ready")
    effective(peer=state["peer"])
    if (
        source(DROPIN) != SSH_POLICY
        or source(SUDO) != SUDO_POLICY
        or source(DOCKER) != DOCKER_POLICY
    ):
        reject("Managed host configuration differs")
    settings = record("prepared.json")
    for name in ("operator", "deployer"):
        account(name, settings[name], create=False)
    for service in ("docker.service", "demand-firewall.service"):
        run("systemctl", "is-active", "--quiet", service)
    run("nft", "list", "table", "inet", "demand_ingress")
    print("Managed SSH policy and host services verified.")


def update_firewall(cidrs):
    require_console()
    host = record("host-ready")
    if not any(ipaddress.IPv4Address(host["peer"]) in net for net in networks(cidrs)):
        reject(
            "Preserve the verified operator source; use reviewed maintenance to change it"
        )
    candidate = firewall_policy(cidrs)
    if subprocess.run(
        [str(BASE / "docker-firewall.sh"), "--update"],
        input=candidate,
        capture_output=True,
        check=False,
        timeout=60,
    ).returncode:
        reject("Firewall candidate was rejected; inspect the console")
    print(
        "Firewall rules committed. Re-test approved sources and use the provider firewall too."
    )


def terminated(_signum, _frame):
    raise InterruptedError("Host operation interrupted")


def main():
    import fcntl

    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    first = commands.add_parser("prepare")
    first.add_argument("operator", type=Path)
    first.add_argument("deployer", type=Path)
    first.add_argument("cidrs", nargs="+")
    for operation in ("verify", "recovery", "finalize"):
        commands.add_parser(operation).add_argument("nonce")
    commands.add_parser("check")
    commands.add_parser("firewall-update").add_argument("cidrs", nargs="+")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, terminated)
    os.umask(0o077)
    initial(args.command == "prepare")
    with (STATE / "bootstrap.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == "prepare":
            prepare(args.operator, args.deployer, args.cidrs)
        elif args.command == "firewall-update":
            update_firewall(args.cidrs)
        elif args.command == "check":
            check()
        else:
            {"verify": verify, "recovery": recovery, "finalize": finalize}[
                args.command
            ](args.nonce)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Host checks never process private key material or print command output.
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
