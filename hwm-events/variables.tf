variable "project_id" {
  description = "The Google Cloud Platform (GCP) project id"
  type        = string
}

variable "region" {
  description = "GCP region to deploy resources"
  type        = string
}

variable "scheduler_cron" {
  description = "Cron schedule for the Cloud Scheduler job"
  type        = string
  default     = "*/5 * * * *"
}

variable "hardware_management_api_endpoint_override" {
  description = "Google Distributed Hardware Management API. Leave empty to use default api endpoint."
  type        = string
  default     = ""
}

variable "monitored_project_ids" {
  description = "List of project IDs to monitor. If empty, defaults to the host project_id."
  type        = list(string)
  default     = []
}

variable "monitored_regions" {
  description = "List of regions to poll. If empty, defaults to [var.region]."
  type        = list(string)
  default     = []
}
