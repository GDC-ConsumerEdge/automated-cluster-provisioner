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

locals {
  cloud_build_inline_create_cluster = yamldecode(file("${path.module}/create-cluster.yaml"))
  cloud_build_inline_modify_cluster = yamldecode(file("${path.module}/modify-cluster.yaml"))
  cloud_build_substitions = merge(
    { _CLUSTER_INTENT_BUCKET = google_storage_bucket.gdce-cluster-provisioner-bucket.name },
    var.edge_container_api_endpoint_override != "" ? { _EDGE_CONTAINER_API_ENDPOINT_OVERRIDE = var.edge_container_api_endpoint_override } : {},
    var.edge_network_api_endpoint_override != "" ? { _EDGE_NETWORK_API_ENDPOINT_OVERRIDE = var.edge_network_api_endpoint_override } : {},
    var.gke_hub_api_endpoint_override != "" ? { _GKEHUB_API_ENDPOINT_OVERRIDE = var.gke_hub_api_endpoint_override } : {},
    var.hardware_management_api_endpoint_override != "" ? { _HARDWARE_MANAGEMENT_API_ENDPOINT_OVERRIDE = var.hardware_management_api_endpoint_override } : {},
    { _SOURCE_OF_TRUTH_REPO = var.source_of_truth_repo },
    { _SOURCE_OF_TRUTH_BRANCH = var.source_of_truth_branch },
    { _SOURCE_OF_TRUTH_PATH = var.source_of_truth_path },
    { _GIT_SECRET_ID = var.git_secret_id },
    { _GIT_SECRETS_PROJECT_ID = local.project_id_secrets },
    { _TIMEOUT_IN_SECONDS = var.cluster-creation-timeout },
    { _CS_VERSION = var.default-config-sync-version },
    { _MAX_RETRIES = var.cluster-creation-max-retries },
    var.skip_identity_service == true ? { _SKIP_IDENTITY_SERVICE = "TRUE" } : {_SKIP_IDENTITY_SERVICE = "FALSE"},
    var.bart_create_bucket == true ? { _BART_CREATE_BUCKET = "TRUE" } : { _BART_CREATE_BUCKET = "FALSE" },
  )
  project_id_fleet   = coalesce(var.project_id_fleet, var.project_id)
  project_id_secrets = coalesce(var.project_id_secrets, var.project_id)
}

resource "random_id" "main" {
  byte_length = 8
}

resource "google_project_service" "project" {
  for_each = toset(var.project_services)
  service  = each.value

  disable_on_destroy = false
}

resource "google_project_service" "project_fleet" {
  for_each = toset(var.project_services_fleet)
  project  = local.project_id_fleet
  service  = each.value

  disable_on_destroy = false
}

resource "google_project_service" "project_secrets" {
  for_each = toset(var.project_services_secrets)
  project  = local.project_id_secrets
  service  = each.value

  disable_on_destroy = false
}

resource "google_storage_bucket" "gdce-cluster-provisioner-bucket" {
  name          = "gdce-cluster-provisioner-bucket-${var.environment}-${random_id.main.hex}"
  location      = "US"
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "apply-spec" {
  name         = "apply-spec.yaml.template"
  source       = "${path.module}/apply-spec.yaml.template"
  content_type = "text/plain"
  bucket       = google_storage_bucket.gdce-cluster-provisioner-bucket.id
}

resource "google_storage_bucket_object" "auth-config" {
  name         = "auth-config.yaml"
  source       = "${path.module}/auth-config.yaml"
  content_type = "text/plain"
  bucket       = google_storage_bucket.gdce-cluster-provisioner-bucket.id
}

resource "google_cloudbuild_trigger" "create-cluster" {
  location        = var.region
  name            = "gdce-cluster-provisioner-trigger-${var.environment}"
  service_account = "projects/${var.project_id}/serviceAccounts/${google_service_account.gdce-provisioning-agent.email}"
  substitutions   = local.cloud_build_substitions

  build {
    substitutions = local.cloud_build_substitions
    timeout       = "${var.cluster-creation-timeout}s"
    tags = try(local.cloud_build_inline_create_cluster["tags"], [])

    options {
      logging = try(local.cloud_build_inline_create_cluster["options"]["logging"], null)
    }

    dynamic "step" {
      for_each = try(local.cloud_build_inline_create_cluster["steps"], [])
      content {
        env    = try(step.value.env, [])
        id     = try(step.value.id, null)
        name   = try(step.value.name, null)
        script = try(step.value.script, null)
      }
    }
  }

  # workaround to create manual trigger: https://github.com/hashicorp/terraform-provider-google/issues/16295
  webhook_config {
    secret = ""
  }
  lifecycle {
    ignore_changes = [webhook_config]
  }
}

resource "google_cloudbuild_trigger" "modify-cluster" {
  location        = var.region
  name            = "gdce-cluster-reconciler-trigger-${var.environment}"
  service_account = "projects/${var.project_id}/serviceAccounts/${google_service_account.gdce-provisioning-agent.email}"
  substitutions   = local.cloud_build_substitions

  build {
    substitutions = local.cloud_build_substitions
    timeout       = try(local.cloud_build_inline_modify_cluster["timeout"], "600s")
    tags          = try(local.cloud_build_inline_modify_cluster["tags"], [])

    options {
      logging = try(local.cloud_build_inline_modify_cluster["options"]["logging"], null)
    }

    dynamic "step" {
      for_each = try(local.cloud_build_inline_modify_cluster["steps"], [])
      content {
        env    = try(step.value.env, [])
        id     = try(step.value.id, null)
        name   = try(step.value.name, null)
        script = try(step.value.script, null)
      }
    }
  }

  # workaround to create manual trigger: https://github.com/hashicorp/terraform-provider-google/issues/16295
  webhook_config {
    secret = ""
  }
  lifecycle {
    ignore_changes = [webhook_config]
  }
}

resource "google_service_account" "gdce-provisioning-agent" {
  account_id = "gdce-prov-agent-${var.environment}"
}

resource "google_project_iam_member" "gdce-provisioning-agent-edge-admin" {
  project = local.project_id_fleet
  role    = "roles/edgecontainer.admin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-edgenetwork-admin" {
  project = local.project_id_fleet
  role    = "roles/edgenetwork.admin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-storage-admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-log-writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-build-viewer" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.viewer"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-secret-accessor" {
  project = local.project_id_secrets
  role    = "roles/secretmanager.secretAccessor"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-hub-admin" {
  project = local.project_id_fleet
  role    = "roles/gkehub.admin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-hub-gateway" {
  project = local.project_id_fleet
  role    = "roles/gkehub.gatewayAdmin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-hardware-management-admin" {
  project = local.project_id_fleet
  role    = "roles/gdchardwaremanagement.admin"
  member  = google_service_account.gdce-provisioning-agent.member
}

// Generating a random_uuid based on the md5s of all files in the watchers directory.
// This avoids situations in temporary workspaces where the file may not be available
//   on subsequent `tf plan/apply` or carried over from the plan to the apply. 
resource "random_uuid" "watcher-src-uuid" {
  keepers = {
    for file in fileset("../watchers/src", "**/*") :
    file => filemd5("../watchers/src/${file}")
  }
}

data "archive_file" "watcher-src" {
  type        = "zip"
  output_path = "/tmp/watcher_src-${resource.random_uuid.watcher-src-uuid.result}.zip"
  source_dir  = "../watchers/src/"
}

resource "google_storage_bucket_object" "watcher-src" {
  name   = "watcher_src.zip"
  bucket = google_storage_bucket.gdce-cluster-provisioner-bucket.name
  source = data.archive_file.watcher-src.output_path # Add path to the zipped function source code
}

resource "google_service_account" "zone-watcher-agent" {
  account_id   = "zone-watcher-agent-${var.environment}"
  display_name = "Zone Watcher Service Account"
}

resource "google_project_iam_member" "zone-watcher-agent-storage-admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_project_iam_member" "zone-watcher-agent-cloud-build-editor" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_project_iam_member" "zone-watcher-agent-fleet-viewer" {
  project = var.project_id
  role    = "roles/gkehub.viewer"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_service_account_iam_member" "gdce-provisioning-agent-token-user" {
  service_account_id = google_service_account.gdce-provisioning-agent.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.zone-watcher-agent.email}"
}

resource "google_service_account_iam_member" "gdce-provisioning-agent-impersonate-sa" {
  role               = "roles/iam.serviceAccountTokenCreator"
  service_account_id = google_service_account.gdce-provisioning-agent.name
  member             = "serviceAccount:${google_service_account.zone-watcher-agent.email}"
}

resource "google_project_iam_member" "zone-watcher-agent-secret-accessor" {
  project = local.project_id_secrets
  role    = "roles/secretmanager.secretAccessor"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_project_iam_member" "zone-watcher-agent-edge-viewer" {
  project = local.project_id_fleet
  role    = "roles/edgecontainer.viewer"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_project_iam_member" "zone-watcher-agent-hardware-management-reader" {
  project = local.project_id_fleet
  role    = "roles/gdchardwaremanagement.reader"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_service_account" "zone-watcher-builder" {
  account_id   = "zone-watcher-builder-${var.environment}"
  display_name = "Zone Watcher Builder Service Account"
}

resource "google_project_iam_member" "zone-watcher-builder-object-viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = google_service_account.zone-watcher-builder.member
}

resource "google_project_iam_member" "zone-watcher-builder-log-writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = google_service_account.zone-watcher-builder.member
}

resource "google_project_iam_member" "zone-watcher-builder-registry-writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = google_service_account.zone-watcher-builder.member
}

# Image pulling from artifact registry

resource "google_service_account" "image-puller-agent" {
  account_id = "image-puller-${var.environment}"
}

resource "google_project_iam_member" "image-puller-agent-artifactregistry-reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = google_service_account.image-puller-agent.member
}

# zone-watcher cloud function
resource "google_cloudfunctions2_function" "zone-watcher" {
  name        = "zone-watcher-${var.environment}"
  location    = var.region
  description = "zone watcher function"

  build_config {
    runtime     = "python312"
    entry_point = "zone_watcher"
    environment_variables = {
      "SOURCE_SHA" = data.archive_file.watcher-src.output_sha # https://github.com/hashicorp/terraform-provider-google/issues/1938
    }
    service_account = google_service_account.zone-watcher-builder.id
    source {
      storage_source {
        bucket = google_storage_bucket.gdce-cluster-provisioner-bucket.name
        object = google_storage_bucket_object.watcher-src.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "512M"
    timeout_seconds    = 60
    environment_variables = {
      GOOGLE_CLOUD_PROJECT                     = var.project_id,
      CB_TRIGGER_NAME                          = "gdce-cluster-provisioner-trigger-${var.environment}"
      REGION                                   = var.region
      EDGE_CONTAINER_API_ENDPOINT_OVERRIDE     = var.edge_container_api_endpoint_override
      HARDWARE_MANAGMENT_API_ENDPOINT_OVERRIDE = var.hardware_management_api_endpoint_override
      SOURCE_OF_TRUTH_REPO                     = var.source_of_truth_repo
      SOURCE_OF_TRUTH_BRANCH                   = var.source_of_truth_branch
      SOURCE_OF_TRUTH_PATH                     = var.source_of_truth_path
      PROJECT_ID_SECRETS                       = var.project_id_secrets
      GIT_SECRET_ID                            = var.git_secret_id
      MAX_RETRIES                              = var.cluster-creation-max-retries
    }
    service_account_email = google_service_account.zone-watcher-agent.email
  }
}

resource "google_cloud_run_service_iam_member" "member" {
  location = google_cloudfunctions2_function.zone-watcher.location
  service  = google_cloudfunctions2_function.zone-watcher.name
  role     = "roles/run.invoker"
  member   = google_service_account.gdce-provisioning-agent.member
}

resource "google_cloud_scheduler_job" "job" {
  name             = "zone-watcher-scheduler-${var.environment}"
  description      = "Trigger the ${google_cloudfunctions2_function.zone-watcher.name}"
  schedule         = "*/10 * * * *" # Run every 10 minutes
  time_zone        = "Europe/Dublin"
  attempt_deadline = "320s"
  region           = var.region

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.zone-watcher.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.gdce-provisioning-agent.email
    }
  }
}

# Cluster Watcher cloud function
resource "google_cloudfunctions2_function" "cluster-watcher" {
  name        = "cluster-watcher-${var.environment}"
  location    = var.region
  description = "cluster watcher function"

  build_config {
    runtime     = "python312"
    entry_point = "cluster_watcher"
    environment_variables = {
      "SOURCE_SHA" = data.archive_file.watcher-src.output_sha # https://github.com/hashicorp/terraform-provider-google/issues/1938
    }
    service_account = google_service_account.zone-watcher-builder.id
    source {
      storage_source {
        bucket = google_storage_bucket.gdce-cluster-provisioner-bucket.name
        object = google_storage_bucket_object.watcher-src.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 60
    environment_variables = {
      GOOGLE_CLOUD_PROJECT                     = var.project_id,
      CB_TRIGGER_NAME                          = "gdce-cluster-reconciler-trigger-${var.environment}"
      REGION                                   = var.region
      EDGE_CONTAINER_API_ENDPOINT_OVERRIDE     = var.edge_container_api_endpoint_override
      EDGE_NETWORK_API_ENDPOINT_OVERRIDE       = var.edge_network_api_endpoint_override
      HARDWARE_MANAGMENT_API_ENDPOINT_OVERRIDE = var.hardware_management_api_endpoint_override
      GKEHUB_API_ENDPOINT_OVERRIDE             = var.gke_hub_api_endpoint_override
      SOURCE_OF_TRUTH_REPO                     = var.source_of_truth_repo
      SOURCE_OF_TRUTH_BRANCH                   = var.source_of_truth_branch
      SOURCE_OF_TRUTH_PATH                     = var.source_of_truth_path
      PROJECT_ID_SECRETS                       = var.project_id_secrets
      GIT_SECRET_ID                            = var.git_secret_id
    }
    service_account_email = google_service_account.zone-watcher-agent.email
  }
}

resource "google_cloud_run_service_iam_member" "cluster-watcher-member" {
  location = google_cloudfunctions2_function.cluster-watcher.location
  service  = google_cloudfunctions2_function.cluster-watcher.name
  role     = "roles/run.invoker"
  member   = google_service_account.gdce-provisioning-agent.member
}

resource "google_cloud_scheduler_job" "cluster-watcher-job" {
  name             = "cluster-watcher-scheduler-${var.environment}"
  description      = "Trigger the ${google_cloudfunctions2_function.cluster-watcher.name}"
  schedule         = "*/10 * * * *" # Run every 10 minutes
  time_zone        = "Europe/Dublin"
  attempt_deadline = "320s"
  region           = var.region

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.cluster-watcher.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.gdce-provisioning-agent.email
    }
  }
}

# Zone Active Metric Ingestion cloud function
resource "google_cloudfunctions2_function" "zone-active-metric" {
  count       = var.deploy-zone-active-monitor ? 1 : 0
  name        = "zone-active-metric-${var.environment}"
  location    = var.region
  description = "zone active metric generator"

  build_config {
    runtime     = "python312"
    entry_point = "zone_active_metric"
    environment_variables = {
      "SOURCE_SHA" = data.archive_file.watcher-src.output_sha # https://github.com/hashicorp/terraform-provider-google/issues/1938
    }
    service_account = google_service_account.zone-watcher-builder.id
    source {
      storage_source {
        bucket = google_storage_bucket.gdce-cluster-provisioner-bucket.name
        object = google_storage_bucket_object.watcher-src.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 60
    environment_variables = {
      GOOGLE_CLOUD_PROJECT                     = var.project_id,
      CB_TRIGGER_NAME                          = "gdce-cluster-reconciler-trigger-${var.environment}"
      REGION                                   = var.region
      EDGE_CONTAINER_API_ENDPOINT_OVERRIDE     = var.edge_container_api_endpoint_override
      EDGE_NETWORK_API_ENDPOINT_OVERRIDE       = var.edge_network_api_endpoint_override
      HARDWARE_MANAGMENT_API_ENDPOINT_OVERRIDE = var.hardware_management_api_endpoint_override
      SOURCE_OF_TRUTH_REPO                     = var.source_of_truth_repo
      SOURCE_OF_TRUTH_BRANCH                   = var.source_of_truth_branch
      SOURCE_OF_TRUTH_PATH                     = var.source_of_truth_path
      PROJECT_ID_SECRETS                       = var.project_id_secrets
      GIT_SECRET_ID                            = var.git_secret_id
    }
    service_account_email = google_service_account.zone-watcher-agent.email
  }
}

resource "google_cloud_run_service_iam_member" "zone-active-metric-member" {
  count    = var.deploy-zone-active-monitor ? 1 : 0
  location = google_cloudfunctions2_function.zone-active-metric[0].location
  service  = google_cloudfunctions2_function.zone-active-metric[0].name
  role     = "roles/run.invoker"
  member   = google_service_account.gdce-provisioning-agent.member
}

resource "google_cloud_scheduler_job" "zone-active-metric-job" {
  count            = var.deploy-zone-active-monitor ? 1 : 0
  name             = "zone-active-metric-scheduler-${var.environment}"
  description      = "Trigger the ${google_cloudfunctions2_function.zone-active-metric[0].name}"
  schedule         = "*/10 * * * *" # Run every 10 minutes
  time_zone        = "Europe/Dublin"
  attempt_deadline = "320s"
  region           = var.region

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.zone-active-metric[0].service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.gdce-provisioning-agent.email
    }
  }
}
