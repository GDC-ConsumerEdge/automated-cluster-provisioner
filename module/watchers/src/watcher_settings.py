from typing import Optional
from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings

class WatcherSettings(BaseSettings):
    project_id: str = Field(..., alias="GOOGLE_CLOUD_PROJECT")
    secrets_project_id: Optional[str] = Field(default=None, alias="PROJECT_ID_SECRETS")
    region: str = Field(..., alias="REGION")
    git_secret_id: str = Field(..., alias="GIT_SECRET_ID")
    source_of_truth_repo: str = Field(..., alias="SOURCE_OF_TRUTH_REPO")
    source_of_truth_branch: str = Field(..., alias="SOURCE_OF_TRUTH_BRANCH")
    source_of_truth_path: str = Field(..., alias="SOURCE_OF_TRUTH_PATH")
    cloud_build_trigger_name: str = Field(..., alias="CB_TRIGGER_NAME")
    max_retries: int = Field(default=0, ge=0, le=5, alias="MAX_RETRIES")
    max_workers: int = Field(default=1, ge=1, le=100, alias="MAX_WORKERS")

    @model_validator(mode='after')
    def set_secrets_project_fallback(self) -> 'WatcherSettings':
        """If secrets_project_id is not set, use project_id as the fallback."""
        if not self.secrets_project_id:
            self.secrets_project_id = self.project_id
        return self

    @computed_field
    @property
    def cloud_build_trigger(self) -> str:
        return f'projects/{self.project_id}/locations/{self.region}/triggers/{self.cloud_build_trigger_name}'
    
    @field_validator('source_of_truth_repo')
    @classmethod
    def check_repo_protocol(cls, v: str) -> str:
        """Validate that the repo URL does not contain a protocol."""
        if v.lower().startswith(('http://', 'https://')):
            raise ValueError('must not include the http/https protocol')
        return v