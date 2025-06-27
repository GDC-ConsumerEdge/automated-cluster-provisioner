# https://github.com/hashicorp/terraform-provider-google/issues/11102
resource "time_sleep" "unknown-zone-timer" {
    depends_on = [ google_logging_metric.unknown-zones ]
    create_duration = "30s"
}

resource "google_monitoring_alert_policy" "unknown-zone-alert" {
  depends_on = [ time_sleep.unknown-zone-timer ]
  display_name = "Unknown Zone Alert"
  combiner = "OR"
  conditions {
    display_name = "Unknown Zone Alert"
    condition_prometheus_query_language {
      query = <<EOL
      count(rate(logging_googleapis_com:user_unknown_zones_${var.environment}{monitored_resource="cloud_run_revision"}[1h])) by (zone) > 0
        EOL
      
      duration = "3600s"
    }
  }
}

# https://github.com/hashicorp/terraform-provider-google/issues/11102
resource "time_sleep" "cluster-creation-failure-timer" {
    depends_on = [ google_logging_metric.cluster-creation-failure ]
    create_duration = "30s"
}

resource "google_monitoring_alert_policy" "cluster-creation-failure-alert" {
  depends_on = [ time_sleep.cluster-creation-failure-timer ]
  display_name = "Cluster Creation Failure Alert"
  combiner = "OR"
  conditions {
    display_name = "Cluster Creation Failure Alert"
    condition_prometheus_query_language {
      query = <<EOL
      count(rate(logging_googleapis_com:user_cluster_creation_failure_${var.environment}{monitored_resource="build"}[1h])) by (cluster_name) > 0
        EOL
      
      duration = "3600s"
    }
  }
}

# https://github.com/hashicorp/terraform-provider-google/issues/11102
resource "time_sleep" "cluster-modify-failure-timer" {
    depends_on = [ google_logging_metric.cluster-modify-failure ]
    create_duration = "30s"
}

resource "google_monitoring_alert_policy" "cluster-modify-failure-alert" {
  depends_on = [ time_sleep.cluster-modify-failure-timer ]
  display_name = "Cluster Modify Failure Alert"
  combiner = "OR"
  conditions {
    display_name = "Cluster Modify Failure Alert"
    condition_prometheus_query_language {
      query = <<EOL
      count(rate(logging_googleapis_com:user_cluster_modify_failure_${var.environment}{monitored_resource="build"}[1h])) by (cluster_name) > 0
        EOL
      
      duration = "3600s"
    }
  }
}