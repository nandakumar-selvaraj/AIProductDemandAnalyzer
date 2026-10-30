terraform {
  required_version = ">= 1.17.1, < 1.18.0"
  required_providers {
    upcloud = {
      source  = "UpCloudLtd/upcloud"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}

# UPCLOUD_TOKEN is supplied only through the process environment.
provider "upcloud" {}
