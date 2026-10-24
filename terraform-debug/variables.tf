variable "cloud_id" { type = string }
variable "folder_id" { type = string }
variable "network_id" {
  type        = string
  description = "Existing VPC, read-only reference. No existing network or subnet is modified."
}
variable "nat_gateway_id" {
  type        = string
  description = "Gateway already created by the full Terraform root."
}
variable "admin_cidr" {
  type = string
  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && endswith(var.admin_cidr, "/32")
    error_message = "Use one administrator IPv4 /32."
  }
}
variable "image_id" { type = string }
variable "ssh_public_key_path" { type = string }
variable "ssh_user" {
  type    = string
  default = "ubuntu"
}
