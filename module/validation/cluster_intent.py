from typing import Optional, Annotated, Iterable
from pydantic import BaseModel, StringConstraints, IPvAnyNetwork, validator

# https://www.ietf.org/rfc/rfc1035.txt
RFC1035String = Annotated[str, StringConstraints(min_length=1, max_length=63, pattern="^[a-z]([-a-z0-9]*[a-z0-9])?")]

ProjectIdString = Annotated[str, StringConstraints(min_length=6, max_length=30, pattern="^[a-z]([-a-z0-9]*[a-z0-9])?")]

class SourceOfTruthModel(BaseModel):
    store_id: RFC1035String
    zone_name: Optional[str] = None
    machine_project_id: ProjectIdString
    fleet_project_id: ProjectIdString
    cluster_name: RFC1035String
    location: RFC1035String
    node_count: int
    cluster_ipv4_cidr: IPvAnyNetwork
    services_ipv4_cidr: IPvAnyNetwork
    external_load_balancer_ipv4_address_pools: str
    sync_repo: str
    sync_branch: str
    sync_dir: str
    secrets_project_id: ProjectIdString
    git_token_secrets_manager_name: str
    cluster_version: str
    maintenance_window_recurrence: Optional[str] = None
    maintenance_window_start: Optional[str] = None
    maintenance_window_end: Optional[str] = None
    maintenance_exclusion_name_1: Optional[str] = None
    maintenance_exclusion_start_1: Optional[str] = None
    maintenance_exclusion_end_1: Optional[str] = None
    maintenance_exclusion_name_2: Optional[str] = None
    maintenance_exclusion_start_2: Optional[str] = None
    maintenance_exclusion_end_2: Optional[str] = None
    maintenance_exclusion_name_3: Optional[str] = None
    maintenance_exclusion_start_3: Optional[str] = None
    maintenance_exclusion_end_3: Optional[str] = None
    subnet_vlans: Optional[str]
    labels: Optional[str] = None
    backup_enable: Optional[bool] = None
    recreate_on_delete: Optional[bool]

    @validator('*', pre=True)
    def convert_to_none(cls, v):
        """
            Convert empty strings and empty lists to None
        """
        if isinstance(v, str) and v.strip() == "":
            return None
        if isinstance(v, Iterable) and len(v) == 0:
            return None
        else:
            return v
