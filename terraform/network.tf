locals {
  zones = {
    e = { zone = "ru-central1-e", public = "10.20.1.0/24", private = "10.20.11.0/24" }
    d = { zone = "ru-central1-d", public = "10.20.2.0/24", private = "10.20.12.0/24" }
  }
}
data "yandex_vpc_network" "existing" { network_id = var.network_id }
resource "yandex_vpc_gateway" "nat" {
  name = "${var.prefix}-nat"
  shared_egress_gateway {}
}
resource "yandex_vpc_route_table" "private" {
  network_id = data.yandex_vpc_network.existing.id
  static_route {
    destination_prefix = "0.0.0.0/0"
    gateway_id         = yandex_vpc_gateway.nat.id
  }
}
resource "yandex_vpc_subnet" "public" {
  for_each       = local.zones
  name           = "${var.prefix}-public-${each.key}"
  zone           = each.value.zone
  network_id     = data.yandex_vpc_network.existing.id
  v4_cidr_blocks = [each.value.public]
}
resource "yandex_vpc_subnet" "private" {
  for_each       = local.zones
  name           = "${var.prefix}-private-${each.key}"
  zone           = each.value.zone
  network_id     = data.yandex_vpc_network.existing.id
  v4_cidr_blocks = [each.value.private]
  route_table_id = yandex_vpc_route_table.private.id
}
resource "yandex_vpc_security_group" "bastion" {
  name       = "${var.prefix}-bastion"
  network_id = data.yandex_vpc_network.existing.id
  ingress {
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = [var.admin_cidr]
  }
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}
# Shared cloud UI group; a per-role host firewall narrows the allowed ports.
resource "yandex_vpc_security_group" "ui" {
  name       = "${var.prefix}-ui"
  network_id = data.yandex_vpc_network.existing.id
  ingress {
    protocol       = "TCP"
    port           = 443
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
  dynamic "ingress" {
    for_each = toset([8080, 5601])
    content {
      protocol       = "TCP"
      port           = ingress.value
      v4_cidr_blocks = [var.admin_cidr]
    }
  }
  ingress {
    protocol          = "TCP"
    port              = 22
    security_group_id = yandex_vpc_security_group.bastion.id
  }
  ingress {
    protocol       = "TCP"
    port           = 10051
    v4_cidr_blocks = concat([for z in local.zones : z.public], [for z in local.zones : z.private])
  }
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "yandex_vpc_security_group" "alb" {
  name       = "${var.prefix}-alb"
  network_id = data.yandex_vpc_network.existing.id
  ingress {
    protocol       = "TCP"
    port           = 80
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    protocol          = "TCP"
    port              = 30080
    predefined_target = "loadbalancer_healthchecks"
  }
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "yandex_vpc_security_group" "web" {
  name       = "${var.prefix}-web"
  network_id = data.yandex_vpc_network.existing.id
  ingress {
    protocol          = "TCP"
    port              = 22
    security_group_id = yandex_vpc_security_group.bastion.id
  }
  dynamic "ingress" {
    for_each = [yandex_vpc_security_group.alb.id, yandex_vpc_security_group.ui.id]
    content {
      protocol          = "TCP"
      port              = 80
      security_group_id = ingress.value
    }
  }
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "yandex_vpc_security_group" "elastic" {
  name       = "${var.prefix}-elastic"
  network_id = data.yandex_vpc_network.existing.id
  ingress {
    protocol          = "TCP"
    port              = 22
    security_group_id = yandex_vpc_security_group.bastion.id
  }
  dynamic "ingress" {
    for_each = [yandex_vpc_security_group.web.id, yandex_vpc_security_group.ui.id]
    content {
      protocol          = "TCP"
      port              = 9200
      security_group_id = ingress.value
    }
  }
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}
