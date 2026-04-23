resource "google_logging_metric" "unknown-zones" {
  name   = "unknown-zones-${var.environment}"
  description = "Zones found in the environment, but are not specified as part of cluster intent"
  filter = <<EOT
(resource.type = "cloud_function"
resource.labels.function_name = "${google_cloudfunctions2_function.zone-watcher.name}"
resource.labels.region = "${var.region}")
 OR 
(resource.type = "cloud_run_revision"
resource.labels.service_name = "${google_cloudfunctions2_function.zone-watcher.name}"
resource.labels.location = "${var.region}")
 severity>=DEFAULT
textPayload=~"Zone found in environment but not in cluster source of truth"
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "zone"
      value_type  = "STRING"
      description = "zone name"
    }
  }

  label_extractors = {
    "zone" = "REGEXP_EXTRACT(textPayload, \"\\\"(.*?)\\\"\")"
  }
}

resource "google_logging_metric" "ready-stores" {
  name   = "ready-stores-${var.environment}"
  description = "Stores ready for provisioning"
  filter = <<EOT
(resource.type = "cloud_function"
resource.labels.function_name = "${google_cloudfunctions2_function.zone-watcher.name}"
resource.labels.region = "${var.region}")
 OR 
(resource.type = "cloud_run_revision"
resource.labels.service_name = "${google_cloudfunctions2_function.zone-watcher.name}"
resource.labels.location = "${var.region}")
 severity>=DEFAULT
textPayload=~"Store is ready for provisioning"
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "store_id"
      value_type  = "STRING"
      description = "store id"
    }
  }

  label_extractors = {
    "store_id" = "REGEXP_EXTRACT(textPayload, \"\\\"(.*?)\\\"\")"
  }
}

resource "google_logging_metric" "cluster-creation-success" {
  name   = "cluster-creation-success-${var.environment}"
  description = "Cluster Creation Success Count"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Creation Succeeded")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \": (.*)\")"
  }
}

resource "google_logging_metric" "cluster-creation-failure" {
  name   = "cluster-creation-failure-${var.environment}"
  description = "Cluster Creation Failure Count"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Creation Failed" AND NOT textPayload=~"\[CUSTOMER_ERROR\]")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \": (.*)\")"
  }
}

resource "google_logging_metric" "cluster-modify-success" {
  name   = "cluster-modify-success-${var.environment}"
  description = "Cluster Modify Success Count"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Modify Succeeded")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \": (.*)\")"
  }
}

resource "google_logging_metric" "cluster-modify-failure" {
  name   = "cluster-modify-failure-${var.environment}"
  description = "Cluster Modify Failure Count"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Modify Failed" AND NOT textPayload=~"\[CUSTOMER_ERROR\]")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \": (.*)\")"
  }
}

resource "google_logging_metric" "cluster-creation-failure-csv" {
  name   = "cluster-creation-failure-csv-${var.environment}"
  description = "Cluster Creation Failure Count due to CSV intent issues"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Creation Failed.*\[CUSTOMER_ERROR\] (Missing required parameter|Empty required parameter|Cluster intent not found|STORE_ID not set|ZONE not set)")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \"Failed for (.*?):\")"
  }
}

resource "google_logging_metric" "cluster-creation-failure-healthcheck" {
  name   = "cluster-creation-failure-healthcheck-${var.environment}"
  description = "Cluster Creation Failure Count due to workload health check timeouts"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Creation Failed.*\[CUSTOMER_ERROR\] Workloads are not healthy")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \"Failed for (.*?):\")"
  }
}

resource "google_logging_metric" "cluster-creation-failure-source-access" {
  name   = "cluster-creation-failure-source-access-${var.environment}"
  description = "Cluster Creation Failure Count due to Git or Secret access issues"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Creation Failed.*\[CUSTOMER_ERROR\] (Failed to retrieve git token|Failed to clone source of truth|Failed to copy cluster intent)")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \"Failed for (.*?):\")"
  }
}

resource "google_logging_metric" "cluster-creation-failure-robin" {
  name   = "cluster-creation-failure-robin-${var.environment}"
  description = "Cluster Creation Failure Count due to invalid Robin CNS configuration"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Creation Failed.*\[CUSTOMER_ERROR\] Invalid Robin CNS request")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \"Failed for (.*?):\")"
  }
}

resource "google_logging_metric" "cluster-modify-failure-csv" {
  name   = "cluster-modify-failure-csv-${var.environment}"
  description = "Cluster Modify Failure Count due to CSV intent issues"
  filter = <<EOT
(resource.type="build" textPayload=~"Cluster Modify Failed.*\[CUSTOMER_ERROR\] (Missing required parameter|Empty required parameter|Cluster intent not found|Missing maintenance exclusion window property)")
EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "cluster_name"
      value_type  = "STRING"
      description = "cluster name"
    }
  }

  label_extractors = {
    "cluster_name" = "REGEXP_EXTRACT(textPayload, \"Failed for (.*?):\")"
  }
}