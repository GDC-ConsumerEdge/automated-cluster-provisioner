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
(resource.type="build" textPayload=~"Cluster Creation Failed")
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
(resource.type="build" textPayload=~"Cluster Modify Failed")
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