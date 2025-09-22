import unittest
from unittest.mock import MagicMock, patch
from src.acp_zone_collection import ACPZoneCollection, ACPZone
from google.cloud import gdchardwaremanagement_v1alpha

class TestACPZoneCollection(unittest.TestCase):

    @patch('src.acp_zone_collection.clients')
    def setUp(self, mock_clients):
        self.mock_hw_mgmt_client = MagicMock()
        mock_clients.get_hardware_management_client.return_value = self.mock_hw_mgmt_client
        self.zone_collection = ACPZoneCollection()

    def test_get_zone_uncached(self):
        project_id = "test-project"
        region = "test-region"
        zone_name = f"projects/{project_id}/locations/{region}/zones/test-zone"

        mock_zone = gdchardwaremanagement_v1alpha.types.Zone(
            name=zone_name,
            state=gdchardwaremanagement_v1alpha.types.Zone.State.ACTIVE,
            globally_unique_id="test-guid",
            cluster_intent_verified=False
        )
        self.mock_hw_mgmt_client.list_zones.return_value = [mock_zone]

        zone = self.zone_collection.get_zone(zone_name)

        self.assertIsInstance(zone, ACPZone)
        self.assertEqual(zone.name, zone_name)
        self.assertEqual(zone.state, gdchardwaremanagement_v1alpha.types.Zone.State.ACTIVE)
        self.mock_hw_mgmt_client.list_zones.assert_called_once()

    def test_get_zone_cached(self):
        project_id = "test-project"
        region = "test-region"
        zone_name = f"projects/{project_id}/locations/{region}/zones/test-zone"

        mock_zone = gdchardwaremanagement_v1alpha.types.Zone(
            name=zone_name,
            state=gdchardwaremanagement_v1alpha.types.Zone.State.ACTIVE,
            globally_unique_id="test-guid",
            cluster_intent_verified=False
        )
        self.mock_hw_mgmt_client.list_zones.return_value = [mock_zone]

        # First call to cache the zone
        self.zone_collection.get_zone(zone_name)
        # Second call should use the cache
        zone = self.zone_collection.get_zone(zone_name)

        self.assertIsInstance(zone, ACPZone)
        self.assertEqual(zone.name, zone_name)
        self.mock_hw_mgmt_client.list_zones.assert_called_once()
