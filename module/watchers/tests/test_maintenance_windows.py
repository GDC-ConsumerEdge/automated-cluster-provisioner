import unittest
from unittest import mock
from src import maintenance_windows
from src.cluster_intent_model import SourceOfTruthModel
from dateutil.parser import parse

class TestMaintenanceWindows(unittest.TestCase):

    def test_maintenance_exclusion_equality(self):
        window1 = maintenance_windows.MaintenanceExclusionWindow("test", parse("2024-07-20T12:00:00Z"), parse("2024-07-20T13:00:00Z"))
        window2 = maintenance_windows.MaintenanceExclusionWindow("test", parse("2024-07-20T12:00:00Z"), parse("2024-07-20T13:00:00Z"))
        window3 = maintenance_windows.MaintenanceExclusionWindow("test2", parse("2024-07-20T12:00:00Z"), parse("2024-07-20T13:00:00Z"))

        self.assertEqual(window1, window2)
        self.assertNotEqual(window1, window3)

    def test_get_exclusion_windows_from_sot_all_defined(self):
        store_info = SourceOfTruthModel(
            store_id="test",
            machine_project_id="test-project",
            fleet_project_id="test-project",
            cluster_name="test-cluster",
            location="test-location",
            node_count=3,
            cluster_ipv4_cidr="10.0.0.0/16",
            services_ipv4_cidr="10.1.0.0/16",
            external_load_balancer_ipv4_address_pools="1.1.1.1-1.1.1.10",
            sync_repo="test-repo",
            sync_branch="main",
            sync_dir=".",
            secrets_project_id="test-project",
            git_token_secrets_manager_name="test-secret",
            cluster_version="1.28",
            maintenance_exclusion_name_1="test1",
            maintenance_exclusion_start_1="2024-07-20T12:00:00Z",
            maintenance_exclusion_end_1="2024-07-20T13:00:00Z",
            maintenance_exclusion_name_2="test2",
            maintenance_exclusion_start_2="2024-07-21T12:00:00Z",
            maintenance_exclusion_end_2="2024-07-21T13:00:00Z"
        )

        expected_exclusions = {
            maintenance_windows.MaintenanceExclusionWindow("test1", parse("2024-07-20T12:00:00Z"), parse("2024-07-20T13:00:00Z")),
            maintenance_windows.MaintenanceExclusionWindow("test2", parse("2024-07-21T12:00:00Z"), parse("2024-07-21T13:00:00Z"))
        }

        actual_exclusions = maintenance_windows.MaintenanceExclusionWindow.get_exclusion_windows_from_sot(store_info)

        self.assertEqual(actual_exclusions, expected_exclusions)

    def test_get_exclusion_windows_from_sot_some_defined(self):
        store_info = SourceOfTruthModel(
            store_id="test",
            machine_project_id="test-project",
            fleet_project_id="test-project",
            cluster_name="test-cluster",
            location="test-location",
            node_count=3,
            cluster_ipv4_cidr="10.0.0.0/16",
            services_ipv4_cidr="10.1.0.0/16",
            external_load_balancer_ipv4_address_pools="1.1.1.1-1.1.1.10",
            sync_repo="test-repo",
            sync_branch="main",
            sync_dir=".",
            secrets_project_id="test-project",
            git_token_secrets_manager_name="test-secret",
            cluster_version="1.28",
            maintenance_exclusion_name_1="test1",
            maintenance_exclusion_start_1="2024-07-20T12:00:00Z",
            maintenance_exclusion_end_1="2024-07-20T13:00:00Z",
            maintenance_exclusion_name_2="test2",
            maintenance_exclusion_start_2="2024-07-21T12:00:00Z",
        )

        expected_exclusions = {
            maintenance_windows.MaintenanceExclusionWindow("test1", parse("2024-07-20T12:00:00Z"), parse("2024-07-20T13:00:00Z")),
        }

        actual_exclusions = maintenance_windows.MaintenanceExclusionWindow.get_exclusion_windows_from_sot(store_info)

        self.assertEqual(actual_exclusions, expected_exclusions)


    def test_get_exclusion_windows_from_sot_none_defined(self):
        store_info = SourceOfTruthModel(
            store_id="test",
            machine_project_id="test-project",
            fleet_project_id="test-project",
            cluster_name="test-cluster",
            location="test-location",
            node_count=3,
            cluster_ipv4_cidr="10.0.0.0/16",
            services_ipv4_cidr="10.1.0.0/16",
            external_load_balancer_ipv4_address_pools="1.1.1.1-1.1.1.10",
            sync_repo="test-repo",
            sync_branch="main",
            sync_dir=".",
            secrets_project_id="test-project",
            git_token_secrets_manager_name="test-secret",
            cluster_version="1.28",
        )

        expected_exclusions = set()

        actual_exclusions = maintenance_windows.MaintenanceExclusionWindow.get_exclusion_windows_from_sot(store_info)

        self.assertEqual(actual_exclusions, expected_exclusions)

    def test_get_exclusion_windows_from_api_response_defined(self):
        mock_cluster = mock.MagicMock()
        mock_cluster.maintenance_policy.maintenance_exclusions = [
            mock.MagicMock(
                id="test1",
                window=mock.MagicMock(
                    start_time=parse("2024-07-20T12:00:00Z"),
                    end_time=parse("2024-07-20T13:00:00Z")
                )
            )
        ]

        expected_exclusions = {
            maintenance_windows.MaintenanceExclusionWindow("test1", parse("2024-07-20T12:00:00Z"), parse("2024-07-20T13:00:00Z"))
        }

        actual_exclusions = maintenance_windows.MaintenanceExclusionWindow.get_exclusion_windows_from_cluster_response(mock_cluster)

        self.assertEqual(actual_exclusions, expected_exclusions)

    def test_get_exclusion_windows_from_cluster_response_not_defined(self):
        mock_cluster = mock.MagicMock()
        mock_cluster.maintenance_policy = None

        expected_exclusions = set()

        actual_exclusions = maintenance_windows.MaintenanceExclusionWindow.get_exclusion_windows_from_cluster_response(mock_cluster)

        self.assertEqual(actual_exclusions, expected_exclusions)