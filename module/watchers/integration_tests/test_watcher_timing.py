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

import os
import time
import unittest
from unittest import mock
from unittest.mock import MagicMock

import flask
from google.auth import credentials as google_credentials
from google.cloud import edgecontainer

auth_patch = mock.patch('google.auth.default')
mock_auth = auth_patch.start()
mock_credentials = mock.MagicMock(spec=google_credentials.Credentials)
mock_project_id = "mock-project"
mock_auth.return_value = (mock_credentials, mock_project_id)

clients_patch = mock.patch('src.clients.GoogleClients')
clients_patch.start()

from src import main
from src.main import Zone
from src.watcher_settings import WatcherSettings

auth_patch.stop()
clients_patch.stop()

class TestWatcherIntegration(unittest.TestCase):

    @unittest.skipUnless(os.environ.get('RUN_PERF_TEST'), "Skipping perf test")
    @mock.patch('google.auth')
    @mock.patch("src.main.get_zone")
    @mock.patch("google.cloud.devtools.cloudbuild.CloudBuildClient")
    @mock.patch("google.cloud.edgecontainer.EdgeContainerClient")
    @mock.patch("src.main.read_intent_data")
    @mock.patch("src.main.WatcherSettings")
    def test_zone_watcher_integration_multiple_stores(
        self,
        mock_watcher_settings,
        mock_read_intent_data,
        mock_ec_client,
        mock_cb_client,
        mock_get_zone,
        mock_auth
    ):
        """
        Tests the zone_watcher function with variable number of projects, regions, and zones.
        Endpoints to retrieve machines and zone state are mocked out with a tunable latency to test
        the impact of different delay conditions on the function.
        """

        number_of_projects = 10
        number_of_regions_within_project = 5
        number_of_stores_within_region = 20
        get_zone_latency = 0.5
        list_machines_per_machine_latency = 0.05

        print("Total clusters = ", number_of_projects * number_of_regions_within_project * number_of_stores_within_region)

        # --- Setup Mock Data ---
        # Mock environment parameters
        params = WatcherSettings(
            project_id="test-project",
            secrets_project_id="test-project",
            region="us-central1",
            cloud_build_trigger_name="test-trigger",
            git_secret_id="secret-id",
            source_of_truth_repo="test-repo",
            source_of_truth_branch="main",
            source_of_truth_path="main/",
        )

        mock_watcher_settings.return_value = params 

        intent_data = generate_cluster_intent(number_of_projects, number_of_regions_within_project, number_of_stores_within_region)
        mock_read_intent_data.return_value = intent_data

        mock_get_zone.side_effect = generate_get_zone_function(get_zone_latency)

        mock_ec_client.return_value.list_machines.side_effect = generate_list_machines_function(list_machines_per_machine_latency, number_of_projects, number_of_regions_within_project, number_of_stores_within_region)

        # Ends up consumed as input for mocked out list_machines.
        def common_location_path(project, location):
            return f"projects/{project}/locations/{location}"

        mock_ec_client.return_value.common_location_path.side_effect = common_location_path

        # Mock CloudBuildClient
        mock_run_build_trigger = MagicMock()
        mock_cb_client.return_value.run_build_trigger = (
            mock_run_build_trigger
        )

        # --- Invoke the Function ---
        req = MagicMock(spec=flask.Request)
        main.zone_watcher(req)

        # --- Assertions ---
        # Verify that the intent data was read
        mock_read_intent_data.assert_called_once()

        # Assert that get zones are being called for generated zones
        mock_get_zone.assert_any_call('projects/project-0/locations/region-0/zones/store1')
        mock_get_zone.assert_any_call('projects/project-9/locations/region-4/zones/store50')

    @unittest.skipUnless(os.environ.get('RUN_PERF_TEST'), "Skipping perf test")
    @mock.patch('google.auth')
    @mock.patch("src.main.get_zone")
    @mock.patch("google.cloud.devtools.cloudbuild.CloudBuildClient")
    @mock.patch("google.cloud.edgenetwork.EdgeNetworkClient")
    @mock.patch("google.cloud.edgecontainer.EdgeContainerClient")
    @mock.patch("src.main.read_intent_data")
    @mock.patch("src.main.WatcherSettings")
    def test_cluster_watcher_integration_multiple_stores(
        self,
        mock_watcher_settings,
        mock_read_intent_data,
        mock_ec_client,
        mock_en_client,
        mock_cb_client,
        mock_get_zone,
        mock_auth
    ):
        """
        Tests the cluster_watcher function with variable number of projects, regions, and zones.
        Endpoints to retrieve machines and zone state are mocked out with a tunable latency to test
        the impact of different delay conditions on the function.
        """

        number_of_projects = 10
        number_of_regions_within_project = 5
        number_of_stores_within_region = 20
        get_zone_latency = 0.5
        list_subnets_latency = 0.5
        list_machines_per_machine_latency = 0.05
        list_clusters_per_cluster_latency = 0.1

        print("Total clusters = ", number_of_projects * number_of_regions_within_project * number_of_stores_within_region)

        # --- Setup Mock Data ---
        # Mock environment parameters
        params = WatcherSettings(
            project_id="test-project",
            secrets_project_id="test-project",
            region="us-central1",
            cloud_build_trigger_name="test-trigger",
            git_secret_id="secret-id",
            source_of_truth_repo="test-repo",
            source_of_truth_branch="main",
            source_of_truth_path="main/",
        )

        mock_watcher_settings.return_value = params 

        intent_data = generate_cluster_intent(number_of_projects, number_of_regions_within_project, number_of_stores_within_region)
        mock_read_intent_data.return_value = intent_data

        mock_get_zone.side_effect = generate_get_zone_function(get_zone_latency)

        mock_ec_client.return_value.list_machines.side_effect = generate_list_machines_function(list_machines_per_machine_latency, number_of_projects, number_of_regions_within_project, number_of_stores_within_region)
        mock_ec_client.return_value.list_clusters.side_effect = generate_list_clusters_function(list_clusters_per_cluster_latency, number_of_projects, number_of_regions_within_project, number_of_stores_within_region)

        # Ends up consumed as input for mocked out list_machines.
        def common_location_path(project, location):
            return f"projects/{project}/locations/{location}"

        mock_ec_client.return_value.common_location_path.side_effect = common_location_path
        mock_en_client.return_value.common_location_path.side_effect = common_location_path

        def empty_list_subnets_with_delay(req):
            time.sleep(list_subnets_latency)
            return []

        mock_en_client.return_value.list_subnets.side_effect = empty_list_subnets_with_delay

        # Mock CloudBuildClient
        mock_run_build_trigger = MagicMock()
        mock_cb_client.return_value.run_build_trigger = (
            mock_run_build_trigger
        )

        # --- Invoke the Function ---
        req = MagicMock(spec=flask.Request)
        main.cluster_watcher(req)

        # --- Assertions ---
        # Verify that the intent data was read
        mock_read_intent_data.assert_called_once()

        # Assert that get zones are being called for generated zones
        mock_get_zone.assert_any_call('projects/project-0/locations/region-0/zones/store1')
        mock_get_zone.assert_any_call('projects/project-1/locations/region-1/zones/store10')


def generate_cluster_intent(number_of_projects, number_of_regions_within_project, number_of_stores_within_region):

    intent_data = {}
    z = 1

    for p in range(number_of_projects):
        for r in range(number_of_regions_within_project):
            for s in range(number_of_stores_within_region):
                proj_loc_key = (f"project-{p}", f"region-{r}")


                if proj_loc_key not in intent_data:
                    intent_data[proj_loc_key] = {}

                intent_data[proj_loc_key][f"store{z}"] = {
                    "store_id": f"store{z}",
                    "zone_name": None,
                    "machine_project_id": f"project-{p}",
                    "fleet_project_id": f"project-{p}",
                    "cluster_name": f"cluster-{p}-{r}-{s}",
                    "location": "us-central1",
                    "node_count": "3",
                    "recreate_on_delete": False,
                    "sync_branch": "main",
                    "maintenance_window_recurrence": "",
                    "maintenance_window_start": "",
                    "maintenance_window_end": ""
                }

                z += 1

    return intent_data


def generate_list_machines_function(delay_seconds_per_zone, number_of_projects, number_of_regions_within_project, number_of_zones_within_region):
    def list_machines(list_machines_req):
        project = list_machines_req.parent.split("/")[1]
        region = list_machines_req.parent.split("/")[3]


        machines = []

        z = 0

        for p in range(number_of_projects):
            for r in range(number_of_regions_within_project):
                for s in range(number_of_zones_within_region):
                    z += 1

                    if (project != f"project-{p}" or region != f"region-{r}"):
                        continue

                    machines.append(edgecontainer.Machine(
                            name=f"machine{z}01", zone=f"zone{z}", hosted_node=f"projects/project-{p}/locations/region-{r}/clusters/cluster-{p}-{r}-{s}/controlPlane"
                        ))

                    machines.append(edgecontainer.Machine(
                            name=f"machine{z}02", zone=f"zone{z}", hosted_node=f"projects/project-{p}/locations/region-{r}/clusters/cluster-{p}-{r}-{s}/controlPlane"
                        ))
                    
                    machines.append(edgecontainer.Machine(
                            name=f"machine{z}03", zone=f"zone{z}", hosted_node=f"projects/project-{p}/locations/region-{r}/clusters/cluster-{p}-{r}-{s}/controlPlane"
                        ))
                    
                    time.sleep(delay_seconds_per_zone)

        return iter(machines)

    return list_machines

def generate_list_clusters_function(delay_seconds_per_cluster, number_of_projects, number_of_regions_within_project, number_of_zones_within_region):
    def list_machines(list_clusters_req):
        project = list_clusters_req.parent.split("/")[1]
        region = list_clusters_req.parent.split("/")[3]

        clusters = []

        z = 0

        for p in range(number_of_projects):
            for r in range(number_of_regions_within_project):
                for s in range(number_of_zones_within_region):
                    z += 1

                    if (project != f"project-{p}" or region != f"region-{r}"):
                        continue

                    clusters.append(edgecontainer.Cluster(
                            name=f"machine{z}01", control_plane=edgecontainer.Cluster.ControlPlane(
                                local=edgecontainer.Cluster.ControlPlane.Local(
                                    node_location=f"zone{z}"
                                )
                            )
                        ))
                    
                    time.sleep(delay_seconds_per_cluster)

        return iter(clusters)

    return list_machines

def generate_get_zone_function(delay_seconds):
    def get_zone(zone_id):
        time.sleep(delay_seconds)

        # zone_id = projects/project-0/locations/region-0/zones/store1
        store_number = zone_id.split("/")[-1][5:]

        zone = Zone()

        zone.state = "ACTIVE"
        zone.globally_unique_id = f"zone{store_number}"

        return zone
    
    return get_zone