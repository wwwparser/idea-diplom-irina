output "machines" {
  value = { for key, vm in yandex_compute_instance.debug : key => {
    id         = vm.id
    fqdn       = "${vm.hostname}.ru-central1.internal"
    public_ip  = vm.network_interface[0].nat_ip_address
    private_ip = vm.network_interface[0].ip_address
    disk_id    = vm.boot_disk[0].disk_id
  } }
}
output "ssh_user" { value = var.ssh_user }
output "inventory_groups" {
  value = {
    web           = ["control", "web"]
    monitoring    = ["control"]
    elasticsearch = ["control"]
    kibana        = ["control"]
    bastion       = ["control"]
  }
}
