variable "project_name" {
  type    = string
  default = "aiproductdemand"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project_name))
    error_message = "Use a short lowercase project identifier."
  }
}
variable "environment" {
  type    = string
  default = "production"
  validation {
    condition     = var.environment == "production"
    error_message = "This root is dedicated to the single production demo."
  }
}
variable "upcloud_zone" {
  type    = string
  default = "sg-sin1"
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z0-9]+$", var.upcloud_zone))
    error_message = "Use a catalog zone identifier."
  }
}
variable "server_plan" {
  type        = string
  description = "Required: approve a current Singapore 2 vCPU / 4 GB plan and its storage tier/price. No assumed plan default."
  validation {
    condition     = can(regex("^[A-Za-z0-9-]+$", var.server_plan))
    error_message = "Select a current plan identifier."
  }
}
variable "server_hostname" {
  type    = string
  default = "aiproductdemand-prod"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,62}$", var.server_hostname))
    error_message = "Use a valid lowercase hostname."
  }
}
variable "ssh_public_key" {
  type = string
  validation {
    condition     = can(regex("^ssh-ed25519 [A-Za-z0-9+/=]+( [^\r\n]*)?$", var.ssh_public_key))
    error_message = "Supply only an Ed25519 operator PUBLIC key."
  }
}
variable "deploy_ssh_public_key" {
  type = string
  validation {
    condition     = can(regex("^ssh-ed25519 [A-Za-z0-9+/=]+( [^\r\n]*)?$", var.deploy_ssh_public_key)) && try(split(" ", var.deploy_ssh_public_key)[1] != split(" ", var.ssh_public_key)[1], false)
    error_message = "Supply a distinct Ed25519 PUBLIC key for restricted CI deployments."
  }
}
variable "ssh_allowed_cidrs" {
  type = list(string)
  validation {
    condition = length(var.ssh_allowed_cidrs) > 0 && length(var.ssh_allowed_cidrs) <= 20 && alltrue([
      for cidr in var.ssh_allowed_cidrs : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) >= 24, false)
    ])
    error_message = "Approve explicit IPv4 administrative/runner CIDRs, /24 or narrower."
  }
}
variable "server_timezone" {
  type    = string
  default = "Etc/UTC"
  validation {
    condition     = contains(["Etc/UTC", "Asia/Singapore"], var.server_timezone)
    error_message = "Choose explicitly supported UTC or Singapore server time."
  }
}
variable "boot_storage_tier" {
  type        = string
  default     = "standard"
  description = "Standard for Starter; confirm compatibility for the selected plan."
  validation {
    condition     = contains(["standard", "maxiops"], var.boot_storage_tier)
    error_message = "Choose a documented storage tier."
  }
}
