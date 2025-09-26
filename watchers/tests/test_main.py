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

import google.auth
auth_patch = mock.patch('google.auth.default', autospec=True)
mock_auth = auth_patch.start()
mock_credentials = mock.MagicMock(spec=google_credentials.Credentials)
mock_project_id = "mock-project"
mock_auth.return_value = (mock_credentials, mock_project_id)

from src import main

auth_patch.stop()

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