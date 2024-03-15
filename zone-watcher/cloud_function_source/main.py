import functions_framework
import sys
import os
import io
import flask
import csv
import logging
from google.api_core import client_options
from google.cloud import edgecontainer
from google.cloud import storage
from google.cloud.devtools import cloudbuild


@functions_framework.http
def zone_watcher(req: flask.Request):

    if req:  # for on-cloud test, where request is not None

        request_json = req.get_json(silent=True, force=True)  # ignor the content type and force parse to json
        if not request_json:
            raise Exception('Invalid json request body')

        if 'projectid' not in request_json:
            raise Exception('missing projectid, (gcs csv file project)')
        if 'config-csv' not in request_json:
            raise Exception('missing config-csv (gs://<bucket_name/<csv_file_path>>)')
        if 'cb-trigger' not in request_json:
            raise Exception('missing cb-trigger (projects/<project-id>/locations/<location>/triggers/<trigger-name>)')

        proj_id = request_json['projectid']  # This is the project id of where the csv file located
        os.environ['GOOGLE_CLOUD_PROJECT'] = proj_id
        gcs_config_uri = request_json['config-csv']
        # format: projects/<project-id>/locations/<location>/triggers/<trigger-name>
        # e.g. projects/daniel-test-proj-411311/locations/us-central1/triggers/test-trigger
        # location could be "global"
        cb_trigger = request_json['cb-trigger']
        run_environment = 'STAGING' if 'env' in request_json and request_json['env'].upper() == 'STAGING' else 'PROD'
        log_lvl = logging.DEBUG if 'debug' in request_json and request_json['debug'] else logging.INFO

    else:
        # mock up: for off-cloud test run
        proj_id = 'gmec-developers-1'
        run_environment = 'PROD'
        gcs_config_uri = 'gs://gdce-cluster-provisioner-bucket/cluster-intent-registry.csv'
        cb_trigger = 'projects/daniel-test-proj-411311/locations/us-central1/triggers/test-trigger'
        log_lvl = logging.DEBUG

    # set log level, default is INFO, unless has {debug: true} in request
    logger = logging.getLogger()
    logging.basicConfig(stream=sys.stdout, level=log_lvl)

    logger.info(f'proj_id = {proj_id}')
    logger.info(f'run_environment = {run_environment}')
    logger.info(f'gcs_config_uri = {gcs_config_uri}')
    logger.info(f'cb_trigger = {cb_trigger}')
    logger.debug(f'log_lvl = {log_lvl}')

    # Get the CSV file from GCS containing target zones
    # NODE_LOCATION	MACHINE_PROJECT_ID	FLEET_PROJECT_ID	CLUSTER_NAME	LOCATION	NODE_COUNT	EXTERNAL_LOAD_BALANCER_IPV4_ADDRESS_POOLS	SYNC_REPO	SYNC_BRANCH	SYNC_DIR	GIT_TOKEN_SECRETS_MANAGER_NAME
    # us-central1-edge-den25349	cloud-alchemist-machines	gmec-developers-1	lcp-den29	us-central1	1	172.17.34.96-172.17.34.100	https://gitlab.com/gcp-solutions-public/retail-edge/gdce-shyguy-internal/primary-root-repo	main	/config/clusters/den29/meta	shyguy-internal-pat
    config_zone_info = {}
    sto_client = storage.Client(project=proj_id)
    blob = storage.Blob.from_string(uri=gcs_config_uri, client=sto_client)
    zone_config_fio = io.StringIO(blob.download_as_bytes().decode())  # download the content to memory
    rdr = csv.DictReader(zone_config_fio)  # will raise exception if csv parsing fails
    for row in rdr:
        if row['LOCATION'] not in config_zone_info.keys():
            config_zone_info[row['LOCATION']] = {}
        config_zone_info[row['LOCATION']][row['NODE_LOCATION']] = row
    for loc in config_zone_info:
        logger.debug(f'Zones to check in {loc} => {len(config_zone_info[loc])}')
    assert len(config_zone_info) > 0, 'no valid zone listed in config file'

    # for edge container API, we will use staging environment for develop and testing.
    # for real customer, it should always be prod environment
    # for other APIs, such as storage and cloud build, always using prod environment
    if run_environment == 'STAGING':  # override with staging endpoint
        op = client_options.ClientOptions(api_endpoint='staging-edgecontainer.sandbox.googleapis.com')
        ec_client = edgecontainer.EdgeContainerClient(client_options=op)
    else:  # use the default prod endpoint
        ec_client = edgecontainer.EdgeContainerClient()

    cb_client = cloudbuild.CloudBuildClient()

    # if cluster already present in the zone, skip this zone
    # method: get all the machines in the zone, and check if "hosted_node" has any value in it
    count = 0
    for loc in config_zone_info:
        for z in config_zone_info[loc]:
            has_cluster = False
            req = edgecontainer.ListMachinesRequest(
                parent=ec_client.common_location_path(config_zone_info[loc][z]['MACHINE_PROJECT_ID'], loc)
            )
            res_pager = ec_client.list_machines(req)
            res_list = [res for res in res_pager]
            for res in res_list:
                if len(res.hosted_node.strip()) > 0:  # if there is any value, consider there is a cluster
                    logger.info(f'ZONE {z}: {res.name} already used by {res.hosted_node}')
                    has_cluster = True
                    break
            if has_cluster:
                continue
            # trigger cloudbuild to initiate the cluster building
            repo_source = cloudbuild.RepoSource()
            repo_source.branch_name = config_zone_info[loc][z]['SYNC_BRANCH']
            repo_source.substitutions = {
                "_NODE_LOCATION": z
            }
            req = cloudbuild.RunBuildTriggerRequest(
                name=cb_trigger,
                source=repo_source
            )
            logger.debug(req)
            try:
                logger.info(f'triggering cloud build for {z}')
                logger.info(f'trigger: {cb_trigger}')
                opr = cb_client.run_build_trigger(request=req)
                # response = opr.result()
            except Exception as err:
                logger.error(err)

            count += len(config_zone_info[loc])

    return f'total zones triggered = {count}'
