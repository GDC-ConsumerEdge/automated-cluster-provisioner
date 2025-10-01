variable "platform_group_role_pairs" {
  type = list(object({
    member     = string
    project_id = string
    roles      = list(string)
    type       = string
  }))
}

variable "workflows_group_role_pairs" {
  type = list(object({
    member     = string
    project_id = string
    roles      = list(string)
    type       = string
  }))
}

variable "fleet_project" {
  type    = string
  default = ""
}