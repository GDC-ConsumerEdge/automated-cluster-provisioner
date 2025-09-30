# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest import mock
from google.auth import credentials as google_credentials
from google.cloud.gdchardwaremanagement_v1alpha import Zone
from src.acp_zone import ACPZone

auth_patch = mock.patch('google.auth.default')
mock_auth = auth_patch.start()
mock_credentials = mock.MagicMock(spec=google_credentials.Credentials)
mock_project_id = "mock-project"
mock_auth.return_value = (mock_credentials, mock_project_id)

clients_patch = mock.patch('src.clients.GoogleClients')
clients_patch.start()

from src import main

auth_patch.stop()
clients_patch.stop()

class TestMain(unittest.TestCase):

    def test_zone_ready_for_provisioning(self):
        result = main.verify_zone_state(Zone.State.READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS, "mock_store_id", False)
        self.assertTrue(result)

        result = main.verify_zone_state(Zone.State.CUSTOMER_FACTORY_TURNUP_CHECKS_STARTED, "mock_store_id", False)
        self.assertTrue(result)

    def test_zone_recreation_flag(self):
        result = main.verify_zone_state(Zone.State.ACTIVE, "mock_store_id", False)
        self.assertFalse(result)

        result = main.verify_zone_state(Zone.State.ACTIVE, "mock_store_id", True)
        self.assertTrue(result)

    def test_zone_preparing(self):
        result = main.verify_zone_state(Zone.State.PREPARING, "mock_store_id", False)
        self.assertFalse(result)

    @mock.patch('src.main.get_memberships')
    @mock.patch('src.main.get_zones')
    @mock.patch('src.main.clients.get_edgecontainer_client')
    @mock.patch('src.main.clients.get_cloudbuild_client')
    def test_cluster_watcher_worker_multi_project(
        self,
        mock_get_cloudbuild_client,
        mock_get_edgecontainer_client,
        mock_get_zones,
        mock_get_memberships,
    ):
        # Arrange
        mock_get_memberships.return_value = {}
        mock_get_zones.return_value = {}
        mock_edgecontainer_client = mock.MagicMock()
        mock_get_edgecontainer_client.return_value = mock_edgecontainer_client
        mock_edgecontainer_client.list_clusters.return_value = []
        mock_edgecontainer_client.common_location_path.return_value = (
            "projects/test-fleet-project/locations/test-location"
        )

        project_id = "test-fleet-project"
        location = "test-location"

        params = mock.MagicMock()
        params.cloud_build_trigger = "test-trigger"

        class MockStore:
            def __init__(self, fleet_project_id, location, machine_project_id):
                self.fleet_project_id = fleet_project_id
                self.location = location
                self.machine_project_id = machine_project_id

        stores = {
            "store1": MockStore(project_id, location, "machine-project-1"),
            "store2": MockStore(project_id, location, "machine-project-2"),
            "store3": MockStore(project_id, "other-location", "machine-project-3"),
            "store4": MockStore("other-fleet-project", location, "machine-project-4"),
        }

        # Act
        main._cluster_watcher_worker(project_id, location, stores, params)

        # Assert
        mock_get_zones.assert_has_calls(
            [
                mock.call("machine-project-1", location),
                mock.call("machine-project-2", location),
            ],
            any_order=True,
        )
        self.assertEqual(mock_get_zones.call_count, 2)