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

from google.cloud.gdchardwaremanagement_v1alpha import Zone, SignalZoneStateRequest

# Mock Zone with a new field called cluster_intent_verified until its available by HW API.
Zone.cluster_intent_verified = mock.MagicMock()

import google.auth

auth_patch = mock.patch("google.auth.default", autospec=True)
mock_auth = auth_patch.start()
mock_credentials = mock.MagicMock(spec=google_credentials.Credentials)
mock_project_id = "mock-project"
mock_auth.return_value = (mock_credentials, mock_project_id)

from src import main

auth_patch.stop()


class TestMain(unittest.TestCase):
    @mock.patch(
        "google.cloud.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient"
    )
    def test_zone_ready_for_provisioning(self, mock_client):
        mock_zone = mock.MagicMock()
        mock_zone.state = Zone.State.READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS

        mock_client.return_value.get_zone.return_value = mock_zone

        result = main.verify_zone_state("mock_store_id", False)

        self.assertTrue(result)

        mock_zone.state = Zone.State.CUSTOMER_FACTORY_TURNUP_CHECKS_STARTED
        result = main.verify_zone_state("mock_store_id", False)
        self.assertTrue(result)

    @mock.patch(
        "google.cloud.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient"
    )
    def test_zone_recreation_flag(self, mock_client):
        mock_zone = mock.MagicMock()
        mock_zone.state = Zone.State.ACTIVE

        mock_client.return_value.get_zone.return_value = mock_zone

        result = main.verify_zone_state("mock_store_id", False)
        self.assertFalse(result)

        result = main.verify_zone_state("mock_store_id", True)
        self.assertTrue(result)

    @mock.patch(
        "google.cloud.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient"
    )
    def test_zone_preparing(self, mock_client):
        mock_zone = mock.MagicMock()
        mock_zone.state = Zone.State.PREPARING

        mock_client.return_value.get_zone.return_value = mock_zone

        result = main.verify_zone_state("mock_store_id", False)
        self.assertFalse(result)

    @mock.patch(
        "google.cloud.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient"
    )
    def test_get_zone_cluster_intent_presence_true(self, mock_client):
        mock_zone = mock.MagicMock()
        mock_zone.cluster_intent_verified = True

        mock_client.return_value.get_zone.return_value = mock_zone

        result = main.get_zone_cluster_intent_presence("mock_store_id")
        self.assertTrue(result)

    @mock.patch(
        "google.cloud.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient"
    )
    def test_get_zone_cluster_intent_presence_false(self, mock_client):
        mock_zone = mock.MagicMock()
        mock_zone.cluster_intent_verified = False

        mock_client.return_value.get_zone.return_value = mock_zone

        result = main.get_zone_cluster_intent_presence("mock_store_id")
        self.assertFalse(result)
