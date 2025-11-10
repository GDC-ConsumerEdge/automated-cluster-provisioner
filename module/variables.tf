# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "project_id" {
  description = "The Google Cloud Platform (GCP) project id in which the solution resources will be provisioned"
  type        = string
}

variable "project_id_fleet" {
  description = "Optional id of GCP project hosting the Google Kubernetes Engine (GKE) fleet or Google Distributed Compute Engine (GDCE) machines. Defaults to the value of 'project_id'."
  default     = null
  type        = string
}

variable "project_id_secrets" {
  description = "Optional id of GCP project containing the Secret Manager entry storing Git repository credentials. Defaults to the value of 'project_id'."
  default     = null
  type        = string
}

variable "region" {
  description = "GCP region to deploy resources"
  type        = string
}

variable "project_services" {
  type        = list(string)
  description = "GCP Service APIs (<api>.googleapis.com) to enable for this project"
  default = [
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudscheduler.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
  ]
}

# prune list of required services later
variable "project_services_fleet" {
  type        = list(string)
  description = "GCP Service APIs (<api>.googleapis.com) to enable for this project"
  default = [
    "anthos.googleapis.com",
    "anthosaudit.googleapis.com",
    "anthosconfigmanagement.googleapis.com",
    "anthosgke.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "connectgateway.googleapis.com",
    "container.googleapis.com",
    "edgecontainer.googleapis.com",
    "gkeconnect.googleapis.com",
    "gkehub.googleapis.com",
    "gkeonprem.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "kubernetesmetadata.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "opsconfigmonitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "stackdriver.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
  ]
}

variable "project_services_secrets" {
  type        = list(string)
  description = "GCP Service APIs (<api>.googleapis.com) to enable for this project"
  default = [
    "secretmanager.googleapis.com",
  ]
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "skip_identity_service" {
  description = "Skip the configuring Anthos identity service during cluster provisioning. This is used for group based RBAC in the cluster."
  type        = bool
  default     = false
}

variable "source_of_truth_repo" {
  description = "Source of truth repository"
  default     = "gitlab.com/gcp-solutions-public/retail-edge/gdce-shyguy-internal/cluster-intent-registry"
}

variable "source_of_truth_branch" {
  description = "Source of truth branch"
  default     = "main"
}

variable "source_of_truth_path" {
  description = "Path to cluster intent registry file"
  default     = "source_of_truth.csv"
}

variable "git_secret_id" {
  description = "Secrets manager secret holding git token to pull source of truth"
  default     = "shyguy-internal-pat"
}

variable "deploy_zone_active_monitor" {
  type        = bool
  description = "Whether to deploy Zone Active Monitor cloud function"
  default     = false
}

variable "edge_container_api_endpoint_override" {
  description = "Google Distributed Cloud Edge API. Leave empty to use default api endpoint."
  default     = ""
}

variable "edge_network_api_endpoint_override" {
  description = "Google Distributed Cloud Edge Network API. Leave empty to use default api endpoint."
  default     = ""
}

variable "gke_hub_api_endpoint_override" {
  description = "Google Distributed Cloud Edge API. Leave empty to use default api endpoint."
  default     = ""
}

variable "hardware_management_api_endpoint_override" {
  description = "Google Distributed Hardware Management API. Leave empty to use default api endpoint."
  default     = ""
}

variable "cluster_creation_timeout" {
  description = "Cloud Build timeout in seconds for cluster creation. This should account for time to create the cluster, configure core services (ConfigSync, Robin, VMRuntime, etc..), and time for any workload configuration needed before the healthchecks pass."
  default     = "28800"
  type        = number
}

variable "cluster_creation_max_retries" {
  description = "The maximum number of retries upon cluster creation failure before marking the zone state as CUSTOMER_FACTORY_TURNUP_CHECKS_FAILED"
  default     = "0"
  type        = number
}

# https://cloud.google.com/kubernetes-engine/enterprise/config-sync/docs/release-notes
variable "default_config_sync_version" {
  description = "Sets a default ConfigSync version to use for provisioned clusters. If left empty, it will not specify a version at the cluster level. If empty, this will either install the fleet configured version or the latest version of ConfigSync."
  default     = ""
  type        = string
}

variable "bart_create_bucket" {
  description = "Create a GCS bucket for cluster backup and recovery."
  type        = bool
  default     = false
}

variable "opt_in_build_messages" {
  description = "Opt in to sending build steps and failure messages to Google. These messages help Google provide support on issues during the provisioning process."
  type        = bool
  default     = false
}

variable "notification_channel_email" {
  description = "Notification Channel for Cluster Provisioner Alerts."
  default     = ""
  type        = string
}

variable "vpc_connector" {
  description = "VPC connector for the cloud functions"
  type        = string
  default     = null
}

variable "vpc_connector_egress_settings" {
  description = "VPC connector egress settings for the cloud functions"
  type        = string
  default     = null
}