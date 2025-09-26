from dataclasses import dataclass
from typing import Dict
from google.cloud import gdchardwaremanagement_v1alpha
from .clients import GoogleClients

clients = GoogleClients()

@dataclass
class ACPZone:
    """
    A minimal representation of a GDC Zone. It only contains a subset
    of the fields of https://cloud.google.com/distributed-cloud/edge/latest/docs/reference/hardware/rest/v1alpha/projects.locations.zones#Zone
    in order to keep memory requirements low.
    """
    
    name: str
    state: gdchardwaremanagement_v1alpha.types.Zone.State
    globally_unique_id: str
    cluster_intent_verified: bool

def get_zones(project_id: str, region: str) -> Dict[str, ACPZone]:
    """
    Handles querying for zones from the GDC HardwareManagement API.
    """
    client = clients.get_hardware_management_client()

    request = gdchardwaremanagement_v1alpha.ListZonesRequest(
        parent=f"projects/{project_id}/locations/{region}"
    )

    zones = {}

    for zone in client.list_zones(request):
        zones[zone.name] = ACPZone(
            name=zone.name,
            state=zone.state,
            globally_unique_id=zone.globally_unique_id,
            cluster_intent_verified=zone.cluster_intent_verified
        )

    return zones
