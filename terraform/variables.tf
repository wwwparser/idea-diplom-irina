variable "cloud_id" { type = string }
variable "folder_id" { type = string }
variable "network_id" { type = string }
variable "snapshot_cron" {
  type        = string
  default     = "0 1 * * *"
  description = "Daily snapshot time in UTC; PostgreSQL dump runs at 00:30 UTC."
}
variable "prefix" {
  type    = string
  default = "irina"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,20}$", var.prefix))
    error_message = "Use a short lowercase DNS label."
  }
}
variable "admin_cidr" {
  type        = string
  description = "Administrator/reviewer public IPv4 /32; never 0.0.0.0/0."
  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && endswith(var.admin_cidr, "/32")
    error_message = "Provide your public IPv4 address with /32."
  }
}
variable "ssh_public_key_path" { type = string }
variable "ssh_user" {
  type    = string
  default = "ubuntu"
}
variable "image_id" {
  type        = string
  description = "Pinned Ubuntu 22.04 LTS image ID, identical on all VMs."
}
variable "preemptible" {
  type    = bool
  default = false
}
