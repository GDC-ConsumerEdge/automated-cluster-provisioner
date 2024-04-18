resource "google_project_service" "project" {
  for_each = toset(var.gcp_project_services)
  service  = each.value

  disable_on_destroy = false
}

resource "google_storage_bucket" "gdce-cluster-provisioner-bucket" {
  name          = "gdce-cluster-provisioner-bucket-${var.environment}"
  location      = "US"
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "apply-spec" {
  name         = "apply-spec.yaml.template"
  source       = "./apply-spec.yaml.template"
  content_type = "text/plain"
  bucket       = google_storage_bucket.gdce-cluster-provisioner-bucket.id
}

resource "google_storage_bucket_object" "cluster-secret-store" {
  name         = "cluster-secret-store.yaml.template"
  source       = "./cluster-secret-store.yaml"
  content_type = "text/plain"
  bucket       = google_storage_bucket.gdce-cluster-provisioner-bucket.id
}

resource "google_storage_bucket_object" "cluster-intent-registry" {
  name         = "cluster-intent-registry.csv"
  source       = "./cluster-intent-registry.csv"
  content_type = "text/plain"
  bucket       = google_storage_bucket.gdce-cluster-provisioner-bucket.id
}


// Not using google_cloudbuild_trigger resource due to missing 
// `automapSubstitutions` options and inline-config
module "gcloud" {
  source  = "terraform-google-modules/gcloud/google"
  version = "~> 3.4"

  platform              = "linux"
  additional_components = ["alpha"]

  create_cmd_entrypoint  = "gcloud"
  create_cmd_body        = <<EOL
     alpha builds triggers create manual \
       --name=gdce-cluster-provisioner-trigger-${var.environment} \
       --inline-config=create-cluster.yaml \
       --region=${var.region} \
       --service-account=projects/${var.project}/serviceAccounts/${google_service_account.gdce-provisioning-agent.email} \
       --substitutions _EDGE_CONTAINER_API_ENDPOINT_OVERRIDE=${var.edge_container_api_endpoint_override},_GKEHUB_API_ENDPOINT_OVERRIDE=${var.gke_hub_api_endpoint_override},_CLUSTER_INTENT_BUCKET=${google_storage_bucket.gdce-cluster-provisioner-bucket.name}
   EOL
  destroy_cmd_entrypoint = "gcloud"
  destroy_cmd_body       = "alpha builds triggers delete gdce-cluster-provisioner-trigger-${var.environment} --region ${var.region}"
}

resource "google_service_account" "gdce-provisioning-agent" {
  account_id = "gdce-prov-agent-${var.environment}"
}

resource "google_project_iam_member" "gdce-provisioning-agent-edge-admin" {
  project = var.project
  role    = "roles/edgecontainer.admin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-storage-admin" {
  project = var.project
  role    = "roles/storage.admin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-log-writer" {
  project = var.project
  role    = "roles/logging.logWriter"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-secret-accessor" {
  project = var.project
  role    = "roles/secretmanager.secretAccessor"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-hub-admin" {
  project = var.project
  role    = "roles/gkehub.admin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_project_iam_member" "gdce-provisioning-agent-hub-gateway" {
  project = var.project
  role    = "roles/gkehub.gatewayAdmin"
  member  = google_service_account.gdce-provisioning-agent.member
}

resource "google_service_account" "es-agent" {
  account_id = "es-agent-${var.environment}"
}

resource "google_project_iam_member" "es-agent-secret-accessor" {
  project = var.project
  role    = "roles/secretmanager.secretAccessor"
  member  = google_service_account.es-agent.member
}

data "archive_file" "zone-watcher" {
  type        = "zip"
  output_path = "/tmp/zone_watcher_gcf.zip"
  source_dir  = "../zone-watcher/cloud_function_source/"
}

resource "google_storage_bucket_object" "zone-watcher-src" {
  name   = "zone_watcher_gcf.zip"
  bucket = google_storage_bucket.gdce-cluster-provisioner-bucket.name
  source = data.archive_file.zone-watcher.output_path # Add path to the zipped function source code
}

resource "google_service_account" "zone-watcher-agent" {
  account_id   = "zone-watcher-agent-${var.environment}"
  display_name = "Zone Watcher Service Account"
}

resource "google_project_iam_member" "zone-watcher-agent-storage-admin" {
  project = var.project
  role    = "roles/storage.admin"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_project_iam_member" "zone-watcher-agent-cloud-build-editor" {
  project = var.project
  role    = "roles/cloudbuild.builds.editor"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_project_iam_member" "zone-watcher-agent-impersonate-sa" {
  project = var.project
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = google_service_account.zone-watcher-agent.member
}

resource "google_project_iam_member" "zone-watcher-agent-token-user" {
  project = var.project
  role    = "roles/iam.serviceAccountUser"
  member  = google_service_account.zone-watcher-agent.member
}



# zone-watcher cloud function
resource "google_cloudfunctions2_function" "zone-watcher" {
  name        = "zone-watcher-${var.environment}"
  location    = var.region
  description = "zone watcher function"

  build_config {
    runtime     = "python312"
    entry_point = "zone_watcher" # Set the entry point
    source {
      storage_source {
        bucket = google_storage_bucket.gdce-cluster-provisioner-bucket.name
        object = google_storage_bucket_object.zone-watcher-src.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 60
    environment_variables = {
      GOOGLE_CLOUD_PROJECT                 = var.project,
      CONFIG_CSV                           = "gs://${google_storage_bucket.gdce-cluster-provisioner-bucket.name}/${google_storage_bucket_object.cluster-intent-registry.output_name}",
      CB_TRIGGER_NAME                      = "gdce-cluster-provisioner-trigger-${var.environment}"
      REGION                               = var.region
      EDGE_CONTAINER_API_ENDPOINT_OVERRIDE = var.edge_container_api_endpoint_override
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
  schedule         = "0 * * * *"     # Run every hour
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