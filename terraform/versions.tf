terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "= 0.233.0"
    }
  }
}

provider "yandex" {
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
}
