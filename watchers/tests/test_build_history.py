import unittest
from unittest.mock import patch, MagicMock, call
import os
from google.cloud.devtools import cloudbuild
from google.protobuf.timestamp_pb2 import Timestamp
from google.cloud.devtools.cloudbuild import Build

# Assuming the classes are in a file named 'build_history.py'
# If not, adjust the import path accordingly
from src.build_history import BuildHistory, BuildSummary

Status = Build.Status

# Helper to create mock build objects
def create_mock_build(id, status, substitutions=None, create_time_seconds=0):
    build = MagicMock(spec=cloudbuild.Build)
    build.id = id
    build.status = status
    build.substitutions = substitutions if substitutions else {}
    # Add a mock create_time if needed for ordering, though the current logic doesn't sort by time
    build.create_time = Timestamp(seconds=create_time_seconds)
    return build

class TestBuildSummary(unittest.TestCase):

    def test_initial_state(self):
        summary = BuildSummary()
        self.assertIsNone(summary.latestStatus)
        self.assertEqual(summary.numberOfBuilds, 0)
        self.assertEqual(summary.numberOfFailures, 0)
        self.assertFalse(summary.retriable)

    def test_add_build_success(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.SUCCESS)
        summary.add_build(build)
        self.assertEqual(summary.latestStatus, Status.SUCCESS)
        self.assertEqual(summary.numberOfBuilds, 1)
        self.assertEqual(summary.numberOfFailures, 0)
        self.assertFalse(summary.retriable)

    def test_add_build_failure(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.FAILURE)
        summary.add_build(build)
        # Note: latestStatus isn't updated on failure if it was None initially
        # self.assertEqual(summary.latestStatus, MockBuildStatus.FAILURE) # This depends on initial state logic
        self.assertEqual(summary.numberOfBuilds, 1)
        self.assertEqual(summary.numberOfFailures, 1)
        self.assertTrue(summary.retriable)

    def test_add_build_working(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.WORKING)
        summary.add_build(build)
        self.assertEqual(summary.latestStatus, Status.WORKING)
        self.assertEqual(summary.numberOfBuilds, 1)
        self.assertEqual(summary.numberOfFailures, 0)
        self.assertFalse(summary.retriable)

    def test_add_build_queued(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.QUEUED)
        summary.add_build(build)
        self.assertEqual(summary.latestStatus, Status.QUEUED)
        self.assertEqual(summary.numberOfBuilds, 1)
        self.assertEqual(summary.numberOfFailures, 0)
        self.assertFalse(summary.retriable)

    def test_add_build_pending(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.PENDING)
        summary.add_build(build)
        self.assertEqual(summary.latestStatus, Status.PENDING)
        self.assertEqual(summary.numberOfBuilds, 1)
        self.assertEqual(summary.numberOfFailures, 0)
        self.assertFalse(summary.retriable)

    def test_add_build_sequence_fail_then_success(self):
        summary = BuildSummary()
        build_fail = create_mock_build("b1", Status.FAILURE)
        build_success = create_mock_build("b2", Status.SUCCESS)
        summary.add_build(build_fail)
        summary.add_build(build_success) # Success overrides retriable
        self.assertEqual(summary.latestStatus, Status.SUCCESS)
        self.assertEqual(summary.numberOfBuilds, 2)
        self.assertEqual(summary.numberOfFailures, 1) # Failure count still increments
        self.assertFalse(summary.retriable)

    def test_add_build_sequence_fail_then_working(self):
        summary = BuildSummary()
        build_fail = create_mock_build("b1", Status.FAILURE)
        build_working = create_mock_build("b2", Status.WORKING)
        summary.add_build(build_fail)
        summary.add_build(build_working) # Working overrides retriable
        self.assertEqual(summary.latestStatus, Status.WORKING)
        self.assertEqual(summary.numberOfBuilds, 2)
        self.assertEqual(summary.numberOfFailures, 1)
        self.assertFalse(summary.retriable)

    def test_add_build_sequence_success_then_fail(self):
        summary = BuildSummary()
        build_success = create_mock_build("b1", Status.SUCCESS)
        build_fail = create_mock_build("b2", Status.FAILURE)
        summary.add_build(build_success)
        summary.add_build(build_fail) # Failure after success doesn't change status/retriable
        self.assertEqual(summary.latestStatus, Status.SUCCESS)
        self.assertEqual(summary.numberOfBuilds, 2)
        self.assertEqual(summary.numberOfFailures, 1) # Failure count still increments
        self.assertFalse(summary.retriable) # Still False because latest was SUCCESS

    def test_add_build_sequence_working_then_fail(self):
        summary = BuildSummary()
        build_working = create_mock_build("b1", Status.WORKING)
        build_fail = create_mock_build("b2", Status.FAILURE)
        summary.add_build(build_working)
        summary.add_build(build_fail) # Failure after working doesn't change status/retriable
        self.assertEqual(summary.latestStatus, Status.WORKING)
        self.assertEqual(summary.numberOfBuilds, 2)
        self.assertEqual(summary.numberOfFailures, 1)
        self.assertFalse(summary.retriable) # Still False because latest was WORKING

    def test_add_build_multiple_failures(self):
        summary = BuildSummary()
        build1 = create_mock_build("b1", Status.FAILURE)
        build2 = create_mock_build("b2", Status.TIMEOUT)
        summary.add_build(build1)
        summary.add_build(build2)
        # self.assertEqual(summary.latestStatus, MockBuildStatus.TIMEOUT) # Status doesn't update on failure if already failed
        self.assertEqual(summary.numberOfBuilds, 2)
        self.assertEqual(summary.numberOfFailures, 2)
        self.assertTrue(summary.retriable)

    def test_is_retriable_false_max_retries_exceeded(self):
        summary = BuildSummary()
        build1 = create_mock_build("b1", Status.FAILURE)
        build2 = create_mock_build("b2", Status.INTERNAL_ERROR)
        summary.add_build(build1)
        summary.add_build(build2) # 2 failures
        self.assertTrue(summary.is_retriable(max_retries=2))
        self.assertFalse(summary.is_retriable(max_retries=1))
        self.assertFalse(summary.is_retriable(max_retries=0))

    def test_is_retriable_false_not_retriable_state(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.SUCCESS)
        summary.add_build(build)
        self.assertFalse(summary.is_retriable(max_retries=1))

        summary = BuildSummary()
        build = create_mock_build("b1", Status.WORKING)
        summary.add_build(build)
        self.assertFalse(summary.is_retriable(max_retries=1))


@patch('google.cloud.devtools.cloudbuild.CloudBuildClient') # Patch the client in the module where it's used
class TestBuildHistory(unittest.TestCase):

    def setUp(self):
        # Set environment variable for logging if needed, though we don't assert logs here
        os.environ["LOG_LEVEL"] = "DEBUG"
        self.project_id = "test-project"
        self.region = "us-central1"
        self.max_retries = 2
        self.trigger_name = "my-cool-trigger"
        self.trigger_id = "trigger-123"
        self.parent = f"projects/{self.project_id}/locations/{self.region}"

    def tearDown(self):
        # Clean up environment variables if set
        if "LOG_LEVEL" in os.environ:
            del os.environ["LOG_LEVEL"]

    def test_init(self, MockCloudBuildClient):
        instance = MockCloudBuildClient.return_value
        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertEqual(history.project_id, self.project_id)
        self.assertEqual(history.region, self.region)
        self.assertEqual(history.max_retries, self.max_retries)
        self.assertEqual(history.trigger_name, self.trigger_name)
        self.assertIs(history.client, instance)
        self.assertIsNone(history.builds)
        MockCloudBuildClient.assert_called_once()

    def test_get_build_history_no_triggers(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_client.list_build_triggers.return_value = [] # No triggers found

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertRaises(Exception, history._get_build_history)

    def test_get_build_history_no_matching_triggers(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = "other-trigger-name"
        mock_trigger.id = "other-id"
        mock_client.list_build_triggers.return_value = [mock_trigger]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)

        self.assertRaises(Exception, history._get_build_history)

    def test_get_build_history_matching_trigger_no_builds(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        mock_client.list_builds.return_value = [] # No builds found

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        build_dict = history._get_build_history()

        self.assertEqual(build_dict, {})
        mock_client.list_build_triggers.assert_called_once()
        mock_client.list_builds.assert_called_once_with(request=cloudbuild.ListBuildsRequest(
            project_id=self.project_id,
            filter=f"trigger_id={self.trigger_id}",
            parent=self.parent
        ))

    def test_get_build_history_with_builds(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]

        build1_zone1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        build2_zone1 = create_mock_build("b2", Status.SUCCESS, {"_ZONE": "zone-a"})
        build3_zone2 = create_mock_build("b3", Status.WORKING, {"_ZONE": "zone-b"})
        build4_no_zone = create_mock_build("b4", Status.FAILURE, {}) # No _ZONE
        build5_zone2_fail = create_mock_build("b5", Status.FAILURE, {"_ZONE": "zone-b"})

        mock_client.list_builds.return_value = [
            build5_zone2_fail, build4_no_zone, build3_zone2, build2_zone1, build1_zone1
        ] # Order shouldn't matter for grouping, but does for status updates

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        build_dict = history._get_build_history()

        self.assertIn("zone-a", build_dict)
        self.assertIn("zone-b", build_dict)
        self.assertEqual(len(build_dict), 2) # build4_no_zone should be skipped

        # Check zone-a summary (Failure then Success)
        summary_a = build_dict["zone-a"]
        self.assertEqual(summary_a.numberOfBuilds, 2)
        self.assertEqual(summary_a.numberOfFailures, 1)
        self.assertEqual(summary_a.latestStatus, Status.SUCCESS)
        self.assertFalse(summary_a.retriable)

        # Check zone-b summary (Working then Failure)
        summary_b = build_dict["zone-b"]
        self.assertEqual(summary_b.numberOfBuilds, 2)
        self.assertEqual(summary_b.numberOfFailures, 1)
        self.assertEqual(summary_b.latestStatus, Status.WORKING) # Working status persists
        self.assertFalse(summary_b.retriable)

        mock_client.list_builds.assert_called_once()

    def test_get_build_history_multiple_matching_triggers(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        trigger1 = MagicMock(); trigger1.name = self.trigger_name; trigger1.id = "id1"
        trigger2 = MagicMock(); trigger2.name = "other-trigger"; trigger2.id = "id-other"
        trigger3 = MagicMock(); trigger3.name = self.trigger_name; trigger3.id = "id3"
        mock_client.list_build_triggers.return_value = [trigger1, trigger2, trigger3]

        mock_client.list_builds.return_value = []

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        history._get_build_history()

        expected_filter = "trigger_id=id1 OR trigger_id=id3"
        mock_client.list_builds.assert_called_once_with(request=cloudbuild.ListBuildsRequest(
            project_id=self.project_id,
            filter=expected_filter,
            parent=self.parent
        ))

    def test_should_retry_zone_build_zone_not_found(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1_zone1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build1_zone1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        # Zone 'zone-b' doesn't exist in history
        self.assertFalse(history.should_retry_zone_build("zone-b"))
        self.assertIn("zone-a", history.builds) # History should be populated

    def test_should_retry_zone_build_is_retriable(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1_zone1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build1_zone1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name) # max_retries = 2
        self.assertTrue(history.should_retry_zone_build("zone-a"))

    def test_should_retry_zone_build_not_retriable_max_exceeded(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        build2 = create_mock_build("b2", Status.TIMEOUT, {"_ZONE": "zone-a"})
        build3 = create_mock_build("b3", Status.INTERNAL_ERROR, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build3, build2, build1] # 3 failures

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name) # max_retries = 2
        self.assertFalse(history.should_retry_zone_build("zone-a"))

    def test_should_retry_zone_build_not_retriable_status_success(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        build2 = create_mock_build("b2", Status.SUCCESS, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build2, build1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertFalse(history.should_retry_zone_build("zone-a"))

    def test_should_retry_zone_build_not_retriable_status_working(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        build2 = create_mock_build("b2", Status.WORKING, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build2, build1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertFalse(history.should_retry_zone_build("zone-a"))

    def test_should_retry_zone_build_lazy_load(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertIsNone(history.builds) # Initially None

        # First call - fetches history
        self.assertTrue(history.should_retry_zone_build("zone-a"))
        self.assertIsNotNone(history.builds)
        mock_client.list_builds.assert_called_once()

        # Second call - uses cached history
        mock_client.list_builds.reset_mock() # Reset mock call count
        self.assertTrue(history.should_retry_zone_build("zone-a"))
        mock_client.list_builds.assert_not_called() # Should not call again

    def test_should_retry_zone_build_missing_zone_name(self, MockCloudBuildClient):
        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        with self.assertRaisesRegex(Exception, 'missing zone_name'):
            history.should_retry_zone_build(None)
        with self.assertRaisesRegex(Exception, 'missing zone_name'):
            history.should_retry_zone_build("")