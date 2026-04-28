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

    @mock.patch('src.main.get_git_token_from_secrets_manager')
    @mock.patch('src.main.ClusterIntentReader')
    def test_read_intent_data_fallback(self, mock_reader_cls, mock_get_token):
        """Test that cluster version falls back to fleet config if missing in main CSV."""
        mock_get_token.return_value = "mock-token"
        mock_reader_instance = mock.MagicMock()
        mock_reader_cls.return_value = mock_reader_instance
        
        main_csv = """store_id,fleet_project_id,machine_project_id,location,cluster_name,node_count,cluster_ipv4_cidr,services_ipv4_cidr,external_load_balancer_ipv4_address_pools,sync_repo,sync_branch,sync_dir,secrets_project_id,git_token_secrets_manager_name,cluster_version
store1,project1,machine1,us-central1,cluster1,3,10.0.0.0/16,10.1.0.0/16,1.1.1.1-1.1.1.10,repo1,main,.,sec-proj,git-sec,""
"""
        fleet_csv = """fleet_project_id,cluster_version
project1,1.12.0
"""
        mock_reader_instance.retrieve_source_of_truth.side_effect = [main_csv, fleet_csv]
        
        params = mock.MagicMock()
        params.source_of_truth_repo = "repo"
        params.source_of_truth_branch = "main"
        params.source_of_truth_path = "intent.csv"
        params.fleet_config_path = "fleet.csv"
        params.secrets_project_id = "sec-proj"
        params.git_secret_id = "git-sec"
        
        result = main.read_intent_data(params, 'fleet_project_id')
        
        self.assertIn(('project1', 'us-central1'), result)
        self.assertIn('store1', result[('project1', 'us-central1')])
        edge_zone = result[('project1', 'us-central1')]['store1']
        self.assertEqual(edge_zone.cluster_version, "1.12.0")

    @mock.patch('src.main.get_git_token_from_secrets_manager')
    @mock.patch('src.main.ClusterIntentReader')
    def test_read_intent_data_no_fleet_config(self, mock_reader_cls, mock_get_token):
        """Test that when fleet_config_path is None, fleet version validation is skipped but parsing continues."""
        mock_get_token.return_value = "mock-token"
        mock_reader_instance = mock.MagicMock()
        mock_reader_cls.return_value = mock_reader_instance
        
        main_csv = """store_id,fleet_project_id,machine_project_id,location,cluster_name,node_count,cluster_ipv4_cidr,services_ipv4_cidr,external_load_balancer_ipv4_address_pools,sync_repo,sync_branch,sync_dir,secrets_project_id,git_token_secrets_manager_name,cluster_version
store1,project1,machine1,us-central1,cluster1,3,10.0.0.0/16,10.1.0.0/16,1.1.1.1-1.1.1.10,repo1,main,.,sec-proj,git-sec,"1.13.0"
"""
        mock_reader_instance.retrieve_source_of_truth.return_value = main_csv
        
        params = mock.MagicMock()
        params.source_of_truth_repo = "repo"
        params.source_of_truth_branch = "main"
        params.source_of_truth_path = "intent.csv"
        params.fleet_config_path = None
        params.secrets_project_id = "sec-proj"
        params.git_secret_id = "git-sec"
        
        result = main.read_intent_data(params, 'fleet_project_id')
        
        self.assertIn(('project1', 'us-central1'), result)
        self.assertIn('store1', result[('project1', 'us-central1')])
        edge_zone = result[('project1', 'us-central1')]['store1']
        self.assertEqual(edge_zone.cluster_version, "1.13.0")
        # Assert ClusterIntentReader was only instantiated once (for the main CSV)
        mock_reader_cls.assert_called_once_with("repo", "main", "intent.csv", "mock-token")

    @mock.patch('src.main.get_git_token_from_secrets_manager')
    @mock.patch('src.main.ClusterIntentReader')
    def test_read_intent_data_robin_cns_invalid_version(self, mock_reader_cls, mock_get_token):
        """Test that Robin CNS validation fails if version is below 1.12.0."""
        mock_get_token.return_value = "mock-token"
        mock_reader_instance = mock.MagicMock()
        mock_reader_cls.return_value = mock_reader_instance
        
        main_csv = """store_id,fleet_project_id,machine_project_id,location,cluster_name,node_count,cluster_ipv4_cidr,services_ipv4_cidr,external_load_balancer_ipv4_address_pools,sync_repo,sync_branch,sync_dir,secrets_project_id,git_token_secrets_manager_name,cluster_version,enable_robin_cns
store1,project1,machine1,us-central1,cluster1,3,10.0.0.0/16,10.1.0.0/16,1.1.1.1-1.1.1.10,repo1,main,.,sec-proj,git-sec,"",true
"""
        fleet_csv = """fleet_project_id,cluster_version
project1,1.11.0
"""
        mock_reader_instance.retrieve_source_of_truth.side_effect = [main_csv, fleet_csv]
        
        params = mock.MagicMock()
        params.source_of_truth_repo = "repo"
        params.source_of_truth_branch = "main"
        params.source_of_truth_path = "intent.csv"
        params.fleet_config_path = "fleet.csv"
        params.secrets_project_id = "sec-proj"
        params.git_secret_id = "git-sec"
        
        result = main.read_intent_data(params, 'fleet_project_id')
        
        self.assertEqual(result.get(('project1', 'us-central1')), {})


class TestZoneActiveMetric(unittest.TestCase):

    @mock.patch('src.main.clients.get_monitoring_client')
    @mock.patch('src.main.get_zones')
    @mock.patch('src.main.ClusterIntentReader')
    @mock.patch('src.main.get_git_token_from_secrets_manager')
    @mock.patch('src.main.WatcherSettings')
    def test_zone_active_metric_api_failure(
        self,
        mock_watcher_settings,
        mock_get_git_token,
        mock_intent_reader_class,
        mock_get_zones,
        mock_get_monitoring_client,
    ):
        from google.api_core import exceptions
        
        # Arrange
        params = mock.MagicMock()
        params.project_id = "test-project"
        params.secrets_project_id = "test-secrets-project"
        params.git_secret_id = "test-git-secret"
        mock_watcher_settings.return_value = params

        mock_get_git_token.return_value = "test-token"

        mock_intent_reader = mock.MagicMock()
        mock_intent_reader_class.return_value = mock_intent_reader
        mock_intent_reader.retrieve_source_of_truth.return_value = (
            "fleet_project_id,location,store_id,cluster_name,machine_project_id\n"
            "test-fleet-project,test-location,store1,cluster1,test-machine-project\n"
        )

        mock_get_zones.side_effect = exceptions.ServerError("API down")

        mock_m_client = mock.MagicMock()
        mock_get_monitoring_client.return_value = mock_m_client

        # Act
        req = mock.MagicMock()
        main.zone_active_metric(req)

        # Assert
        mock_m_client.create_time_series.assert_called_once()
        args, kwargs = mock_m_client.create_time_series.call_args
        request = args[0]
        
        self.assertEqual(request.time_series[0].points[0].value.int64_value, 1)


class TestNetworkConnectionHeartbeat(unittest.TestCase):

    @mock.patch('src.main.clients.get_monitoring_client')
    @mock.patch('src.main.clients.get_edgenetwork_client')
    @mock.patch('src.main.clients.get_edgecontainer_client')
    @mock.patch('src.main.clients.get_hardware_management_client')
    @mock.patch('src.main.ClusterIntentReader')
    @mock.patch('src.main.get_git_token_from_secrets_manager')
    @mock.patch('src.main.WatcherSettings')
    def test_network_connection_heartbeat_success(
        self,
        mock_watcher_settings,
        mock_get_git_token,
        mock_intent_reader_class,
        mock_get_hwm_client,
        mock_get_ec_client,
        mock_get_en_client,
        mock_get_monitoring_client,
    ):
        from google.api_core import exceptions
        
        # Arrange
        params = mock.MagicMock()
        params.project_id = "test-project"
        params.secrets_project_id = "test-secrets-project"
        params.git_secret_id = "test-git-secret"
        mock_watcher_settings.return_value = params

        mock_get_git_token.return_value = "test-token"

        mock_intent_reader = mock.MagicMock()
        mock_intent_reader_class.return_value = mock_intent_reader
        mock_intent_reader.retrieve_source_of_truth.return_value = (
            "fleet_project_id,location,store_id,cluster_name,machine_project_id\n"
            "test-fleet-project,test-location,store1,cluster1,test-machine-project\n"
        )

        mock_hwm_client = mock.MagicMock()
        mock_get_hwm_client.return_value = mock_hwm_client
        
        mock_ec_client = mock.MagicMock()
        mock_get_ec_client.return_value = mock_ec_client
        
        mock_en_client = mock.MagicMock()
        mock_get_en_client.return_value = mock_en_client

        mock_m_client = mock.MagicMock()
        mock_get_monitoring_client.return_value = mock_m_client

        # Act
        req = mock.MagicMock()
        main.network_connection_heartbeat(req)

        # Assert
        mock_m_client.create_time_series.assert_called_once()
        args, kwargs = mock_m_client.create_time_series.call_args
        request = args[0]
        
        self.assertEqual(len(request.time_series), 2)
        for ts in request.time_series:
            self.assertEqual(ts.points[0].value.int64_value, 1)

