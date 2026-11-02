output "public_ipv4" { value = upcloud_server.app.network_interface[0].ip_address }
output "server_hostname" { value = upcloud_server.app.hostname }
output "server_id" { value = upcloud_server.app.id }
output "ssh_connection" { value = "ssh -i ~/.ssh/aiproductdemand_upcloud operator@${upcloud_server.app.network_interface[0].ip_address}" }
