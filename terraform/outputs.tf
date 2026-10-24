output "machines" {
  value = { for key, vm in yandex_compute_instance.vm : key => {
    id         = vm.id
    fqdn       = "${vm.hostname}.ru-central1.internal"
    public_ip  = vm.network_interface[0].nat_ip_address
    private_ip = vm.network_interface[0].ip_address
    disk_id    = vm.boot_disk[0].disk_id
  } }
}
output "ssh_user" { value = var.ssh_user }
output "admin_cidr" { value = var.admin_cidr }
output "site_url" {
  value = "http://${yandex_alb_load_balancer.web.listener[0].endpoint[0].address[0].external_ipv4_address[0].address}"
}
