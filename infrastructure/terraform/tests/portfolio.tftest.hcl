mock_provider "upcloud" {}

variables {
  zone                    = "fi-hel1"
  plan                    = "2xCPU-4GB"
  ssh_allowed_cidrs       = ["203.0.113.10/32"]
  deploy_ssh_public_key   = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA deploy-test"
  operator_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB operator-test"
}

run "domain_free_server" {
  command = plan
  assert {
    condition     = upcloud_server.portfolio.firewall && upcloud_server.portfolio.plan == "2xCPU-4GB"
    error_message = "Server firewall and configurable sizing are required."
  }
  assert {
    condition     = upcloud_storage.data.encrypt && upcloud_storage.data.size == 40
    error_message = "Persistent data storage must be encrypted."
  }
  assert {
    condition     = upcloud_server.portfolio.login[0].create_password == false
    error_message = "SSH password creation must be disabled."
  }
  assert {
    condition     = !strcontains(upcloud_server.portfolio.user_data, "JWT_SIGNING_SECRET=")
    error_message = "Application secrets must never enter cloud-init/state."
  }
  assert {
    condition     = yamldecode(upcloud_server.portfolio.user_data).ssh_pwauth == false && yamldecode(upcloud_server.portfolio.user_data).disable_root
    error_message = "Rendered cloud-init must disable password and root SSH login."
  }
  assert {
    condition     = one([for entry in yamldecode(upcloud_server.portfolio.user_data).write_files : entry.permissions if entry.path == "/usr/local/lib/portfolio/init-db.sh"]) == "0644"
    error_message = "The unprivileged PostgreSQL entrypoint must be able to read the public initialization script."
  }
}

run "reject_open_ssh" {
  command = plan
  variables { ssh_allowed_cidrs = ["0.0.0.0/0"] }
  expect_failures = [var.ssh_allowed_cidrs]
}

run "reject_root_deployer" {
  command = plan
  variables { deploy_user = "root" }
  expect_failures = [var.deploy_user]
}
