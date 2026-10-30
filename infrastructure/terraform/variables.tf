variable "zone" {
  type        = string
  description = "Operator-selected UpCloud zone; verify current availability before planning."
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z0-9]+$", var.zone))
    error_message = "Provide an explicit UpCloud zone."
  }
}
variable "plan" {
  type        = string
  description = "Operator-selected plan; start by checking available 2 vCPU / 4 GB offers."
  validation {
    condition     = length(var.plan) > 0 && !can(regex("[\\r\\n]", var.plan))
    error_message = "Provide an explicit plan from the current UpCloud catalog."
  }
}
variable "ssh_allowed_cidrs" {
  type = list(string)
  validation {
    condition = length(var.ssh_allowed_cidrs) > 0 && length(var.ssh_allowed_cidrs) <= 20 && alltrue([
      for cidr in var.ssh_allowed_cidrs : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) >= 8, false)
    ])
    error_message = "Supply 1–20 explicit IPv4 SSH CIDRs with prefix >= 8; never world-open SSH."
  }
}
variable "deploy_user" {
  type    = string
  default = "deployer"
  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{2,20}$", var.deploy_user)) && !contains(["root", "operator", "ubuntu"], var.deploy_user)
    error_message = "Use a dedicated non-root deployment username."
  }
}
variable "deploy_ssh_public_key" {
  type = string
  validation {
    condition     = can(regex("^ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\\r\\n]*)?$", var.deploy_ssh_public_key))
    error_message = "Provide an Ed25519 PUBLIC key, never a private key."
  }
}
variable "operator_ssh_public_key" {
  type = string
  validation {
    condition     = can(regex("^ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\\r\\n]*)?$", var.operator_ssh_public_key)) && try(split(" ", var.operator_ssh_public_key)[1] != split(" ", var.deploy_ssh_public_key)[1], false)
    error_message = "Provide a distinct operator Ed25519 public key."
  }
}
variable "data_size_gb" {
  type    = number
  default = 40
  validation {
    condition     = var.data_size_gb >= 40 && var.data_size_gb <= 500 && floor(var.data_size_gb) == var.data_size_gb
    error_message = "Data storage must be 40–500 whole GB; review incremental cost."
  }
}
