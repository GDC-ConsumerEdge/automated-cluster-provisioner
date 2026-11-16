module "cluster_automation" {
  source                       = "git::https://github.com/GDC-ConsumerEdge/automated-cluster-provisioner.git?ref=v1.5.2"
  project_id                   = "sample-project-id"
  source_of_truth_repo         = "github.com/GDC-ConsumerEdge/automated-cluster-provisioner"
  git_secret_id                = "example-pat-token"
  project_id_secrets           = "example-secrets-project"
  source_of_truth_path         = "example-source-of-truth.csv"
  fleet_config_path            = "fleet-version-config.csv"
  region                       = "us-central1"
  environment                  = "prod"
  cluster_creation_timeout     = "86400"
  cluster_creation_max_retries = "0"
  notification_channel_email   = "ops@example.com"
  opt_in_build_messages        = true
  default_config_sync_version  = "1.26.0"
  legacy_config_sync_version   = "1.22.2"
}