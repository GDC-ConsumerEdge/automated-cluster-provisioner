import unittest
from unittest.mock import patch, MagicMock
from src.clients import GoogleClients

class TestGoogleClients(unittest.TestCase):

    @patch('src.clients.edgecontainer.EdgeContainerClient')
    @patch('src.clients.edgenetwork.EdgeNetworkClient')
    @patch('src.clients.gkehub_v1.GkeHubClient')
    @patch('src.clients.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient')
    @patch('src.clients.secretmanager.SecretManagerServiceClient')
    @patch('src.clients.cloudbuild.CloudBuildClient')
    @patch('src.clients.monitoring_v3.MetricServiceClient')
    def test_client_initialization(self, mock_monitoring, mock_cloudbuild, mock_secretmanager, mock_hw_mgmt, mock_gkehub, mock_edgenetwork, mock_edgecontainer):
        clients = GoogleClients()
        self.assertIsNotNone(clients.get_edgecontainer_client())
        self.assertIsNotNone(clients.get_edgenetwork_client())
        self.assertIsNotNone(clients.get_gkehub_client())
        self.assertIsNotNone(clients.get_hardware_management_client())
        self.assertIsNotNone(clients.get_secret_manager_client())
        self.assertIsNotNone(clients.get_cloudbuild_client())
        self.assertIsNotNone(clients.get_monitoring_client())