###########################
# Cluster Automation SA Permissions #
resource "google_project_iam_member" "cluster_provisioning_sa_edgecontainer_admin" {
  project = var.fleet_project
  role    = "roles/edgecontainer.admin"
  member  = module.cluster_automation.gdce_provisioner_sa_email
}

resource "google_project_iam_member" "cluster_provisioning_sa_edgenetwork_admin" {
  project = var.fleet_project
  role    = "roles/edgenetwork.admin"
  member  = module.cluster_automation.gdce_provisioner_sa_email
}

resource "google_project_iam_member" "cluster_provisioning_sa_logwriter" {
  project = var.fleet_project
  role    = "roles/logging.logWriter"
  member  = module.cluster_automation.gdce_provisioner_sa_email
}

resource "google_project_iam_member" "cluster_provisioning_sa_monitor_editor" {
  project = var.fleet_project
  role    = "roles/monitoring.editor"
  member  = module.cluster_automation.gdce_provisioner_sa_email
}

resource "google_project_iam_member" "cluster_provisioning_sa_gkehub_admin" {
  project = var.fleet_project
  role    = "roles/gkehub.admin"
  member  = module.cluster_automation.gdce_provisioner_sa_email
}

resource "google_project_iam_member" "cluster_provisioning_sa_gkehub_gatewayadmin" {
  project = var.fleet_project
  role    = "roles/gkehub.gatewayAdmin"
  member  = module.cluster_automation.gdce_provisioner_sa_email
}

resource "google_project_iam_member" "cluster_provisioning_sa_hardwaremanagement_operator" {
  project = var.fleet_project
  role    = "roles/gdchardwaremanagement.operator"
  member  = module.cluster_automation.gdce_provisioner_sa_email
}

resource "google_project_iam_member" "zone_watcher_sa_hardwaremanagement_reader" {
  project = var.fleet_project
  role    = "roles/gdchardwaremanagement.reader"
  member  = module.cluster_automation.zone_watcher_sa_email
}

resource "google_project_iam_member" "zone_watcher_sa_edgecontainer_viewer" {
  project = var.fleet_project
  role    = "roles/edgecontainer.viewer"
  member  = module.cluster_automation.zone_watcher_sa_email
}

resource "google_project_iam_member" "zone_watcher_sa_edgenetwork_viewer" {
  project = var.fleet_project
  role    = "roles/edgenetwork.viewer"
  member  = module.cluster_automation.zone_watcher_sa_email
}