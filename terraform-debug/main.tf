locals {
  machines = {
    control = { zone = "ru-central1-d", cidr = "10.60.1.0/24", memory = 8, disk = 40, public = true }
    web     = { zone = "ru-central1-e", cidr = "10.60.2.0/24", memory = 2, disk = 10, public = false }
  }
}
data "yandex_vpc_network" "existing" { network_id = var.network_id }

resource "yandex_vpc_route_table" "private" {
  name       = "irina-debug-private"
  network_id = data.yandex_vpc_network.existing.id
  static_route {
    destination_prefix = "0.0.0.0/0"
    gateway_id         = var.nat_gateway_id
  }
}
resource "yandex_vpc_subnet" "debug" {
  for_each       = local.machines
  name           = "irina-debug-${each.key}"
  zone           = each.value.zone
  network_id     = data.yandex_vpc_network.existing.id
  v4_cidr_blocks = [each.value.cidr]
  route_table_id = each.value.public ? null : yandex_vpc_route_table.private.id
}
resource "yandex_vpc_security_group" "control" {
  name       = "irina-debug-control"
  network_id = data.yandex_vpc_network.existing.id
  dynamic "ingress" {
    for_each = toset([22, 80, 8080, 5601])
    content {
      protocol       = "TCP"
      port           = ingress.value
      v4_cidr_blocks = [var.admin_cidr]
    }
  }
  ingress {
    protocol       = "TCP"
    port           = 10051
    v4_cidr_blocks = [local.machines.control.cidr, local.machines.web.cidr]
  }
  ingress {
    protocol       = "TCP"
    port           = 9200
    v4_cidr_blocks = [local.machines.web.cidr]
  }
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "yandex_vpc_security_group" "web" {
  name       = "irina-debug-web"
  network_id = data.yandex_vpc_network.existing.id
  dynamic "ingress" {
    for_each = toset([22, 80])
    content {
      protocol          = "TCP"
      port              = ingress.value
      security_group_id = yandex_vpc_security_group.control.id
    }
  }
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "yandex_compute_instance" "debug" {
  for_each    = local.machines
  name        = "irina-debug-${each.key}"
  hostname    = "irina-debug-${each.key}"
  zone        = each.value.zone
  platform_id = "standard-v3"
  resources {
    cores         = 2
    core_fraction = 20
    memory        = each.value.memory
  }
  boot_disk {
    initialize_params {
      image_id = var.image_id
      type     = "network-ssd"
      size     = each.value.disk
    }
  }
  scheduling_policy { preemptible = true }
  network_interface {
    subnet_id          = yandex_vpc_subnet.debug[each.key].id
    nat                = each.value.public
    security_group_ids = [each.key == "control" ? yandex_vpc_security_group.control.id : yandex_vpc_security_group.web.id]
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
