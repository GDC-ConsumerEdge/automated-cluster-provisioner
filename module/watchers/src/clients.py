import os
from google.api_core import client_options
import google.auth
from google.cloud import (
    edgecontainer,
    edgenetwork,
    gdchardwaremanagement_v1alpha,
    gkehub_v1,
    monitoring_v3,
    secretmanager,
)
from google.cloud.devtools import cloudbuild
from urllib.parse import urlparse

creds, auth_project = google.auth.default()

class GoogleClients:
    def __init__(self) -> None:
        edgecontainer_api_endpoint_override = os.environ.get("EDGE_CONTAINER_API_ENDPOINT_OVERRIDE")
        edgenetwork_api_endpoint_override = os.environ.get("EDGE_NETWORK_API_ENDPOINT_OVERRIDE")
        gkehub_api_endpoint_override = os.environ.get("GKEHUB_API_ENDPOINT_OVERRIDE")
        hardware_management_api_endpoint_override = os.environ.get("HARDWARE_MANAGEMENT_API_ENDPOINT_OVERRIDE")

        if edgecontainer_api_endpoint_override:
            op = client_options.ClientOptions(api_endpoint=urlparse(edgecontainer_api_endpoint_override).netloc)
            self.ec_client = edgecontainer.EdgeContainerClient(client_options=op)
        else:  # use the default prod endpoint
            self.ec_client = edgecontainer.EdgeContainerClient()

        if edgenetwork_api_endpoint_override:
            op = client_options.ClientOptions(api_endpoint=urlparse(edgenetwork_api_endpoint_override).netloc)
            self.en_client = edgenetwork.EdgeNetworkClient(client_options=op)
        else:  # use the default prod endpoint
            self.en_client = edgenetwork.EdgeNetworkClient()

        if gkehub_api_endpoint_override:
            op = client_options.ClientOptions(api_endpoint=urlparse(gkehub_api_endpoint_override).netloc)
            self.gkehub_client = gkehub_v1.GkeHubClient(client_options=op)
        else:  # use the default prod endpoint
            self.gkehub_client = gkehub_v1.GkeHubClient()

        if hardware_management_api_endpoint_override:
            op = client_options.ClientOptions(api_endpoint=urlparse(hardware_management_api_endpoint_override).netloc)
            self.hw_mgmt_client = gdchardwaremanagement_v1alpha.GDCHardwareManagementClient(client_options=op)
        else:
            self.hw_mgmt_client = gdchardwaremanagement_v1alpha.GDCHardwareManagementClient()

        self.secret_manager_client = secretmanager.SecretManagerServiceClient()
        self.cb_client = cloudbuild.CloudBuildClient()
        self.monitoring_client = monitoring_v3.MetricServiceClient()

    def get_edgecontainer_client(self) -> edgecontainer.EdgeContainerClient:
        return self.ec_client

    def get_edgenetwork_client(self) -> edgenetwork.EdgeNetworkClient:
        return self.en_client

    def get_gkehub_client(self) -> gkehub_v1.GkeHubClient:
        return self.gkehub_client

    def get_hardware_management_client(self) -> gdchardwaremanagement_v1alpha.GDCHardwareManagementClient:
        return self.hw_mgmt_client

    def get_secret_manager_client(self) -> secretmanager.SecretManagerServiceClient:
        return self.secret_manager_client

    def get_cloudbuild_client(self) -> cloudbuild.CloudBuildClient:
        return self.cb_client
    
    def get_monitoring_client(self) -> monitoring_v3.MetricServiceClient:
        return self.monitoring_client