locals {
  deployment_files = {
    "/opt/demand/compose.prod.yml"      = "../../compose.prod.yml"
    "/opt/demand/init-db.sh"            = "../../deploy/single/init-db.sh"
    "/opt/demand/nginx.stage-a.conf"    = "../../deploy/single/nginx.stage-a.conf"
    "/opt/demand/nginx.tls.conf"        = "../../deploy/single/nginx.tls.conf"
    "/opt/demand/release.py"            = "../../deploy/single/release.py"
    "/opt/demand/backup.sh"             = "../../deploy/single/backup.sh"
    "/opt/demand/restore-verify.sh"     = "../../deploy/single/restore-verify.sh"
    "/opt/demand/renew-certificate.sh"  = "../../deploy/single/renew-certificate.sh"
    "/usr/local/sbin/demand-release"    = "../../deploy/single/release-entry.sh"
    "/usr/local/sbin/demand-harden-ssh" = "../../deploy/single/harden-ssh.sh"
  }
}

resource "upcloud_server" "app" {
  hostname = var.server_hostname
  title    = "${var.project_name}-${var.environment} (Demo 3 only)"
  zone     = var.upcloud_zone
  plan     = var.server_plan
  timezone = var.server_timezone
  firewall = true
  metadata = true
  labels = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform-single-app"
  }
  login {
    user              = "operator"
    keys              = [var.ssh_public_key]
    create_password   = false
    password_delivery = "none"
  }
  template {
    storage = "Ubuntu Server 24.04 LTS (Noble Numbat)"
    title   = "${var.project_name}-persistent-boot"
    size    = 30
    tier    = var.boot_storage_tier
    encrypt = true
  }
  network_interface {
    type              = "public"
    ip_address_family = "IPv4"
  }
  user_data = templatefile("${path.module}/cloud-init.yml.tftpl", {
    operator_key = jsonencode(var.ssh_public_key)
    deploy_key   = jsonencode(var.deploy_ssh_public_key)
    timezone     = var.server_timezone
    ssh_cidrs    = var.ssh_allowed_cidrs
    files        = { for target, source in local.deployment_files : target => filebase64("${path.module}/${source}") }
  })
  # Teardown requires a reviewed code change, fresh destroy plan and separate approval.
  lifecycle { prevent_destroy = true }
}

resource "upcloud_firewall_rules" "app" {
  server_id = upcloud_server.app.id
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
      comment                = "Approved operator or fixed-egress runner"
    }
  }
  dynamic "firewall_rule" {
    for_each = ["80", "443"]
    content {
      action                 = "accept"
      direction              = "in"
      family                 = "IPv4"
      protocol               = "tcp"
      destination_port_start = firewall_rule.value
      destination_port_end   = firewall_rule.value
      comment                = "Nginx ingress"
    }
  }
  firewall_rule {
    action    = "accept"
    direction = "in"
    family    = "IPv4"
    protocol  = "icmp"
    comment   = "Path MTU diagnostics"
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
