"""HWM Events Poller Cloud Function.

This module polls the Hardware Management API for zone states,
tracks state changes in Firestore, and publishes events to Pub/Sub.
"""

import json
import logging
import os
from typing import Any, Optional
from urllib.parse import urlparse

import functions_framework
import google.auth
from google.api_core import client_options
from google.cloud import firestore
from google.cloud import gdchardwaremanagement_v1alpha
from google.cloud import pubsub_v1


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

creds, auth_project = google.auth.default()

def poll_zones(
    hwm_client: gdchardwaremanagement_v1alpha.GDCHardwareManagementClient,
    db: firestore.Client,
    publisher: pubsub_v1.PublisherClient,
    host_project_id: str,
    target_project_id: str,
    region: str,
    topic: str,
) -> None:
    """Polls HWM zones and emits events on state changes.

    Args:
        hwm_client: Client for HWM API.
        db: Client for Firestore.
        publisher: Client for Pub/Sub.
        host_project_id: Project ID where Pub/Sub topic resides.
        target_project_id: Project ID to poll for zones.
        region: GCP Region.
        topic: Pub/Sub topic name.
    """
    topic_path = publisher.topic_path(host_project_id, topic)
    parent = f"projects/{target_project_id}/locations/{region}"
    request = gdchardwaremanagement_v1alpha.ListZonesRequest(parent=parent)
    zones_ref = db.collection("zone_states")

    for zone in hwm_client.list_zones(request):
        try:
            zone_name = zone.name

            try:
                current_state = gdchardwaremanagement_v1alpha.Zone.State(zone.state).name
            except (ValueError, AttributeError):
                current_state = str(zone.state)

            # Firestore IDs cannot contain slashes
            doc_ref = zones_ref.document(zone_name.replace("/", "_"))
            doc = doc_ref.get()

            previous_state = None
            should_emit = False

            if doc.exists:
                data = doc.to_dict()
                previous_state = data.get("state")
                if current_state != previous_state:
                    should_emit = True
                    logger.info(
                        f"Zone {zone_name} state changed: {previous_state} -> {current_state}"
                    )
            else:
                should_emit = True
                logger.info(f"Zone {zone_name} discovered with state: {current_state}")

            if should_emit:
                doc_ref.set({
                    "state": current_state,
                    "last_updated": firestore.SERVER_TIMESTAMP
                })

                message_data = {
                    "event_type": "ZONE_STATE_CHANGE",
                    "zone": zone_name,
                    "current_state": current_state,
                    "previous_state": previous_state,
                }
                data_str = json.dumps(message_data)
                future = publisher.publish(
                    topic_path,
                    data_str.encode("utf-8"),
                    zone=zone_name,
                    event_type="ZONE_STATE_CHANGE",
                )
                logger.info(f"Published event for {zone_name}: {future.result()}")

        except Exception as e:
            logger.error(f"Error processing zone {zone.name if 'zone' in locals() else 'unknown'}: {e}", exc_info=True)
            continue


@functions_framework.http
def main(request: Any) -> tuple[str, int]:
    """HTTP Cloud Function entry point.

    Args:
        request: The HTTP request object.

    Returns:
        tuple[str, int]: A tuple containing the response text and HTTP status code.
    """
    logger.info("Starting HWM Events Poller")

    try:
        project_id = os.environ.get("PROJECT_ID")
        monitored_projects_str = os.environ.get("MONITORED_PROJECTS")
        region = os.environ.get("REGION")
        firestore_db = os.environ.get("FIRESTORE_DB")
        pubsub_topic = os.environ.get("PUBSUB_TOPIC")
        hwm_api_endpoint = os.environ.get("HWM_API_ENDPOINT")

        if not all([project_id, region, firestore_db, pubsub_topic]):
            raise ValueError("Missing required environment variables")


        if hwm_api_endpoint:
            op = client_options.ClientOptions(
                api_endpoint=urlparse(hwm_api_endpoint).netloc
            )
            hwm_client = gdchardwaremanagement_v1alpha.GDCHardwareManagementClient(
                client_options=op
            )
        else:
            hwm_client = gdchardwaremanagement_v1alpha.GDCHardwareManagementClient()

        db = firestore.Client(project=project_id, database=firestore_db)
        publisher = pubsub_v1.PublisherClient()


        # Run logic for each monitored project and region
        monitored_projects = monitored_projects_str.split(",") if monitored_projects_str else [project_id]
        monitored_regions_str = os.environ.get("MONITORED_REGIONS")
        monitored_regions = monitored_regions_str.split(",") if monitored_regions_str else [region]
        
        for target_project in monitored_projects:
            target_project = target_project.strip()
            if not target_project:
                continue
                
            for target_region in monitored_regions:
                target_region = target_region.strip()
                if not target_region:
                    continue

                logger.info(f"Polling zones for project: {target_project}, region: {target_region}")
                poll_zones(
                    hwm_client=hwm_client,
                    db=db,
                    publisher=publisher,
                    host_project_id=project_id,
                    target_project_id=target_project,
                    region=target_region,
                    topic=pubsub_topic,
                )

        return "Polled HWM zones successfully", 200

    except Exception as e:
        logger.error(f"Error checking zones: {e}", exc_info=True)
        return f"Error: {e}", 500
