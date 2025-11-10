module "cluster_automation" {
  source                       = "git::https://github.com/GDC-ConsumerEdge/automated-cluster-provisioner.git?ref=v1.4.0"
  project_id                   = "sample-project-id"
  source_of_truth_repo         = "github.com/GDC-ConsumerEdge/automated-cluster-provisioner"
  git_secret_id                = "example-pat-token"
  project_id_secrets           = "example-secrets-project"
  source_of_truth_path         = "example-source-of-truth.csv"
  region                       = "us-central1"
  environment                  = "prod"
  cluster_creation_timeout     = "86400"
  cluster_creation_max_retries = "0"
  notification_channel_email   = "ops@example.com"
  opt_in_build_messages        = true
  default_config_sync_version  = "1.18.3"
  vpc_connector                = google_vpc_access_connector.connector.id
  vpc_connector_egress_settings = "ALL_TRAFFIC"
}

# VPC for Cloud Functions
resource "google_compute_network" "function_vpc" {
  name                    = "cloud-functions-vpc-prod"
  project                 = "sample-project-id"
  auto_create_subnetworks = false
}

# Create an IP address
resource "google_compute_global_address" "private_ip_alloc" {
  name          = "private-ip-alloc-prod"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.function_vpc.id
}

# Create a private connection
resource "google_service_networking_connection" "default" {
  network                 = google_compute_network.function_vpc.self_link
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
}

# Import or export custom routes
resource "google_compute_network_peering_routes_config" "peering_routes" {
  peering = google_service_networking_connection.default.peering
  network = google_compute_network.function_vpc.name

  import_custom_routes = true
  export_custom_routes = true
}

resource "google_compute_subnetwork" "function_subnet" {
  name          = "cloud-functions-subnet-prod"
  region        = "us-central1"
  network       = google_compute_network.function_vpc.name
  ip_cidr_range = "10.0.0.0/28"
  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
  private_ip_google_access = true
}

# VPC Serverless Connector
resource "google_vpc_access_connector" "connector" {
  name   = "serverless-connector-prod"
  region = "us-central1"
  # network = google_compute_network.function_vpc.name
  subnet {
    name = google_compute_subnetwork.function_subnet.name
  }
  min_instances = 2
  max_instances = 3
}

resource "google_compute_router" "nat_router" {
  name    = "nat-router-prod"
  region  = google_compute_subnetwork.function_subnet.region
  network = google_compute_network.function_vpc.name
}

resource "google_compute_router_nat" "nat_gateway" {
  name                               = "nat-gateway-prod"
  router                             = google_compute_router.nat_router.name
  region                             = google_compute_subnetwork.function_subnet.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
