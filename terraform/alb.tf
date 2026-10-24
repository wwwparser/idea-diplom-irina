resource "yandex_alb_target_group" "web" {
  name = "${var.prefix}-web"
  dynamic "target" {
    for_each = toset(["web-a", "web-b"])
    content {
      subnet_id  = yandex_compute_instance.vm[target.value].network_interface[0].subnet_id
      ip_address = yandex_compute_instance.vm[target.value].network_interface[0].ip_address
    }
  }
}
resource "yandex_alb_backend_group" "web" {
  name = "${var.prefix}-web"
  http_backend {
    name             = "nginx"
    weight           = 1
    port             = 80
    target_group_ids = [yandex_alb_target_group.web.id]
    healthcheck {
      timeout  = "1s"
      interval = "5s"
      http_healthcheck { path = "/" }
    }
  }
}
resource "yandex_alb_http_router" "web" { name = "${var.prefix}-router" }
resource "yandex_alb_virtual_host" "web" {
  name           = "${var.prefix}-host"
  http_router_id = yandex_alb_http_router.web.id
  route {
    name = "all"
    http_route {
      http_match {
        path { prefix = "/" }
      }
      http_route_action { backend_group_id = yandex_alb_backend_group.web.id }
    }
  }
}
resource "yandex_alb_load_balancer" "web" {
  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }
  name               = "${var.prefix}-alb"
  network_id         = data.yandex_vpc_network.existing.id
  security_group_ids = [yandex_vpc_security_group.alb.id]
  allocation_policy {
    dynamic "location" {
      for_each = local.zones
      content {
        zone_id   = location.value.zone
        subnet_id = yandex_vpc_subnet.public[location.key].id
      }
    }
  }
  listener {
    name = "http"
    endpoint {
      address {
        external_ipv4_address {}
      }
      ports = [80]
    }
    http {
      handler { http_router_id = yandex_alb_http_router.web.id }
    }
  }
}
