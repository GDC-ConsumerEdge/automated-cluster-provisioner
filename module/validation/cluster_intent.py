from typing import Optional, Annotated, Iterable
from pydantic import BaseModel, StringConstraints, validator, field_validator, ValidationInfo
from ipaddress import IPv4Network

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
    cluster_ipv4_cidr: IPv4Network
    services_ipv4_cidr: IPv4Network
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
    enable_robin_cns: Optional[bool] = None

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

    @field_validator('enable_robin_cns')
    @classmethod
    def check_robin_cns_version(cls, v, info):
        if v is True:
            cluster_version = info.data.get('cluster_version')
            if cluster_version:
                try:
                    version_parts = cluster_version.split('-')[0].split('.')
                    major = int(version_parts[0])
                    minor = int(version_parts[1])
                except (IndexError, ValueError):
                     raise ValueError(f"Invalid cluster version format: {cluster_version}")
                
                if major < 1 or (major == 1 and minor < 12):
                    raise ValueError(f"Robin CNS is only supported for GDC versions 1.12.0 or higher. Current version: {cluster_version}")
        return v
