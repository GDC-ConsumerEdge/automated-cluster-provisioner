from dataclasses import dataclass
from typing import Dict, MutableMapping
from google.cloud import gkehub_v1
from .clients import GoogleClients

clients = GoogleClients()

@dataclass
class ACPMembership:
    """
    A minimal representation of a GKEHub Membership. It only contains a subset
    of the fields of https://cloud.google.com/python/docs/reference/gkehub/latest/google.cloud.gkehub_v1.types.Membership
    in order to keep memory requirements low.
    """
    
    labels: MutableMapping[str, str]

def get_memberships(project_id: str, region: str) -> Dict[str, ACPMembership]:
    """
    Handles querying for memberships from the GKE Hub API.
    """
    client = clients.get_gkehub_client()

    request = gkehub_v1.ListMembershipsRequest(
        parent=f"projects/{project_id}/locations/global"
    )

    memberships = {}

    for membership in client.list_memberships(request):
        memberships[membership.name] = ACPMembership(
            labels=membership.labels
        )

    return memberships
