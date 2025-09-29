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

from typing import Dict, Tuple
import functions_framework
import os
import io
import flask
from collections import defaultdict
import csv
import logging
from google.api_core.operation import Operation
from pydantic import ValidationError
import requests
import google_crc32c
from requests.structures import CaseInsensitiveDict
from urllib.parse import urlparse
from google.api_core import exceptions
import google.auth
from google.cloud import edgecontainer
from google.cloud import edgenetwork
from google.cloud import gdchardwaremanagement_v1alpha
from google.cloud.gdchardwaremanagement_v1alpha import Zone, SignalZoneStateRequest
from google.cloud.devtools import cloudbuild
from google.cloud import monitoring_v3
from google.protobuf.timestamp_pb2 import Timestamp
from dateutil.parser import parse
from .maintenance_windows import MaintenanceExclusionWindow
from .build_history import BuildHistory
from .acp_zone import ACPZone, get_zones
from .acp_membership import get_memberships
from .clients import GoogleClients
from .cluster_intent_model import SourceOfTruthModel
from .watcher_settings import WatcherSettings
import concurrent.futures
import threading
import time

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

creds, auth_project = google.auth.default()

clients = GoogleClients()


def _zone_watcher_worker(
    machine_project: str,
    location: str,
    stores: Dict[Tuple, Dict[str, SourceOfTruthModel]],
    params: WatcherSettings,
    builds: BuildHistory,
    machine_lists: Dict[str, list[edgecontainer.Machine]],
    unprocessed_zones,
    unprocessed_zones_lock,
) -> int:
    thread_start_time = time.perf_counter()

    cb_client = clients.get_cloudbuild_client()
    count = 0

    zones = get_zones(machine_project, location)

    for store_id in stores:
        store_info = stores[store_id]

        zone_store_id = f'projects/{machine_project}/locations/{location}/zones/{store_id}'

        try:
            if store_info.zone_name:
                zone = store_info.zone_name
                zone_name_retrieved_from_api = False
            else:
                zone = zones[zone_store_id].globally_unique_id
                zone_name_retrieved_from_api = True
        except Exception:
            logger.error(f'Zone for store {store_id} cannot be found, skipping.')
            continue

        try:                                       
            if not zone_name_retrieved_from_api:
                logger.info(f'Zone name was provided directly in cluster intent for store: {store_id}. Skipping intent verification.')
            elif zones[zone_store_id].cluster_intent_verified:
                logger.info(f'Cluster intent is present and verification has already been set for Store: {store_id}. Skipping..')
            else:
                logger.info(f'Cluster intent is present but verification is not set on Store: {store_id}. Setting cluster intent verification.')
                operation = set_zone_state_verify_cluster_intent(zone_store_id)
                logger.info(f'HW API Operation: {operation.operation.name}')
        except Exception:
            logger.error(
                f'Cluster intent could not be checked for Store: {store_id}. Skipping',
                exc_info=True,
            )

        
        if zone not in machine_lists:
            logger.warning(f'No machine found in zone {zone}')
            continue

        count_of_free_machines = 0
        cluster_exists = False
        with unprocessed_zones_lock:
            if zone in unprocessed_zones:
                unprocessed_zones.pop(zone)
        for m in machine_lists[zone]:
            if len(m.hosted_node.strip()) > 0:  # if there is any value, consider there is a cluster
                # check if target cluster already exists
                if (m.hosted_node.split('/')[5] == store_info.cluster_name):
                    cluster_exists = True
                    break

                logger.info(f'ZONE {zone}: {m.name} already used by {m.hosted_node}')
            else:
                logger.info(f'ZONE {zone}: {m.name} is a free node')
                count_of_free_machines = count_of_free_machines+1

        if cluster_exists and not builds.should_retry_zone_build(zone):
            logger.info(f'Cluster already exists for {zone}. Skipping..')
            continue

        if count_of_free_machines >= int(store_info.node_count):
            logger.info(f'ZONE {zone}: There are enough free  nodes to create cluster')
        else:
            logger.info(f'ZONE {zone}: Not enough free  nodes to create cluster. Need {str(store_info.node_count)} but have {str(count_of_free_machines)} free nodes')
            if not builds.should_retry_zone_build(zone):
                continue

        if zone_name_retrieved_from_api and not verify_zone_state(zones[zone_store_id].state ,zone_store_id, store_info.recreate_on_delete):
            logger.info(f'Zone: {zone}, Store: {store_id} is not in expected state! skipping..')
            continue

        # trigger cloudbuild to initiate the cluster building
        repo_source = cloudbuild.RepoSource()
        repo_source.branch_name = store_info.sync_branch
        repo_source.substitutions = {
            "_STORE_ID": store_id,
            "_ZONE": zone
        }
        req = cloudbuild.RunBuildTriggerRequest(
            name=params.cloud_build_trigger,
            source=repo_source
        )
        logger.debug(req)
        try:
            logger.info(f'triggering cloud build for {zone}')
            logger.info(f'trigger: {params.cloud_build_trigger}')
            cb_client.run_build_trigger(request=req)
            count += 1
            # response = opr.result()
        except Exception as err:
            logger.error(err)

    thread_end_time = time.perf_counter()
    logger.info(f"Thread zone_watcher({machine_project}, {location}) took {thread_end_time - thread_start_time:0.2f} seconds)")

    return count

@functions_framework.http
def zone_watcher(req: flask.Request):
    params = WatcherSettings()

    logger.info(f'Running zone watcher for: proj_id={params.project_id},sot={params.source_of_truth_repo}/{params.source_of_truth_branch}/{params.source_of_truth_path}, cb_trigger={params.cloud_build_trigger}')
    
    config_zone_info = read_intent_data(params, 'machine_project_id')
    
    ec_client = clients.get_edgecontainer_client()
    builds = BuildHistory(params.project_id, params.region, params.max_retries, params.cloud_build_trigger_name)

    machine_lists: Dict[str, list[edgecontainer.Machine]] = {}
    unprocessed_zones: Dict[str, Tuple] = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=params.max_workers) as executor:
        machine_futures = {
            executor.submit(
                ec_client.list_machines,
                edgecontainer.ListMachinesRequest(
                    parent=ec_client.common_location_path(machine_project, location)
                ),
            ): (machine_project, location)
            for (machine_project, location) in config_zone_info
        }
        for future in concurrent.futures.as_completed(machine_futures):
            machine_project, location = machine_futures[future]
            try:
                res_pager = future.result()
                for m in res_pager:
                    if m.zone not in machine_lists:
                        machine_lists[m.zone] = [m]
                        unprocessed_zones[m.zone] = (machine_project, location)
                    else:
                        machine_lists[m.zone].append(m)
            except Exception as err:
                logger.error(f"Error listing machines for project: {machine_project}, location: {location}")
                logger.error(err)

    count = 0
    unprocessed_zones_lock = threading.Lock()
    with concurrent.futures.ThreadPoolExecutor(max_workers=params.max_workers) as executor:
        watcher_futures = []
        for (machine_project, location), stores in config_zone_info.items():
            future = executor.submit(_zone_watcher_worker, machine_project, location, stores, params, builds, machine_lists, unprocessed_zones, unprocessed_zones_lock)
            watcher_futures.append(future)
        
        for future in concurrent.futures.as_completed(watcher_futures):
            count += future.result()

    logger.info(f'total zones triggered = {count}')

    for zone, (machine_project, location) in unprocessed_zones.items():
        logger.info(f'Zone found in environment but not in cluster source of truth. "projects/{machine_project}/locations/{location}/zones/{zone}"')

    return f'total zones triggered = {count}'

def _cluster_watcher_worker(
    project_id: str,
    location: str,
    stores: Dict[str, SourceOfTruthModel],
    params: WatcherSettings,
) -> int:
    ec_client = clients.get_edgecontainer_client()
    en_client = clients.get_edgenetwork_client()
    cb_client = clients.get_cloudbuild_client()
    count = 0

    zones = get_zones(project_id, location)
    memberships = get_memberships(project_id, location)

    req_c = edgecontainer.ListClustersRequest(
        parent=ec_client.common_location_path(project_id, location)
    )
    
    try:
        res_pager_c = ec_client.list_clusters(req_c)
        clusters_by_zone: Dict[str, list[edgecontainer.Cluster]] = defaultdict(list)
        for c in res_pager_c:
            clusters_by_zone[c.control_plane.local.node_location].append(c)
    except Exception as err:
        logger.error(f"Error listing clusters for project: {project_id}, location: {location}")
        logger.error(err)
        return 0

    for store_id in stores:
        store_info = stores[store_id]

        machine_project_id = store_info.machine_project_id
        zone_store_id = f'projects/{machine_project_id}/locations/{location}/zones/{store_id}'
        try:
            if store_info.zone_name:
                zone = store_info.zone_name
            else:
                zone = zones[zone_store_id].globally_unique_id
        except Exception:
            logger.error(f'Zone for store {store_id} cannot be found, skipping.')
            continue

        zone_cluster_list = clusters_by_zone[zone]
        if len(zone_cluster_list) == 0:
            logger.warning(f'No lcp cluster found in {zone}')
            continue
        elif len(zone_cluster_list) > 1:
            logger.warning(f'More than 1 lcp clusters found in {zone}')
        logger.debug(zone_cluster_list)

        cluster = zone_cluster_list[0]
        rw = cluster.maintenance_policy.window.recurring_window
        has_update = False

        if (not store_info.maintenance_window_recurrence or
            not store_info.maintenance_window_start or
            not store_info.maintenance_window_end
            ):
            has_update = False
        elif (rw.recurrence != store_info.maintenance_window_recurrence or
                rw.window.start_time != parse(store_info.maintenance_window_start) or
                rw.window.end_time != parse(store_info.maintenance_window_end)):
            logger.info("Maintenance window requires update")
            logger.info(f"Actual values (recurrence={rw.recurrence}, start_time={rw.window.start_time}, end_time={rw.window.end_time})")
            logger.info(f"Desired values (recurrence={store_info.maintenance_window_recurrence}, start_time={store_info.maintenance_window_start}, end_time={store_info.maintenance_window_end})")
            has_update = True
        else:
            defined_exclusion_windows = MaintenanceExclusionWindow.get_exclusion_windows_from_sot(store_info)
            actual_exclusion_windows = MaintenanceExclusionWindow.get_exclusion_windows_from_cluster_response(cluster)
            if defined_exclusion_windows != actual_exclusion_windows:
                has_update = True

        req_n = edgenetwork.ListSubnetsRequest(
            parent=f'{en_client.common_location_path(store_info.machine_project_id, location)}/zones/{zone}'
        )

        try:
            res_pager_n = en_client.list_subnets(req_n)
            subnet_list = [{'vlan_id': net.vlan_id, 'ipv4_cidr': sorted(net.ipv4_cidr)} for net in res_pager_n]
        except Exception as err:
            logger.error(f"Error listing subnets for project: {project_id}, location: {location}, zone: {zone}")
            logger.error(err)
            continue
            
        subnet_list.sort(key=lambda x: x['vlan_id'])
        logger.debug(subnet_list)
        try:
            for desired_subnet in store_info.subnet_vlans.split(','):
                try:
                    vlan_id = int(desired_subnet)
                except Exception as err:
                    logger.error("unable to convert vlan to an int", err)

                if vlan_id not in [n['vlan_id'] for n in subnet_list]:
                    logger.info(f"No vlan created for vlan: {vlan_id}")
                    has_update = True

            for actual_vlan_id in [n['vlan_id'] for n in subnet_list]:
                if actual_vlan_id not in [int(v) for v in store_info.subnet_vlans.split(',')]:
                    logger.error(f"VLAN {actual_vlan_id} is defined in the environment, but not in the source of truth. The subnet will need to be manually deleted from the environment.")
        except Exception as err:
            logger.error(err)

        cluster_name = store_info.cluster_name
        if store_info.labels:
            labels = store_info.labels.strip()
        else:
            labels = ""

        if labels:
            desired_labels = {}
            for label in labels.split(","):
                kv_pair = label.split("=")
                desired_labels[kv_pair[0]] = kv_pair[1]

            membership = memberships[f"projects/{project_id}/locations/global/memberships/{cluster_name}"]

            membership_labels = membership.labels
            if (desired_labels != membership_labels):
                has_update = True

        if not has_update:
            continue

        repo_source = cloudbuild.RepoSource()
        repo_source.branch_name = store_info.sync_branch
        repo_source.substitutions = {
            "_STORE_ID": store_id,
            "_ZONE": zone
        }
        req = cloudbuild.RunBuildTriggerRequest(
            name=params.cloud_build_trigger,
            source=repo_source
        )
        logger.debug(req)
        try:
            logger.info(f'triggering cloud build for {zone}')
            logger.info(f'trigger: {params.cloud_build_trigger}')
            cb_client.run_build_trigger(request=req)
            count += 1
        except Exception as err:
            logger.error(f'failed to trigger cloud build for {zone}')
            logger.error(err)
            continue
    return count

@functions_framework.http
def cluster_watcher(req: flask.Request):
    params = WatcherSettings()

    logger.info(f'proj_id = {params.project_id}')
    logger.info(f'cb_trigger = {params.cloud_build_trigger}')

    config_zone_info = read_intent_data(params, 'fleet_project_id')
    count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=params.max_workers) as executor:
        futures = []
        for (project_id, location), stores in config_zone_info.items():
            future = executor.submit(_cluster_watcher_worker, project_id, location, stores, params)
            futures.append(future)
        
        for future in concurrent.futures.as_completed(futures):
            count += future.result()

    return f'total zones triggered = {count}'


@functions_framework.http
def zone_active_metric(req: flask.Request):
    params = WatcherSettings()

    logger.info(
        f'Running zone active watcher in: proj_id={params.project_id}, sot={params.source_of_truth_repo}/{params.source_of_truth_branch}/{params.source_of_truth_path}')

    token = get_git_token_from_secrets_manager(params.secrets_project_id, params.git_secret_id)
    intent_reader = ClusterIntentReader(
        params.source_of_truth_repo, params.source_of_truth_branch,
        params.source_of_truth_path, token)
    zone_config_fio = intent_reader.retrieve_source_of_truth()
    rdr = csv.DictReader(io.StringIO(zone_config_fio))  # will raise exception if csv parsing fails

    time_series_data = []
    zones: Dict[str, ACPZone] = {}
    zones_project_locations_checked = set()

    for row in rdr:
        f_proj_id = row['fleet_project_id']
        m_proj_id = f_proj_id if row['machine_project_id'] is None or len(row['machine_project_id']) == 0 else row['machine_project_id']
        loc = params.region if row['location'] is None or len(row['location']) == 0 else row['location']
        store_id = row['store_id']
        cl_name = row['cluster_name']
        b_generate_metric = False
        b_zone_found = False
        active_metric = 0  # 0 - inactive, 1 - active
        if (m_proj_id, loc) not in zones_project_locations_checked:
            zones.update(get_zones(m_proj_id, loc))
            zones_project_locations_checked.add((m_proj_id, loc))   

        try:
            zone = zones[store_id]
            logger.debug(f'{store_id} state = {Zone.State(zone.state).name}')
            b_zone_found = True
        except Exception as e:
            logger.debug(f'get_zone({store_id}) -> {type(e)}', exc_info=False)
            if isinstance(e, exceptions.ServerError):
                # if ServerError (API failure), treat zone as active and not to filter any alerts
                # any exception other than hw mgmt API failure, such as ClientError or generic exception
                # treat as non-existing zone (don't generate metric)
                b_generate_metric = True
                active_metric = 1

        if b_zone_found and zone.globally_unique_id is not None and len(zone.globally_unique_id.strip()) > 0:
            # only zones with globally_unique_id is considering as existing zones(generate metric)
            gdce_zone_name = zone.globally_unique_id.strip()
            b_generate_metric = True
            if zone.state == Zone.State.ACTIVE:
                active_metric = 1

        if not b_generate_metric:
            continue

        # Construct time series datapoints for each store
        timestamp = Timestamp()
        timestamp.GetCurrentTime()
        data_point = {
            'interval': {'end_time': timestamp},
            'value': {'int64_value': active_metric}
        }
        time_series_point = {
            'metric': {
                'type': 'custom.googleapis.com/gdc_zone_active',
                'labels': {
                    'fleet_project_id': f_proj_id,
                    'machine_project_id': m_proj_id,
                    'location': loc,
                    'store_id': store_id,
                    'zone_name': gdce_zone_name,
                    'cluster_name': cl_name,
                    'cluster': cl_name
                }
            },
            'resource': {
                'type': 'global',
                'labels': {
                    'project_id': f_proj_id
                }
            },
            'points': [data_point]
        }
        time_series_data.append(time_series_point)

    # send batch requests to metric
    m_client = clients.get_monitoring_client()
    batch_size = 200
    for i in range(0, len(time_series_data), batch_size):
        request = monitoring_v3.CreateTimeSeriesRequest({
            'name': f'projects/{params.project_id}',
            'time_series': time_series_data[i:i + batch_size]
        })
        m_client.create_time_series(request)

    logger.debug(f'update datapoint for {[x["metric"]["labels"]["store_id"] for x in time_series_data]}')
    logger.debug(f'total zone active flag updated = {len(time_series_data)}')
    return f'total zone active flag updated = {len(time_series_data)}'

def read_intent_data(params, named_key) -> Dict[Tuple, Dict[str, SourceOfTruthModel]]:
    """Returns a data structure containing project, location, and store information  

    For example:
    {
        ('project1', 'us-central1'): {'storeid': {'cluster_name': 'cluster1', 'cluster_ipv4_cidr', '192.168.1.1/24'}},
        ('project2', 'us-east4'): {'storeid': {'cluster_name': 'cluster2', 'cluster_ipv4_cidr', '192.168.2.1/24'}}
    }

    store_information matches the cluster intent's source of truth. Please reference the example-source-of-truth.csv
    file for more information. 

    Args:
        params: WatcherParams
        named_key: either 'fleet_project_id' or 'machine_project_id'
    Returns:
        A dictionary with the structure described above.
    """

    config_zone_info = {}
    token = get_git_token_from_secrets_manager(params.secrets_project_id, params.git_secret_id)
    intent_reader = ClusterIntentReader(params.source_of_truth_repo, params.source_of_truth_branch, params.source_of_truth_path, token)
    zone_config_fio = intent_reader.retrieve_source_of_truth()
    rdr = csv.DictReader(io.StringIO(zone_config_fio))  # will raise exception if csv parsing fails
    
    for row in rdr:
        proj_loc_key = (row[named_key], row['location'])

        if proj_loc_key not in config_zone_info.keys():
            config_zone_info[proj_loc_key] = {}

        try:
            edge_zone = SourceOfTruthModel.model_validate(row)
        except ValidationError as e:
            logger.error(f"Invalid row detected in source of truth: {e.errors()}")
            continue

        config_zone_info[proj_loc_key][row['store_id']] = edge_zone
    for key in config_zone_info:
        logger.debug(f'Stores to check in {key[0]}, {key[1]} => {len(config_zone_info[proj_loc_key])}')
    if len(config_zone_info) == 0:
        raise Exception('no valid zone listed in config file')
    
    return config_zone_info

def set_zone_state_verify_cluster_intent(store_id: str) -> Operation:
    '''Return Zone info.
    Args:
      store_id: name of zone which is store id usually
    '''
    client = clients.get_hardware_management_client()

    request = gdchardwaremanagement_v1alpha.SignalZoneStateRequest(
        name=store_id,
        state_signal=SignalZoneStateRequest.StateSignal.VERIFY_CLUSTER_INTENT_PRESENCE,
    )
    return client.signal_zone_state(request=request)


def verify_zone_state(state: Zone.State,store_id: str, recreate_on_delete: bool) -> bool:
    """Checks if zone is in right state to create.
    Args:
        store_id: name of zone which is store id usually
        recreate_on_delete: true if cluster needs to be recreated on delete.
    Returns:
        if cluster can be created or not
    """
    # READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS, provisioning has not yet been attempted
    # CUSTOMER_FACTORY_TURNUP_CHECKS_STARTED, provisioning has been attempted and is either in progress or failed
    if state == Zone.State.READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS or state == Zone.State.CUSTOMER_FACTORY_TURNUP_CHECKS_STARTED :
        logger.info(f'Store is ready for provisioning: "{store_id}"')
        return True

    if state == Zone.State.ACTIVE and recreate_on_delete:
        logger.info(f'Store: {store_id} was already setup, but specified to recreate on delete!')
        return True
    
    return False

class ClusterIntentReader:
    def __init__(self, repo, branch, sourceOfTruth, token):
        self.repo = repo
        self.branch = branch
        self.sourceOfTruth = sourceOfTruth
        self.token = token

    def retrieve_source_of_truth(self):
        url = self._get_url()

        resp = requests.get(url, headers=self._get_headers())

        if resp.status_code == 200:
            return resp.text
        else:
            raise Exception(f"Unable to retrieve source of truth with status code ({resp.status_code})")

    def _get_url(self):
        parse_result = urlparse(f"https://{self.repo}")

        if parse_result.netloc == "github.com":
            # Remove .git suffix used in git web url
            path = parse_result.path.split('.')[0]

            return f"https://raw.githubusercontent.com{path}/{self.branch}/{self.sourceOfTruth}"
        elif parse_result.netloc == "gitlab.com":
            path = parse_result.path.split('.')[0]

            # projectid is url encoded: org%2Fproject%2Frepo_name
            project_id = path[1:].replace('/', '%2F')

            return f"https://gitlab.com/api/v4/projects/{project_id}/repository/files/{self.sourceOfTruth}/raw?ref={self.branch}&private_token={self.token}"
        else:
            raise Exception("Unsupported git provider")

    def _get_headers(self):
        headers = CaseInsensitiveDict()

        parse_result = urlparse(f"https://{self.repo}")

        if parse_result.netloc == "github.com":
            headers["Authorization"] = f"token {self.token}"
            return headers
        elif parse_result.netloc == "gitlab.com":
            return headers
        else:
            raise Exception("Unsupported git provider")


def get_git_token_from_secrets_manager(secrets_project_id, secret_id, version_id="latest"):
    client = clients.get_secret_manager_client()

    name = f"projects/{secrets_project_id}/secrets/{secret_id}/versions/{version_id}"

    response = client.access_secret_version(request={"name": name})

    crc32c = google_crc32c.Checksum()
    crc32c.update(response.payload.data)
    if response.payload.data_crc32c != int(crc32c.hexdigest(), 16):
        raise Exception("Data corruption detected.")

    return response.payload.data.decode("UTF-8")