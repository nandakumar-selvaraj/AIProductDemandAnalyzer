terraform {
  required_version = ">= 1.17.1, < 1.18.0"
  required_providers {
    upcloud = {
      source  = "UpCloudLtd/upcloud"
      version = "= 5.48.0"
    }
  }
  # An approved existing AWS S3 bucket is mandatory; there is no local fallback.
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}

provider "upcloud" {}
