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
        params.project_id = "test-host-project"
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

    def test_get_failure_reason(self):
        self.assertEqual(main._get_failure_reason(main.exceptions.PermissionDenied("error")), "permission_denied")
        self.assertEqual(main._get_failure_reason(main.exceptions.Unauthenticated("error")), "permission_denied")
        self.assertEqual(main._get_failure_reason(main.exceptions.InvalidArgument("error")), "invalid_argument")
        self.assertEqual(main._get_failure_reason(main.exceptions.NotFound("error")), "not_found")
        self.assertEqual(main._get_failure_reason(main.exceptions.ResourceExhausted("error")), "quota_exceeded")
        self.assertEqual(main._get_failure_reason(Exception("generic")), "unreachable")

    @mock.patch('src.main.clients.get_monitoring_client')
    def test_report_api_connectivity_metric_success(self, mock_get_monitoring_client):
        mock_m_client = mock.MagicMock()
        mock_get_monitoring_client.return_value = mock_m_client

        params = mock.MagicMock()
        params.project_id = "test-host-project"

        main.report_api_connectivity_metric(
            host_project_id="test-host-project",
            api="hwm",
            project_type="machine_project",
            project_id="mach-proj",
            location="us-central1",
            status=1,
            failure_reason=""
        )

        mock_m_client.create_time_series.assert_called_once()
        args, _ = mock_m_client.create_time_series.call_args
        request = args[0]

        self.assertEqual(request.name, "projects/test-host-project")
        self.assertEqual(len(request.time_series), 1)
        ts = request.time_series[0]
        self.assertEqual(ts.metric.type, "custom.googleapis.com/gdc_api_connectivity")
        self.assertEqual(ts.metric.labels["api"], "hwm")
        self.assertEqual(ts.metric.labels["project_type"], "machine_project")
        self.assertEqual(ts.metric.labels["target_project_id"], "mach-proj")
        self.assertEqual(ts.metric.labels["location"], "us-central1")
        self.assertEqual(ts.metric.labels["failure_reason"], "")
        self.assertEqual(ts.resource.type, "global")
        self.assertEqual(ts.resource.labels["project_id"], "test-host-project")
        self.assertEqual(ts.points[0].value.int64_value, 1)

    @mock.patch('src.main.report_api_connectivity_metric')
    @mock.patch('src.main.get_zones')
    @mock.patch('src.main.clients.get_cloudbuild_client')
    def test_zone_watcher_worker_reports_hwm_connectivity_success(
        self, mock_get_cb, mock_get_zones, mock_report
    ):
        mock_get_zones.return_value = {}
        params = mock.MagicMock()
        params.project_id = "test-host-project"
        builds = mock.MagicMock()

        class MockStore:
            fleet_project_id = "fleet-proj-1"
            intent_hash = "hash-1"

        stores = {"store1": MockStore()}

        main._zone_watcher_worker(
            machine_project="mach-proj",
            location="us-central1",
            stores=stores,
            params=params,
            builds=builds,
            machine_lists={},
            unprocessed_zones={},
            unprocessed_zones_lock=mock.MagicMock(),
        )

        mock_report.assert_called_once_with(
            host_project_id="test-host-project",
            api="hwm",
            project_type="machine_project",
            project_id="mach-proj",
            location="us-central1",
            status=1,
            failure_reason=""
        )

    @mock.patch('src.main.report_api_connectivity_metric')
    @mock.patch('src.main.get_zones')
    @mock.patch('src.main.clients.get_cloudbuild_client')
    def test_zone_watcher_worker_reports_hwm_connectivity_failure(
        self, mock_get_cb, mock_get_zones, mock_report
    ):
        mock_get_zones.side_effect = Exception("HWM API Connection Failed")
        params = mock.MagicMock()
        params.project_id = "test-host-project"
        builds = mock.MagicMock()

        class MockStore:
            fleet_project_id = "fleet-proj-1"
            intent_hash = "hash-1"

        stores = {"store1": MockStore()}

        result = main._zone_watcher_worker(
            machine_project="mach-proj",
            location="us-central1",
            stores=stores,
            params=params,
            builds=builds,
            machine_lists={},
            unprocessed_zones={},
            unprocessed_zones_lock=mock.MagicMock(),
        )

        self.assertEqual(result, 0)
        mock_report.assert_called_once_with(
            host_project_id="test-host-project",
            api="hwm",
            project_type="machine_project",
            project_id="mach-proj",
            location="us-central1",
            status=0,
            failure_reason="unreachable"
        )

    @mock.patch('src.main.report_api_connectivity_metric')
    @mock.patch('src.main.get_memberships')
    @mock.patch('src.main.get_zones')
    @mock.patch('src.main.clients.get_edgecontainer_client')
    @mock.patch('src.main.clients.get_cloudbuild_client')
    def test_cluster_watcher_worker_reports_metrics_success(
        self, mock_get_cb, mock_get_ec, mock_get_zones, mock_get_memberships, mock_report
    ):
        mock_get_memberships.return_value = {}
        mock_get_zones.return_value = {}
        
        mock_ec_client = mock.MagicMock()
        mock_get_ec.return_value = mock_ec_client
        mock_ec_client.list_clusters.return_value = []
        mock_ec_client.common_location_path.return_value = "path"

        class MockStore:
            fleet_project_id = "fleet-proj-1"
            machine_project_id = "mach-proj-1"
            location = "us-central1"

        stores = {"store1": MockStore()}
        params = mock.MagicMock()
        params.project_id = "test-host-project"

        main._cluster_watcher_worker("fleet-proj-1", "us-central1", stores, params)

        # Assert report call for edgecontainer connectivity status=1 (HWM is not reported by cluster_watcher)
        mock_report.assert_called_once_with(
            host_project_id="test-host-project",
            api="edgecontainer",
            project_type="fleet_project",
            project_id="fleet-proj-1",
            location="us-central1",
            status=1,
            failure_reason=""
        )

    @mock.patch('src.main.report_api_connectivity_metric')
    @mock.patch('src.main.get_memberships')
    @mock.patch('src.main.get_zones')
    @mock.patch('src.main.clients.get_edgecontainer_client')
    @mock.patch('src.main.clients.get_cloudbuild_client')
    def test_cluster_watcher_worker_reports_metrics_failure(
        self, mock_get_cb, mock_get_ec, mock_get_zones, mock_get_memberships, mock_report
    ):
        mock_get_memberships.return_value = {}
        mock_get_zones.return_value = {}
        
        mock_ec_client = mock.MagicMock()
        mock_get_ec.return_value = mock_ec_client
        # Edgecontainer API fails
        mock_ec_client.list_clusters.side_effect = Exception("EdgeContainer API down")
        mock_ec_client.common_location_path.return_value = "path"

        class MockStore:
            fleet_project_id = "fleet-proj-1"
            machine_project_id = "mach-proj-1"
            location = "us-central1"

        stores = {"store1": MockStore()}
        params = mock.MagicMock()
        params.project_id = "test-host-project"

        main._cluster_watcher_worker("fleet-proj-1", "us-central1", stores, params)

        # Assert report call for edgecontainer status=0
        mock_report.assert_called_once_with(
            host_project_id="test-host-project",
            api="edgecontainer",
            project_type="fleet_project",
            project_id="fleet-proj-1",
            location="us-central1",
            status=0,
            failure_reason="unreachable"
        )