import logging
import os
from google.cloud.devtools import cloudbuild
from google.cloud.devtools.cloudbuild import Build
from typing import Dict

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

class BuildSummary:
    latestStatus: Build.Status = None
    numberOfBuilds: int = 0
    numberOfFailures: int = 0
    retriable: bool = False

    def add_build(self, build: cloudbuild.Build):
        self.numberOfBuilds += 1

        if build.status not in (
            cloudbuild.Build.Status.QUEUED,
            cloudbuild.Build.Status.PENDING,
            cloudbuild.Build.Status.WORKING,
            cloudbuild.Build.Status.SUCCESS):
            self.numberOfFailures += 1

        # This means that there is a build in progress and we should not retry or change the status
        if self.latestStatus in (cloudbuild.Build.Status.QUEUED, cloudbuild.Build.Status.PENDING, cloudbuild.Build.Status.WORKING):
            self.retriable = False
            return

        # This means that there was a successful build and we should not retry
        if self.latestStatus == cloudbuild.Build.Status.SUCCESS:
            self.retriable = False
            return
        
        if build.status in (cloudbuild.Build.Status.QUEUED, cloudbuild.Build.Status.PENDING, cloudbuild.Build.Status.WORKING):
            self.latestStatus = build.status
            self.retriable = False
        elif build.status == cloudbuild.Build.Status.SUCCESS:
            self.latestStatus = build.status
            self.retriable = False
        else:
            # Any status in this category can be treated as a failure
            self.retriable = True

    def is_retriable(self, max_retries: int):
        if self.numberOfFailures > max_retries:
            return False
        
        return self.retriable


class BuildHistory:
    def __init__(self, project_id: str, region: str, max_retries: int, trigger_name: str):
        self.project_id = project_id
        self.region = region
        self.max_retries = max_retries
        self.trigger_name = trigger_name
        self.client = cloudbuild.CloudBuildClient()
        self.builds: Dict[str, BuildSummary] = None

    def _get_build_history(self) ->Dict[str, BuildSummary]:
        """
        Queries for Cloud Build history matching a specific trigger name.

        Args:
            trigger_name: The name of the Cloud Build trigger.

        Returns:
            A dictionary with the zone name as the key and the build summary
            which contains relevant information to determine if a retry should
            be triggered.
        """
        trigger_request = cloudbuild.ListBuildTriggersRequest(
            project_id = self.project_id,
            parent = f"projects/{self.project_id}/locations/{self.region}"
        )

        trigger_name_filter = ""

        triggers = self.client.list_build_triggers(trigger_request)

        if len(triggers) == 0:
            raise Exception(f"No triggers found named {self.trigger_name}")

        for trigger in triggers:
            if (trigger.name == self.trigger_name):
                if trigger_name_filter == "":
                    trigger_name_filter += f"trigger_id={trigger.id}"
                else:
                    trigger_name_filter += f" OR trigger_id={trigger.id}"

        request = cloudbuild.ListBuildsRequest(
            project_id=self.project_id,
            filter=trigger_name_filter,
            parent = f"projects/{self.project_id}/locations/{self.region}"
        )

        page_result = self.client.list_builds(request=request)

        # Only page through last 1,000 builds
        build_entries = 0
        build_summary_dict: Dict[str, BuildSummary] = dict()

        for response in page_result:
            build_entries += 1

            if build_entries > 1000:
                break

            zone = ""

            for key in response.substitutions:
                if key == "_ZONE":
                    zone = response.substitutions[key]

            if not zone:
                # Builds are expected to have the _ZONE substitution. This is the value that is
                # matched on to calculate whether a build should be retried or not. 
                logging.warning(f"build found within _ZONE substitution, skipping... Build ID: {response.id}")
                continue

            if zone in build_summary_dict:
                summary = build_summary_dict[zone]
                summary.add_build(response)
            else:
                summary = BuildSummary()
                summary.add_build(response)
                build_summary_dict[zone] = summary

        return build_summary_dict

    def should_retry_zone_build(self, zone_name: str):
        """
        Determines if a build should be retried or not. `False` is returned in the event 
        of no build history for a zone. 

        Args:
            zone_name: The name of the zone
        """
        if not zone_name:
            raise Exception('missing zone_name')
        
        if self.builds is None:
            self.builds = self._get_build_history()

        if zone_name not in self.builds:
            return False
        else:
            build = self.builds[zone_name]
            return build.is_retriable(self.max_retries)

        
        