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
from src.acp_zone_collection import ACPZone

import google.auth
auth_patch = mock.patch('google.auth.default', autospec=True)
mock_auth = auth_patch.start()
mock_credentials = mock.MagicMock(spec=google_credentials.Credentials)
mock_project_id = "mock-project"
mock_auth.return_value = (mock_credentials, mock_project_id)

from src import main

auth_patch.stop()

class TestMain(unittest.TestCase):

    @mock.patch('src.main.ACPZoneCollection')
    def test_zone_ready_for_provisioning(self, mock_zone_collection):
        mock_zone = mock.MagicMock(spec=ACPZone)
        mock_zone.state = Zone.State.READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS
        
        mock_zone_collection.return_value.get_zone.return_value = mock_zone

        main.zones = mock_zone_collection()
        result = main.verify_zone_state("mock_store_id", False)

        self.assertTrue(result)

        mock_zone.state = Zone.State.CUSTOMER_FACTORY_TURNUP_CHECKS_STARTED
        result = main.verify_zone_state("mock_store_id", False)
        self.assertTrue(result)

    @mock.patch('src.main.ACPZoneCollection')
    def test_zone_recreation_flag(self, mock_zone_collection):
        mock_zone = mock.MagicMock(spec=ACPZone)
        mock_zone.state = Zone.State.ACTIVE

        mock_zone_collection.return_value.get_zone.return_value = mock_zone
        main.zones = mock_zone_collection()
        result = main.verify_zone_state("mock_store_id", False)
        self.assertFalse(result)

        result = main.verify_zone_state("mock_store_id", True)
        self.assertTrue(result)

    @mock.patch('src.main.ACPZoneCollection')
    def test_zone_preparing(self, mock_zone_collection):
        mock_zone = mock.MagicMock(spec=ACPZone)
        mock_zone.state = Zone.State.PREPARING

        mock_zone_collection.return_value.get_zone.return_value = mock_zone
        main.zones = mock_zone_collection()
        result = main.verify_zone_state("mock_store_id", False)
        self.assertFalse(result)
        
    @mock.patch("src.main.ACPZoneCollection")
    def test_get_zone_cluster_intent_verified_false(self, mock_zone_collection):
        mock_zone = mock.MagicMock(spec=ACPZone)
        mock_zone.cluster_intent_verified = False

        mock_zone_collection.return_value.get_zone.return_value = mock_zone
        main.zones = mock_zone_collection()
        result = main.get_zone_cluster_intent_verified("mock_store_id")
        self.assertFalse(result)

    @mock.patch("src.main.ACPZoneCollection")
    def test_get_zone_cluster_intent_verified_true(self, mock_zone_collection):
        mock_zone = mock.MagicMock(spec=ACPZone)
        mock_zone.cluster_intent_verified = True

        mock_zone_collection.return_value.get_zone.return_value = mock_zone
        main.zones = mock_zone_collection()
        result = main.get_zone_cluster_intent_verified("mock_store_id")
        self.assertTrue(result)

    @mock.patch("src.main.GoogleClients")
    def test_set_zone_state_verify_cluster_intent(self, mock_clients):
        mock_hw_mgmt_client = mock.MagicMock()
        mock_operation = mock.MagicMock()
        mock_hw_mgmt_client.signal_zone_state.return_value = mock_operation
        mock_clients.return_value.get_hardware_management_client.return_value = mock_hw_mgmt_client
        main.clients = mock_clients()
        result = main.set_zone_state_verify_cluster_intent("mock_store_id")
        self.assertEqual(result, mock_operation)
        mock_hw_mgmt_client.signal_zone_state.assert_called_once()

    def test_reset_zone_cache(self):
        with mock.patch('src.main.ACPZoneCollection') as mock_zone_collection:
            main.reset_zone_cache()
            self.assertIsInstance(main.zones, mock.MagicMock)