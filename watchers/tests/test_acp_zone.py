import unittest
from unittest.mock import MagicMock, patch
from src.acp_zone import ACPZone, get_zones
from google.cloud import gdchardwaremanagement_v1alpha

class TestACPZone(unittest.TestCase):

    @patch('src.acp_zone.clients')
    def test_get_zones(self, mock_clients):
        mock_hw_mgmt_client = MagicMock()
        mock_clients.get_hardware_management_client.return_value = mock_hw_mgmt_client
        
        project_id = "test-project"
        region = "test-region"
        zone_name = f"projects/{project_id}/locations/{region}/zones/test-zone"

        mock_zone = gdchardwaremanagement_v1alpha.types.Zone(
            name=zone_name,
            state=gdchardwaremanagement_v1alpha.types.Zone.State.ACTIVE,
            globally_unique_id="test-guid",
            cluster_intent_verified=False
        )
        mock_hw_mgmt_client.list_zones.return_value = [mock_zone]

        zones = get_zones(project_id, region)

        self.assertIn(zone_name, zones)
        self.assertIsInstance(zones[zone_name], ACPZone)
        self.assertEqual(zones[zone_name].name, zone_name)
        self.assertEqual(zones[zone_name].state, gdchardwaremanagement_v1alpha.types.Zone.State.ACTIVE)
        
        expected_request = gdchardwaremanagement_v1alpha.ListZonesRequest(
            parent=f"projects/{project_id}/locations/{region}"
        )
        mock_hw_mgmt_client.list_zones.assert_called_once_with(expected_request)

if __name__ == '__main__':
    unittest.main()