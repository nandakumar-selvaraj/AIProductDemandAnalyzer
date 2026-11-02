mock_provider "upcloud" {}

variables {
  server_plan           = "CATALOG-REVIEW-REQUIRED"
  ssh_public_key        = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixtureOperatorKey"
  deploy_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixtureDeploymentKey"
  ssh_allowed_cidrs     = ["203.0.113.10/32"]
}

run "single_server_defaults" {
  command = plan
  assert {
    condition     = upcloud_server.app.zone == "sg-sin1" && upcloud_server.app.timezone == "Etc/UTC"
    error_message = "Singapore preference and explicit UTC server time must be preserved."
  }
  assert {
    condition     = upcloud_server.app.firewall && upcloud_server.app.template[0].encrypt && upcloud_server.app.template[0].size == 30
    error_message = "Firewall and encrypted persistent boot storage required."
  }
  assert {
    condition     = length(upcloud_server.app.network_interface) == 1 && upcloud_server.app.network_interface[0].ip_address_family == "IPv4"
    error_message = "Exactly one public IPv4 interface required."
  }
  assert {
    condition = alltrue([
      for f in yamldecode(upcloud_server.app.user_data).write_files :
      f.permissions == "0644" if contains(["/opt/demand/init-db.sh", "/opt/demand/nginx.stage-a.conf", "/opt/demand/nginx.tls.conf"], f.path)
    ])
    error_message = "Non-root containers must be able to read their mounted configuration/initializer."
  }
  assert {
    condition = alltrue([
      for f in yamldecode(upcloud_server.app.user_data).write_files :
      strcontains(f.content, "PasswordAuthentication no") && strcontains(f.content, "AuthenticationMethods publickey") && strcontains(f.content, "ForceCommand sudo -n /usr/local/sbin/demand-release") && strcontains(f.content, "PermitTunnel no")
      if f.path == "/etc/ssh/sshd_config.d/00-demand-initial.conf"
    ])
    error_message = "SSH must be key-only and the deployer restricted to the release command."
  }
}

run "reject_world_open_ssh" {
  command = plan
  variables { ssh_allowed_cidrs = ["0.0.0.0/0"] }
  expect_failures = [var.ssh_allowed_cidrs]
}
