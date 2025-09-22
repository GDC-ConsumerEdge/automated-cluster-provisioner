from dataclasses import dataclass
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

class ACPZoneCollection:
    """
    A collection class that handles querying and caching of ZoneStates from
    the GDC HardwareManagement API.
    """

    def __init__(self):
        self.zones = {}
        self.project_region_pairs = {}

        self.client = clients.get_hardware_management_client()

    def _ensure_cache_is_loaded(self, project_id: str, region: str):
        """
        Checks if zone in projects/{project}/locations/{region} have already been loaded.
        If not, then query for all zones within that project
        """
        if (project_id, region) not in self.project_region_pairs:
            self._populate_zones_cache(project_id, region)
            self.project_region_pairs[(project_id, region)] = True

    def _populate_zones_cache(self, project_id: str, region: str):

        request = gdchardwaremanagement_v1alpha.ListZonesRequest(
            parent=f"projects/{project_id}/locations/{region}"
        )

        for zone in self.client.list_zones(request):
            self.zones[zone.name] = ACPZone(
                name=zone.name,
                state=zone.state,
                globally_unique_id=zone.globally_unique_id,
                cluster_intent_verified=zone.cluster_intent_verified
            )

    def get_zone(self, zone_name: str) -> ACPZone:
        """
        :param zone_name: a string of the form f'projects/{machine_project}/locations/{location}/zones/{store_id}'
        
        """
        project_id = zone_name.split('/')[1]
        region = zone_name.split('/')[3]
        self._ensure_cache_is_loaded(project_id, region)

        return self.zones.get(zone_name)