locals {
  machines = {
    # Backend names are logical labels; actual availability zones are e and d.
    web-a         = { zone = "e", public = false, memory = 2, disk = 10, type = "network-ssd", group = "web" }
    web-b         = { zone = "d", public = false, memory = 2, disk = 10, type = "network-ssd", group = "web" }
    elasticsearch = { zone = "d", public = false, memory = 4, disk = 20, type = "network-ssd", group = "elastic" }
    zabbix        = { zone = "d", public = true, memory = 4, disk = 20, type = "network-ssd", group = "ui" }
    kibana        = { zone = "e", public = true, memory = 4, disk = 10, type = "network-hdd", group = "ui" }
    bastion       = { zone = "e", public = true, memory = 2, disk = 10, type = "network-hdd", group = "bastion" }
  }
  service_groups = {
    web     = yandex_vpc_security_group.web.id
    elastic = yandex_vpc_security_group.elastic.id
    ui      = yandex_vpc_security_group.ui.id
    bastion = yandex_vpc_security_group.bastion.id
  }
}
resource "yandex_compute_instance" "vm" {
  for_each    = local.machines
  name        = "${var.prefix}-${each.key}"
  hostname    = "${var.prefix}-${each.key}"
  zone        = local.zones[each.value.zone].zone
  platform_id = "standard-v3"
  resources {
    cores         = 2
    core_fraction = 20
    memory        = each.value.memory
  }
  boot_disk {
    initialize_params {
      image_id = var.image_id
      type     = each.value.type
      size     = each.value.disk
    }
  }
  scheduling_policy { preemptible = var.preemptible }
  network_interface {
    subnet_id          = each.value.public ? yandex_vpc_subnet.public[each.value.zone].id : yandex_vpc_subnet.private[each.value.zone].id
    nat                = each.value.public
    security_group_ids = [local.service_groups[each.value.group]]
  }
  metadata = {
    ssh-keys  = "${var.ssh_user}:${trimspace(file(pathexpand(var.ssh_public_key_path)))}"
    user-data = <<-YAML
      #cloud-config
      runcmd:
        - [echo, IRINA_HOSTKEY_START]
        - [cat, /etc/ssh/ssh_host_ed25519_key.pub]
        - [echo, IRINA_HOSTKEY_END]
    YAML
  }
  allow_stopping_for_update = true
}
resource "yandex_compute_snapshot_schedule" "daily" {
  name             = "${var.prefix}-daily"
  retention_period = "168h0m0s"
  schedule_policy { expression = var.snapshot_cron }
  snapshot_spec { description = "Daily boot disk snapshot; crash-consistent" }
  disk_ids = [for vm in yandex_compute_instance.vm : vm.boot_disk[0].disk_id]
}
