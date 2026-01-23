terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
    random = {
      source = "hashicorp/random"
    }
    archive = {
      source = "hashicorp/archive"
    }
  }
}

locals {
  target_projects   = length(var.monitored_project_ids) > 0 ? var.monitored_project_ids : [var.project_id]
  monitored_regions = length(var.monitored_regions) > 0 ? var.monitored_regions : [var.region]
}


resource "random_id" "main" {
  byte_length = 8
}

resource "google_firestore_database" "database" {
  project     = var.project_id
  name        = "hwm-events-db"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}

resource "google_pubsub_topic" "topic" {
  project = var.project_id
  name    = "hwm-events-zones-topic"
}

resource "google_storage_bucket" "bucket" {
  project       = var.project_id
  name          = "hwm-events-bucket-${random_id.main.hex}"
  location      = var.region
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
}

resource "google_service_account" "hwm_events_sa" {
  project      = var.project_id
  account_id   = "hwm-events-sa"
  display_name = "HWM Events Service Account"
}

resource "google_project_iam_member" "host_sa_roles" {
  for_each = toset([
    "roles/datastore.user",
    "roles/pubsub.publisher",
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.hwm_events_sa.email}"
}

resource "google_project_iam_member" "viewer_sa_roles" {
  for_each = toset(local.target_projects)

  project = each.value
  role    = "roles/gdchardwaremanagement.reader"
  member  = "serviceAccount:${google_service_account.hwm_events_sa.email}"
}

data "archive_file" "source" {
  type        = "zip"
  output_path = "/tmp/hwm_events_src-${random_id.main.hex}.zip"
  source_dir  = "${path.module}/src"
  excludes    = ["__pycache__", ".venv"]
}

resource "google_storage_bucket_object" "source" {
  name   = "source-${data.archive_file.source.output_sha}.zip"
  bucket = google_storage_bucket.bucket.name
  source = data.archive_file.source.output_path
}

resource "google_cloudfunctions2_function" "function" {
  project     = var.project_id
  name        = "hwm-events-function"
  location    = var.region
  description = "HWM Events Poller Function"

  build_config {
    runtime     = "python311"
    entry_point = "main"
    source {
      storage_source {
        bucket = google_storage_bucket.bucket.name
        object = google_storage_bucket_object.source.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 60
    environment_variables = {
      PROJECT_ID         = var.project_id
      REGION             = var.region
      FIRESTORE_DB       = google_firestore_database.database.name
      PUBSUB_TOPIC       = google_pubsub_topic.topic.name
      MONITORED_PROJECTS = join(",", local.target_projects)
      MONITORED_REGIONS  = join(",", local.monitored_regions)
      HWM_API_ENDPOINT   = var.hardware_management_api_endpoint_override
    }
    service_account_email = google_service_account.hwm_events_sa.email
  }
}

resource "google_cloud_run_service_iam_member" "invoker" {
  location = google_cloudfunctions2_function.function.location
  project  = var.project_id
  service  = google_cloudfunctions2_function.function.name
  role     = "roles/run.invoker"
  member   = google_service_account.hwm_events_sa.member
}

resource "google_cloud_scheduler_job" "job" {
  project          = var.project_id
  name             = "hwm-events-scheduler"
  description      = "Trigger the HWM events function"
  schedule         = var.scheduler_cron
  time_zone        = "UTC"
  attempt_deadline = "320s"
  region           = var.region

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.function.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.hwm_events_sa.email
    }
  }
}
