import os
import sys
import unittest
import json
from unittest.mock import MagicMock, patch


# Add src to path so we can import main
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

# Mock external dependencies that might be missing in the environment
# We still need this because the imports in main.py would fail otherwise
sys.modules['functions_framework'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.gdchardwaremanagement_v1alpha'] = MagicMock()
sys.modules['google.cloud.firestore'] = MagicMock()
sys.modules['google.cloud.pubsub_v1'] = MagicMock()
sys.modules['google.api_core'] = MagicMock()
sys.modules['google.api_core.client_options'] = MagicMock()

sys.modules['google'] = MagicMock()
sys.modules['google.auth'] = MagicMock()
sys.modules['google'].auth = sys.modules['google.auth']
sys.modules['google.auth'].default.return_value = (None, "test-project")

# Pass-through decorator for functions_framework.http
def identity(f):
    return f
sys.modules['functions_framework'].http.side_effect = identity

import main

class FakeZone:
    def __init__(self, name, state):
        self.name = name
        self.state = state

class FakeHwmClient:
    def __init__(self, zones=None):
        self.zones = zones or []

    def list_zones(self, request):
        return self.zones

class FakeSnapshot:
    def __init__(self, data=None, exists=False):
        self._data = data
        self._exists = exists

    @property
    def exists(self):
        return self._exists

    def to_dict(self):
        return self._data

class FakeDocument:
    def __init__(self, doc_id, data=None):
        self.id = doc_id
        self.data = data # Current state in DB

    def get(self):
        return FakeSnapshot(data=self.data, exists=self.data is not None)

    def set(self, data):
        self.data = data

class FakeCollection:
    def __init__(self):
        self.docs = {} # id -> FakeDocument

    def document(self, doc_id):
        if doc_id not in self.docs:
            self.docs[doc_id] = FakeDocument(doc_id)
        return self.docs[doc_id]

class FakeFirestore:
    def __init__(self, project=None, database=None):
        self.collections = {} # name -> FakeCollection

    def collection(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]

class FakeFuture:
    def result(self):
        return "msg-id"

class FakePublisher:
    def __init__(self):
        self.published_messages = [] # list of (topic, data, kwargs)

    def topic_path(self, project, topic):
        return f"projects/{project}/topics/{topic}"

    def publish(self, topic, data, **kwargs):
        self.published_messages.append({
            "topic": topic,
            "data": json.loads(data.decode('utf-8')),
            "attributes": kwargs
        })
        return FakeFuture()

class TestHwmEvents(unittest.TestCase):

    def setUp(self):
        self.hwm_client = FakeHwmClient()
        self.db = FakeFirestore()
        self.publisher = FakePublisher()
        self.project_id = "test-project"
        self.region = "us-central1"
        self.topic = "test-topic"

    def test_poll_zones_state_change(self):
        zone_name = "projects/test-project/locations/us-central1/zones/zone-1"
        self.hwm_client.zones = [FakeZone(name=zone_name, state=1)] # 1 = int for state

        db_doc_id = zone_name.replace("/", "_")
        self.db.collection("zone_states").document(db_doc_id).set({"state": "PREPARING"})

        # Mock Enum lookup (dependent on external lib structure, we mock it via patch here for the test helper)
        with patch('main.gdchardwaremanagement_v1alpha') as mock_gdc:
            mock_gdc.Zone.State.return_value.name = "READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS"
            
            main.poll_zones(
                self.hwm_client,
                self.db,
                self.publisher,
                host_project_id=self.project_id,
                target_project_id=self.project_id,
                region=self.region,
                topic=self.topic
            )

        updated_doc = self.db.collection("zone_states").document(db_doc_id)
        self.assertEqual(updated_doc.data["state"], "READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS")
        self.assertIsNotNone(updated_doc.data["last_updated"])

        self.assertEqual(len(self.publisher.published_messages), 1)
        msg = self.publisher.published_messages[0]
        self.assertEqual(msg["data"]["zone"], zone_name)
        self.assertEqual(msg["data"]["current_state"], "READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS")
        self.assertEqual(msg["data"]["previous_state"], "PREPARING")
        self.assertEqual(msg["topic"], f"projects/{self.project_id}/topics/{self.topic}")

    def test_poll_zones_no_change(self):
        zone_name = "zone-1"
        self.hwm_client.zones = [FakeZone(name=zone_name, state=1)]
        
        db_doc_id = zone_name.replace("/", "_")
        self.db.collection("zone_states").document(db_doc_id).set({"state": "READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS"})

        with patch('main.gdchardwaremanagement_v1alpha') as mock_gdc:
            mock_gdc.Zone.State.return_value.name = "READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS"

            main.poll_zones(
                self.hwm_client,
                self.db,
                self.publisher,
                host_project_id=self.project_id,
                target_project_id=self.project_id,
                region=self.region,
                topic=self.topic
            )

        self.assertEqual(len(self.publisher.published_messages), 0)

    def test_poll_zones_partial_failure(self):
        # Setup: Two zones.
        zone1_name = "projects/p/l/r/zones/z1"
        zone2_name = "projects/p/l/r/zones/z2"
        
        self.hwm_client.zones = [
            FakeZone(name=zone1_name, state=1),
            FakeZone(name=zone2_name, state=1)
        ]
        
        # Inject failure for the first zone (z1)
        original_document = self.db.collection("zone_states").document
        
        def side_effect_document(doc_id):
            if "z1" in doc_id:
                raise RuntimeError("Firestore overloaded")
            return original_document(doc_id)
            
        self.db.collection("zone_states").document = side_effect_document

        with patch('main.gdchardwaremanagement_v1alpha') as mock_gdc:
            mock_gdc.Zone.State.return_value.name = "READY_FOR_CUSTOMER_FACTORY_TURNUP_CHECKS"

            # Execute
            main.poll_zones(
                self.hwm_client,
                self.db,
                self.publisher,
                host_project_id=self.project_id,
                target_project_id=self.project_id,
                region=self.region,
                topic=self.topic
            )

        # Verify: z2 processed successfully (1 message published)
        self.assertEqual(len(self.publisher.published_messages), 1)
        self.assertEqual(self.publisher.published_messages[0]["data"]["zone"], zone2_name)


    @patch('main.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient')
    @patch('main.firestore.Client')
    @patch('main.pubsub_v1.PublisherClient')
    @patch('main.poll_zones')
    @patch.dict(os.environ, {
        "PROJECT_ID": "host-project",
        "REGION": "us-central1",
        "FIRESTORE_DB": "test-db",
        "PUBSUB_TOPIC": "test-topic",
        "MONITORED_PROJECTS": "p1, p2",
        "MONITORED_REGIONS": "r1, r2"
    })
    def test_main_multi_project(self, mock_poll, mock_pubsub_cls, mock_firestore_cls, mock_hwm_cls):
        fake_hwm = FakeHwmClient()
        fake_db = FakeFirestore()
        fake_pub = FakePublisher()
        
        mock_hwm_cls.return_value = fake_hwm
        mock_firestore_cls.return_value = fake_db
        mock_pubsub_cls.return_value = fake_pub

        main.main(MagicMock())

        # 2 projects * 2 regions = 4 calls
        self.assertEqual(mock_poll.call_count, 4)
        
        calls = mock_poll.call_args_list
        target_projects = [c.kwargs['target_project_id'] for c in calls]
        target_regions = [c.kwargs['region'] for c in calls]
        
        # Verify projects
        self.assertEqual(target_projects.count('p1'), 2)
        self.assertEqual(target_projects.count('p2'), 2)
        
        # Verify regions
        self.assertEqual(target_regions.count('r1'), 2)
        self.assertEqual(target_regions.count('r2'), 2)
        
        # Check host_project_id is passed correctly
        self.assertEqual(calls[0].kwargs['host_project_id'], "host-project")
        
        self.assertIs(calls[0].kwargs['hwm_client'], fake_hwm)
        self.assertIs(calls[0].kwargs['db'], fake_db)


    def test_main_missing_env_vars(self):
        # Clear environment variables to force error
        with patch.dict(os.environ, {}, clear=True):
            result = main.main(MagicMock())
            # Verify 500 error
            self.assertEqual(result, ("Error: Missing required environment variables", 500))

    @patch('main.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient')
    @patch('main.firestore.Client')
    @patch('main.pubsub_v1.PublisherClient')
    @patch('main.poll_zones')
    @patch.dict(os.environ, {
        "PROJECT_ID": "host-project",
        "REGION": "us-central1",
        "FIRESTORE_DB": "test-db",
        "PUBSUB_TOPIC": "test-topic",
        "MONITORED_REGIONS": "r1, r2, r3"
    })
    def test_main_multi_region_single_project(self, mock_poll, mock_pubsub_cls, mock_firestore_cls, mock_hwm_cls):
        """Test iteration over multiple regions with a single (default) project."""
        main.main(MagicMock())

        # 1 project (default) * 3 regions = 3 calls
        self.assertEqual(mock_poll.call_count, 3)
        
        calls = mock_poll.call_args_list
        target_regions = [c.kwargs['region'] for c in calls]
        
        self.assertCountEqual(target_regions, ['r1', 'r2', 'r3'])
        
        # Verify project is always host-project
        for call in calls:
            self.assertEqual(call.kwargs['target_project_id'], "host-project")

    @patch('main.gdchardwaremanagement_v1alpha.GDCHardwareManagementClient')
    @patch('main.firestore.Client')
    @patch('main.pubsub_v1.PublisherClient')
    @patch('main.poll_zones')
    @patch.dict(os.environ, {
        "PROJECT_ID": "host-project",
        "REGION": "us-central1",
        "FIRESTORE_DB": "test-db",
        "PUBSUB_TOPIC": "test-topic"
        # No MONITORED_REGIONS, should default to REGION
    })
    def test_main_default_region(self, mock_poll, mock_pubsub_cls, mock_firestore_cls, mock_hwm_cls):
        """Test default behavior when MONITORED_REGIONS is not set."""
        main.main(MagicMock())

        self.assertEqual(mock_poll.call_count, 1)
        self.assertEqual(mock_poll.call_args.kwargs['region'], "us-central1")

if __name__ == '__main__':
    unittest.main()
