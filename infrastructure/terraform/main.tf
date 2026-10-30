locals {
  files = {
    "/usr/local/lib/portfolio/compose.production.yml" = "../../compose.production.yml"
    "/usr/local/sbin/portfolio-release"               = "release.py"
    "/usr/local/lib/portfolio/compose.app.yml"        = "compose.app.yml"
    "/usr/local/lib/portfolio/compose.ingress.yml"    = "compose.ingress.yml"
    "/usr/local/lib/portfolio/init-db.sh"             = "../init-db.sh"
    "/usr/local/lib/portfolio/backup.sh"              = "backup-offhost.sh"
    "/usr/local/lib/portfolio/restore-verify.sh"      = "restore-verify.sh"
    "/usr/local/lib/portfolio/monitor.sh"             = "monitor.sh"
    "/usr/local/lib/portfolio/operations.py"          = "operations.py"
  }
}

resource "upcloud_storage" "data" {
  title   = "portfolio-persistent-data"
  zone    = var.zone
  size    = var.data_size_gb
  tier    = "maxiops"
  encrypt = true
  lifecycle { prevent_destroy = true }
}

resource "upcloud_server" "portfolio" {
  hostname = "portfolio-vps"
  title    = "Shared portfolio VPS"
  zone     = var.zone
  plan     = var.plan
  firewall = true
  metadata = true
  login {
    user              = "operator"
    keys              = [var.operator_ssh_public_key]
    create_password   = false
    password_delivery = "none"
  }
  template {
    storage          = "Ubuntu Server 24.04 LTS (Noble Numbat)"
    size             = 25
    tier             = "maxiops"
    encrypt          = true
    address          = "virtio"
    address_position = "0"
  }
  storage_devices {
    storage          = upcloud_storage.data.id
    address          = "virtio"
    address_position = "1"
    type             = "disk"
  }
  network_interface {
    type              = "public"
    ip_address_family = "IPv4"
  }
  user_data = templatefile("${path.module}/cloud-init.yml.tftpl", {
    deploy_user  = var.deploy_user
    deploy_key   = jsonencode(var.deploy_ssh_public_key)
    operator_key = jsonencode(var.operator_ssh_public_key)
    ssh_cidrs    = jsonencode(var.ssh_allowed_cidrs)
    bootstrap    = filebase64("${path.module}/bootstrap.sh")
    files        = { for target, source in local.files : target => filebase64("${path.module}/../../deploy/ops/${source}") }
  })
  lifecycle { prevent_destroy = true }
}

resource "upcloud_firewall_rules" "portfolio" {
  server_id = upcloud_server.portfolio.id
  dynamic "firewall_rule" {
    for_each = var.ssh_allowed_cidrs
    content {
      action                 = "accept"
      direction              = "in"
      family                 = "IPv4"
      protocol               = "tcp"
      destination_port_start = "22"
      destination_port_end   = "22"
      source_address_start   = cidrhost(firewall_rule.value, 0)
      source_address_end     = cidrhost(firewall_rule.value, -1)
      comment                = "Restricted SSH"
    }
  }
  dynamic "firewall_rule" {
    for_each = toset(["80", "443"])
    content {
      action                 = "accept"
      direction              = "in"
      family                 = "IPv4"
      protocol               = "tcp"
      destination_port_start = firewall_rule.value
      destination_port_end   = firewall_rule.value
      comment                = "Shared HTTPS ingress and ACME redirect"
    }
  }
  firewall_rule {
    action    = "accept"
    direction = "in"
    family    = "IPv4"
    protocol  = "icmp"
    comment   = "Network diagnostics and path MTU"
  }
  firewall_rule {
    action    = "drop"
    direction = "in"
  }
  firewall_rule {
    action    = "accept"
    direction = "out"
  }
}
