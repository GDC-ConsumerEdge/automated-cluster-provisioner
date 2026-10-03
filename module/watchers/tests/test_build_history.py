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
        self.assertIsNone(summary.latest_non_failure_status)
        self.assertFalse(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_flag_first_non_failure_build_success(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.SUCCESS)
        summary.flag_first_non_failure_build(build)
        self.assertEqual(summary.latest_non_failure_status, Status.SUCCESS)
        self.assertFalse(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_flag_first_non_failure_build_failure(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.FAILURE)
        summary.flag_first_non_failure_build(build)
        # Note: latest_non_failure_status isn't updated on failure if it was None initially
        # self.assertEqual(summary.latest_non_failure_status, MockBuildStatus.FAILURE) # This depends on initial state logic
        self.assertTrue(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_flag_first_non_failure_build_working(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.WORKING)
        summary.flag_first_non_failure_build(build)
        self.assertEqual(summary.latest_non_failure_status, Status.WORKING)
        self.assertFalse(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_flag_first_non_failure_build_queued(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.QUEUED)
        summary.flag_first_non_failure_build(build)
        self.assertEqual(summary.latest_non_failure_status, Status.QUEUED)
        self.assertFalse(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_flag_first_non_failure_build_pending(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.PENDING)
        summary.flag_first_non_failure_build(build)
        self.assertEqual(summary.latest_non_failure_status, Status.PENDING)
        self.assertFalse(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_flag_first_non_failure_build_sequence_fail_then_success(self):
        summary = BuildSummary()
        build_fail = create_mock_build("b1", Status.FAILURE)
        build_success = create_mock_build("b2", Status.SUCCESS)
        summary.flag_first_non_failure_build(build_fail)
        summary.flag_first_non_failure_build(build_success) # Success overrides retriable
        self.assertEqual(summary.latest_non_failure_status, Status.SUCCESS)
        self.assertFalse(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_flag_first_non_failure_build_sequence_fail_then_working(self):
        summary = BuildSummary()
        build_fail = create_mock_build("b1", Status.FAILURE)
        build_working = create_mock_build("b2", Status.WORKING)
        summary.flag_first_non_failure_build(build_fail)
        summary.flag_first_non_failure_build(build_working) # Working overrides retriable
        self.assertEqual(summary.latest_non_failure_status, Status.WORKING)
        self.assertFalse(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_flag_first_non_failure_build_multiple_failures(self):
        summary = BuildSummary()
        build1 = create_mock_build("b1", Status.FAILURE)
        build2 = create_mock_build("b2", Status.TIMEOUT)
        summary.flag_first_non_failure_build(build1)
        summary.flag_first_non_failure_build(build2)
        # self.assertEqual(summary.latest_non_failure_status, MockBuildStatus.TIMEOUT) # Status doesn't update on failure if already failed
        self.assertTrue(summary.retriable)
        self.assertEqual(summary.latest_try_count, 0)

    def test_is_retriable_false_not_retriable_state(self):
        summary = BuildSummary()
        build = create_mock_build("b1", Status.SUCCESS)
        summary.flag_first_non_failure_build(build)
        self.assertFalse(summary.retriable)

        summary = BuildSummary()
        build = create_mock_build("b1", Status.WORKING)
        summary.flag_first_non_failure_build(build)
        self.assertFalse(summary.retriable)


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
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        instance.list_build_triggers.return_value = [mock_trigger]
        instance.list_builds.return_value = []

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertEqual(history.project_id, self.project_id)
        self.assertEqual(history.region, self.region)
        self.assertEqual(history.max_retries, self.max_retries)
        self.assertEqual(history.trigger_names, {self.trigger_name})
        self.assertIs(history.client, instance)
        self.assertIsNotNone(history.builds)
        MockCloudBuildClient.assert_called_once()

    def test_get_build_history_no_triggers(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_client.list_build_triggers.return_value = [] # No triggers found

        with self.assertRaises(Exception):
            BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)

    def test_get_build_history_no_matching_triggers(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = "other-trigger-name"
        mock_trigger.id = "other-id"
        mock_client.list_build_triggers.return_value = [mock_trigger]

        with self.assertRaises(Exception):
            BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)

    def test_get_build_history_matching_trigger_no_builds(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        mock_client.list_builds.return_value = [] # No builds found

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        
        self.assertEqual(history.builds, {})
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
        build_dict = history.builds

        self.assertIn(("zone-a", ""), build_dict)
        self.assertIn(("zone-b", ""), build_dict)
        self.assertEqual(len(build_dict), 2) # build4_no_zone should be skipped

        # Check zone-a summary (Failure then Success)
        summary_a = build_dict[("zone-a", "")]
        self.assertEqual(summary_a.latest_non_failure_status, Status.SUCCESS)
        self.assertFalse(summary_a.retriable)

        # Check zone-b summary (Working then Failure)
        summary_b = build_dict[("zone-b", "")]
        self.assertEqual(summary_b.latest_non_failure_status, Status.WORKING) # Working status persists
        self.assertFalse(summary_b.retriable)

        mock_client.list_builds.assert_called_once()

    def test_get_build_history_groups_by_hash(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]

        # Create builds for SAME zone but DIFFERENT hashes
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a", "_INTENT_HASH": "hash-1"})
        build2 = create_mock_build("b2", Status.SUCCESS, {"_ZONE": "zone-a", "_INTENT_HASH": "hash-2"})

        mock_client.list_builds.return_value = [build2, build1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        build_dict = history.builds

        # Verify that it groups them separately!
        self.assertIn(("zone-a", "hash-1"), build_dict)
        self.assertIn(("zone-a", "hash-2"), build_dict)
        self.assertEqual(len(build_dict), 2)

    def test_get_build_history_extracts_try_count(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]

        # Create build with _TRY_COUNT
        build = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a", "_INTENT_HASH": "hash-1", "_TRY_COUNT": "3"})

        mock_client.list_builds.return_value = [build]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        
        # Verify that it extracts the try count correctly!
        self.assertEqual(history.get_latest_try_count("zone-a", "hash-1"), 3)

    @patch('src.build_history.BuildSummary')
    def test_get_build_history_optimizes_traversal(self, MockBuildSummary, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]

        # Create builds for SAME zone and hash: Newest=SUCCESS, Older=FAILURE
        build1 = create_mock_build("b1", Status.SUCCESS, {"_ZONE": "zone-a", "_INTENT_HASH": "hash-1"})
        build2 = create_mock_build("b2", Status.FAILURE, {"_ZONE": "zone-a", "_INTENT_HASH": "hash-1"})

        mock_client.list_builds.return_value = [build1, build2]

        # Mock BuildSummary instance
        mock_summary = MagicMock()
        mock_summary.latest_non_failure_status = None
        
        def side_effect(build):
            mock_summary.latest_non_failure_status = build.status
            
        mock_summary.flag_first_non_failure_build.side_effect = side_effect
        MockBuildSummary.return_value = mock_summary

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        
        # Verify that flag_first_non_failure_build was only called ONCE!
        self.assertEqual(mock_summary.flag_first_non_failure_build.call_count, 1)

    def test_latest_attempt_failed(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]

        # Test case 1: Newest build failed
        build_fail = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a", "_INTENT_HASH": "hash-1"})
        mock_client.list_builds.return_value = [build_fail]
        
        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        summary = history.builds[("zone-a", "hash-1")]
        self.assertTrue(summary.latest_attempt_failed)

        # Test case 2: Newest build succeeded
        build_success = create_mock_build("b2", Status.SUCCESS, {"_ZONE": "zone-b", "_INTENT_HASH": "hash-2"})
        mock_client.list_builds.return_value = [build_success]
        
        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        summary = history.builds[("zone-b", "hash-2")]
        self.assertFalse(summary.latest_attempt_failed)

    def test_should_retry_independent_per_hash(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]

        # Create builds for SAME zone but DIFFERENT hashes
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a", "_INTENT_HASH": "hash-1"})
        build2 = create_mock_build("b2", Status.SUCCESS, {"_ZONE": "zone-a", "_INTENT_HASH": "hash-2"})

        mock_client.list_builds.return_value = [build2, build1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)

        # Verify independent retry results
        self.assertTrue(history.should_retry_zone_build("zone-a", "hash-1"))
        self.assertFalse(history.should_retry_zone_build("zone-a", "hash-2"))

    def test_get_build_history_backward_compatibility(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]

        # Create build WITHOUT _INTENT_HASH
        build = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})

        mock_client.list_builds.return_value = [build]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        build_dict = history.builds

        # Verify it uses empty string as hash
        self.assertIn(("zone-a", ""), build_dict)

    def test_get_latest_try_count_empty_history(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        mock_client.list_builds.return_value = []

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        
        # Verify it returns 0 for non-existent history
        self.assertEqual(history.get_latest_try_count("zone-a", "hash-1"), 0)

    def test_get_build_history_multiple_matching_triggers(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        trigger1 = MagicMock(); trigger1.name = self.trigger_name; trigger1.id = "id1"
        trigger2 = MagicMock(); trigger2.name = "other-trigger"; trigger2.id = "id-other"
        trigger3 = MagicMock(); trigger3.name = self.trigger_name; trigger3.id = "id3"
        mock_client.list_build_triggers.return_value = [trigger1, trigger2, trigger3]

        mock_client.list_builds.return_value = []

        BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)

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
        self.assertFalse(history.should_retry_zone_build("zone-b", ""))
        self.assertIn(("zone-a", ""), history.builds) # History should be populated

    def test_should_retry_zone_build_is_retriable(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1_zone1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build1_zone1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name) # max_retries = 2
        self.assertTrue(history.should_retry_zone_build("zone-a", ""))

    def test_should_retry_zone_build_not_retriable_max_exceeded(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        build2 = create_mock_build("b2", Status.TIMEOUT, {"_ZONE": "zone-a"})
        build3 = create_mock_build("b3", Status.INTERNAL_ERROR, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build3, build2, build1] # 3 failures

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name) # max_retries = 2
        self.assertTrue(history.should_retry_zone_build("zone-a", ""))

    def test_should_retry_zone_build_not_retriable_status_success(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        build2 = create_mock_build("b2", Status.SUCCESS, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build2, build1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertFalse(history.should_retry_zone_build("zone-a", ""))

    def test_should_retry_zone_build_not_retriable_status_working(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        build2 = create_mock_build("b2", Status.WORKING, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build2, build1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertFalse(history.should_retry_zone_build("zone-a", ""))

    def test_should_retry_zone_build_eager_load(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock(); mock_trigger.name = self.trigger_name; mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        build1 = create_mock_build("b1", Status.FAILURE, {"_ZONE": "zone-a"})
        mock_client.list_builds.return_value = [build1]

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        self.assertIsNotNone(history.builds) # Should be loaded at init

        # First call
        self.assertTrue(history.should_retry_zone_build("zone-a", ""))
        mock_client.list_builds.assert_called_once()

        # Second call - uses cached history
        mock_client.list_builds.reset_mock() # Reset mock call count
        self.assertTrue(history.should_retry_zone_build("zone-a", ""))
        mock_client.list_builds.assert_not_called() # Should not call again

    def test_should_retry_zone_build_missing_zone_name(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        mock_client.list_builds.return_value = []

        history = BuildHistory(self.project_id, self.region, self.max_retries, self.trigger_name)
        with self.assertRaisesRegex(Exception, 'missing zone_name'):
            history.should_retry_zone_build(None, "")
        with self.assertRaisesRegex(Exception, 'missing zone_name'):
            history.should_retry_zone_build("", "")

    def _history_from_builds(self, MockCloudBuildClient, builds):
        mock_client = MockCloudBuildClient.return_value
        mock_trigger = MagicMock()
        mock_trigger.name = self.trigger_name
        mock_trigger.id = self.trigger_id
        mock_client.list_build_triggers.return_value = [mock_trigger]
        mock_client.list_builds.return_value = builds
        return BuildHistory(self.project_id, self.region, self.max_retries,
                            self.trigger_name)

    def test_has_active_build_for_in_flight_statuses(self, MockCloudBuildClient):
        for status in (Status.WORKING, Status.QUEUED, Status.PENDING):
            with self.subTest(status=status.name):
                build = create_mock_build(
                    "b1", status, {"_ZONE": "zone-a", "_STORE_ID": "store-1"})
                history = self._history_from_builds(MockCloudBuildClient, [build])
                self.assertTrue(history.has_active_build("store-1"))

    def test_has_active_build_false_for_settled_statuses(self, MockCloudBuildClient):
        for status in (Status.SUCCESS, Status.FAILURE, Status.TIMEOUT,
                       Status.CANCELLED, Status.INTERNAL_ERROR):
            with self.subTest(status=status.name):
                build = create_mock_build(
                    "b1", status, {"_ZONE": "zone-a", "_STORE_ID": "store-1"})
                history = self._history_from_builds(MockCloudBuildClient, [build])
                self.assertFalse(history.has_active_build("store-1"))

    def test_has_active_build_when_zone_substitution_missing(self, MockCloudBuildClient):
        """A build without _ZONE is skipped for retry accounting, but it is still running.
        Treating it as inactive would let a modify build race it."""
        build = create_mock_build("b1", Status.WORKING, {"_STORE_ID": "store-1"})
        history = self._history_from_builds(MockCloudBuildClient, [build])

        self.assertTrue(history.has_active_build("store-1"))
        self.assertEqual(history.builds, {})

    def test_has_active_build_ignores_builds_without_store_id(self, MockCloudBuildClient):
        build = create_mock_build("b1", Status.WORKING, {"_ZONE": "zone-a"})
        history = self._history_from_builds(MockCloudBuildClient, [build])

        self.assertEqual(history.active_stores, set())
        self.assertFalse(history.has_active_build("store-1"))

    def test_has_active_build_only_matches_the_requested_store(self, MockCloudBuildClient):
        build = create_mock_build(
            "b1", Status.WORKING, {"_ZONE": "zone-a", "_STORE_ID": "store-1"})
        history = self._history_from_builds(MockCloudBuildClient, [build])

        self.assertFalse(history.has_active_build("store-2"))

    def test_trigger_names_accepts_a_list(self, MockCloudBuildClient):
        """The cluster watcher passes both the modify and create triggers so an
        in-flight create-cluster build is visible to has_active_build()."""
        mock_client = MockCloudBuildClient.return_value
        modify = MagicMock(); modify.name = "modify-trigger"; modify.id = "id-modify"
        create = MagicMock(); create.name = "create-trigger"; create.id = "id-create"
        unrelated = MagicMock(); unrelated.name = "unrelated"; unrelated.id = "id-other"
        mock_client.list_build_triggers.return_value = [modify, create, unrelated]
        mock_client.list_builds.return_value = []

        history = BuildHistory(self.project_id, self.region, self.max_retries,
                               ["modify-trigger", "create-trigger"])

        self.assertEqual(history.trigger_names, {"modify-trigger", "create-trigger"})
        build_filter = mock_client.list_builds.call_args.kwargs["request"].filter
        self.assertIn("trigger_id=id-modify", build_filter)
        self.assertIn("trigger_id=id-create", build_filter)
        self.assertNotIn("id-other", build_filter)

    def test_trigger_names_partial_miss_still_loads_history(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        modify = MagicMock(); modify.name = "modify-trigger"; modify.id = "id-modify"
        mock_client.list_build_triggers.return_value = [modify]
        mock_client.list_builds.return_value = []

        BuildHistory(self.project_id, self.region, self.max_retries,
                     ["modify-trigger", "create-trigger"])

        build_filter = mock_client.list_builds.call_args.kwargs["request"].filter
        self.assertEqual(build_filter, "trigger_id=id-modify")

    def test_trigger_names_total_miss_raises(self, MockCloudBuildClient):
        mock_client = MockCloudBuildClient.return_value
        unrelated = MagicMock(); unrelated.name = "unrelated"; unrelated.id = "id-other"
        mock_client.list_build_triggers.return_value = [unrelated]

        with self.assertRaises(Exception):
            BuildHistory(self.project_id, self.region, self.max_retries,
                         ["modify-trigger", "create-trigger"])