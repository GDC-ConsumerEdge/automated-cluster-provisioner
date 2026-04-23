# https://github.com/hashicorp/terraform-provider-google/issues/11102
resource "time_sleep" "unknown-zone-timer" {
    depends_on = [ google_logging_metric.unknown-zones ]
    create_duration = "30s"
}

resource "google_monitoring_notification_channel" "cp_notification_channel" {
  display_name = "Cluster Provisioner Notification Channel"
  type         = "email"
  labels = {
    email_address = var.notification_channel_email
  }
  force_delete = false
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
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
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
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
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

resource "google_monitoring_alert_policy" "watcher-absence-alert" {
  display_name = "Watcher Execution Absence Alert"
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
  combiner = "OR"
  
  conditions {
    display_name = "Zone Watcher Absence"
    condition_absent {
      filter = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"${google_cloudfunctions2_function.zone-watcher.name}\" AND metric.type = \"run.googleapis.com/request_count\""
      duration = "1800s" # 30 minutes
      aggregations {
        alignment_period = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  conditions {
    display_name = "Cluster Watcher Absence"
    condition_absent {
      filter = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"${google_cloudfunctions2_function.cluster-watcher.name}\" AND metric.type = \"run.googleapis.com/request_count\""
      duration = "1800s" # 30 minutes
      aggregations {
        alignment_period = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "build-timeout-alert" {
  display_name = "Cloud Build Duration Timeout Alert"
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
  combiner = "OR"
  
  conditions {
    display_name = "Build duration exceeds 4 hours"
    condition_threshold {
      filter = "resource.type = \"build\" AND metric.type = \"cloudbuild.googleapis.com/build/duration\""
      comparison = "COMPARISON_GT"
      threshold_value = 14400 # 4 hours in seconds
      duration = "60s"
      aggregations {
        alignment_period = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }
}

resource "time_sleep" "cluster-creation-failure-csv-timer" {
    depends_on = [ google_logging_metric.cluster-creation-failure-csv ]
    create_duration = "30s"
}

resource "google_monitoring_alert_policy" "cluster-creation-failure-csv-alert" {
  depends_on = [ time_sleep.cluster-creation-failure-csv-timer ]
  display_name = "Cluster Creation Failed - Invalid Intent (Customer Action Required)"
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
  combiner = "OR"
  conditions {
    display_name = "CSV Intent Failure Alert"
    condition_prometheus_query_language {
      query = <<EOL
      count(rate(logging_googleapis_com:user_cluster_creation_failure_csv_${var.environment}{monitored_resource="build"}[1h])) by (cluster_name) > 0
        EOL
      
      duration = "3600s"
    }
  }
  documentation {
    content = "The cluster provisioning failed because the cluster intent CSV contains invalid or missing parameters. Please review the source of truth repository and ensure all required columns are filled correctly."
    mime_type = "text/markdown"
  }
}

resource "time_sleep" "cluster-creation-failure-healthcheck-timer" {
    depends_on = [ google_logging_metric.cluster-creation-failure-healthcheck ]
    create_duration = "30s"
}

resource "google_monitoring_alert_policy" "cluster-creation-failure-healthcheck-alert" {
  depends_on = [ time_sleep.cluster-creation-failure-healthcheck-timer ]
  display_name = "Cluster Creation Failed - Health Check Timeout (Customer Action Required)"
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
  combiner = "OR"
  conditions {
    display_name = "Health Check Timeout Alert"
    condition_prometheus_query_language {
      query = <<EOL
      count(rate(logging_googleapis_com:user_cluster_creation_failure_healthcheck_${var.environment}{monitored_resource="build"}[1h])) by (cluster_name) > 0
        EOL
      
      duration = "3600s"
    }
  }
  documentation {
    content = "The cluster provisioning failed because workloads did not become healthy within the timeout period. This usually indicates issues with customer-deployed workloads or environment readiness. Please check the cluster workloads and platform health checks for details."
    mime_type = "text/markdown"
  }
}

resource "time_sleep" "cluster-modify-failure-csv-timer" {
    depends_on = [ google_logging_metric.cluster-modify-failure-csv ]
    create_duration = "30s"
}

resource "google_monitoring_alert_policy" "cluster-modify-failure-csv-alert" {
  depends_on = [ time_sleep.cluster-modify-failure-csv-timer ]
  display_name = "Cluster Modify Failed - Invalid Intent (Customer Action Required)"
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
  combiner = "OR"
  conditions {
    display_name = "CSV Intent Modify Failure Alert"
    condition_prometheus_query_language {
      query = <<EOL
      count(rate(logging_googleapis_com:user_cluster_modify_failure_csv_${var.environment}{monitored_resource="build"}[1h])) by (cluster_name) > 0
        EOL
      
      duration = "3600s"
    }
  }
  documentation {
    content = "The cluster modification failed because the cluster intent CSV contains invalid or missing parameters. Please review the source of truth repository and ensure all required columns are filled correctly."
    mime_type = "text/markdown"
  }
}

resource "time_sleep" "cluster-creation-failure-source-access-timer" {
    depends_on = [ google_logging_metric.cluster-creation-failure-source-access ]
    create_duration = "30s"
}

resource "google_monitoring_alert_policy" "cluster-creation-failure-source-access-alert" {
  depends_on = [ time_sleep.cluster-creation-failure-source-access-timer ]
  display_name = "Cluster Creation Failed - Source Access Issue (Customer Action Required)"
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
  combiner = "OR"
  conditions {
    display_name = "Source Access Failure Alert"
    condition_prometheus_query_language {
      query = <<EOL
      count(rate(logging_googleapis_com:user_cluster_creation_failure_source_access_${var.environment}{monitored_resource="build"}[1h])) by (cluster_name) > 0
        EOL
      
      duration = "3600s"
    }
  }
  documentation {
    content = "The cluster provisioning failed because the system could not access the source of truth repository or retrieve the required secrets. Please check the Git token in Secret Manager and the repository URL configuration."
    mime_type = "text/markdown"
  }
}

resource "time_sleep" "cluster-creation-failure-robin-timer" {
    depends_on = [ google_logging_metric.cluster-creation-failure-robin ]
    create_duration = "30s"
}

resource "google_monitoring_alert_policy" "cluster-creation-failure-robin-alert" {
  depends_on = [ time_sleep.cluster-creation-failure-robin-timer ]
  display_name = "Cluster Creation Failed - Invalid Robin CNS Request (Customer Action Required)"
  notification_channels = [google_monitoring_notification_channel.cp_notification_channel.name]
  combiner = "OR"
  conditions {
    display_name = "Robin CNS Failure Alert"
    condition_prometheus_query_language {
      query = <<EOL
      count(rate(logging_googleapis_com:user_cluster_creation_failure_robin_${var.environment}{monitored_resource="build"}[1h])) by (cluster_name) > 0
        EOL
      
      duration = "3600s"
    }
  }
  documentation {
    content = "The cluster provisioning failed because Robin CNS was requested on an unsupported version. Robin CNS requires version 1.12.0 or higher. Please check the cluster intent configuration."
    mime_type = "text/markdown"
  }
}