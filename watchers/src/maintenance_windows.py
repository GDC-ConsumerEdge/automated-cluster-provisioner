from dateutil.parser import parse
from typing import Self
from google.cloud import edgecontainer

from .cluster_intent_model import SourceOfTruthModel

class MaintenanceExclusionWindow:
    def __init__(self, name, start_time, end_time):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time

    def __eq__(self, other):
        return self.name == other.name and self.start_time == other.start_time and self.end_time == other.end_time
    
    def __hash__(self):
        return hash((self.name, self.start_time, self.end_time))

    @staticmethod
    def get_exclusion_windows_from_sot(store_info: SourceOfTruthModel) -> set[Self]:
        exclusions = set()

        for i in range(3):
            exclusion_name = getattr(store_info, f"maintenance_exclusion_name_{i+1}")
            exclusion_start = getattr(store_info, f"maintenance_exclusion_start_{i+1}")
            exclusion_end = getattr(store_info, f"maintenance_exclusion_end_{i+1}")

            # Only consider exclusions that are fully defined
            if (exclusion_name and exclusion_start and exclusion_end):
                exclusion_window = MaintenanceExclusionWindow(exclusion_name, parse(exclusion_start), parse(exclusion_end))
                exclusions.add(exclusion_window)

        return exclusions

    @staticmethod
    def get_exclusion_windows_from_cluster_response(cluster: edgecontainer.Cluster) -> set[Self]:
        exclusions = set()

        if (cluster and cluster.maintenance_policy and cluster.maintenance_policy.maintenance_exclusions):
            for exclusion in cluster.maintenance_policy.maintenance_exclusions:
                exclusions.add(MaintenanceExclusionWindow(exclusion.id, exclusion.window.start_time, exclusion.window.end_time))

        return exclusions