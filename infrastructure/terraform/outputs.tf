output "public_ipv4" {
  value       = upcloud_server.portfolio.network_interface[0].ip_address
  description = "Stop here after provisioning: send this IPv4 to the subdomain owner."
}
output "operator_ssh" {
  value = "ssh operator@${upcloud_server.portfolio.network_interface[0].ip_address}"
}
output "deploy_ssh" {
  value = "ssh ${var.deploy_user}@${upcloud_server.portfolio.network_interface[0].ip_address}"
}
output "persistent_storage_id" { value = upcloud_storage.data.id }
