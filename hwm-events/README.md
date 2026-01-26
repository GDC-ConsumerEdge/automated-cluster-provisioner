# HWM Events

## Overview

`hwm-events` is a standalone component designed to watch for zone state changes in the GDC Hardware Management API. It periodically polls the API, tracks the state of zones, and emits events when a zone's state changes.

This component is useful for building event-driven automation or monitoring systems that need to react to hardware availability or maintenance events in Google Distributed Cloud.

## Architecture

The solution uses a serverless architecture on Google Cloud Platform:

1.  **Cloud Scheduler**: triggers the polling function on a defined schedule (default: every 5 minutes).
2.  **Cloud Function (2nd Gen)**:
    *   Queries the GDC Hardware Management API for zones in configured projects and regions.
    *   Compares the current state of each zone with the state stored in Firestore.
    *   Emits a `ZONE_STATE_CHANGE` event to Pub/Sub if the state has changed or is seen for the first time.
3.  **Firestore**: Acts as the state store, maintaining the last known state of each zone.
4.  **Pub/Sub**: Receives events. Downstream systems can subscribe to the `hwm-events-zones-topic` to consume these events.

### Event Format

Events published to Pub/Sub have the following JSON structure:

```json
{
  "event_type": "ZONE_STATE_CHANGE",
  "zone": "projects/my-project/locations/us-central1/zones/zone-1",
  "current_state": "READY",
  "previous_state": "PROVISIONING" 
}
```

*Note: `previous_state` will be `null` for newly discovered zones.*

## Getting Started

### Prerequisites

*   Google Cloud Project
*   Terraform >= 1.0
*   Permissions to create Cloud Functions, Firestore, Pub/Sub, and IAM roles.

### Installation

1.  Clone this repository.
2.  Create a `terraform.tfvars` file or pass variables via command line.
3.  Run Terraform:

```bash
terraform init
terraform apply
```

### Usage Example

```hcl
module "hwm_events" {
  source = "./hwm-events"

  project_id = "my-host-project"
  region     = "us-central1"
  
  # Monitor zones in these projects (optional, defaults to host project)
  monitored_project_ids = ["target-project-1", "target-project-2"]
  
  # Monitor zones in these regions (optional, defaults to host region)
  monitored_regions     = ["us-central1", "us-west1"]

  # API Endpoint override (optional)
  hardware_management_api_endpoint_override = "https://custom-hwm-endpoint.googleapis.com"
}
```

## Terraform Details

### Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| `project_id` | The Google Cloud Platform (GCP) project id | `string` | n/a | yes |
| `region` | GCP region to deploy resources | `string` | n/a | yes |
| `scheduler_cron` | Cron schedule for the Cloud Scheduler job | `string` | `*/5 * * * *` | no |
| `monitored_project_ids` | List of project IDs to monitor. If empty, defaults to the host project_id. | `list(string)` | `[]` | no |
| `monitored_regions` | List of regions to poll. If empty, defaults to `[var.region]`. | `list(string)` | `[]` | no |
| `hardware_management_api_endpoint_override` | GDC Hardware Management API Endpoint. | `string` | `""` | no |

### Outputs

| Name | Description |
|------|-------------|
| `function_uri` | The URI of the deployed Cloud Function |
| `pubsub_topic_id` | The ID of the Pub/Sub topic where events are published |
| `firestore_database_name` | The name of the Firestore database used for state tracking |

### Resources Created

*   **Google Cloud Function (v2)**: `hwm-events-function`
*   **Cloud Scheduler Job**: `hwm-events-scheduler`
*   **Pub/Sub Topic**: `hwm-events-zones-topic`
*   **Firestore Database**: `hwm-events-db`
*   **Service Account**: `hwm-events-sa`
*   **Designated Storage Bucket**: For function source code.

### IAM Permissions

The created Service Account `hwm-events-sa` is granted:
*   `roles/datastore.user` (Host Project)
*   `roles/pubsub.publisher` (Host Project)
*   `roles/logging.logWriter` (Host Project)
*   `roles/gdchardwaremanagement.reader` (On all monitored projects)
