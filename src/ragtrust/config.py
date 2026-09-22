from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Search current directory or parent directories for .env
load_dotenv()


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("RAGTRUST_MODE", "fixture").lower()
    data_dir: Path = Path(os.getenv("RAGTRUST_DATA_DIR", "./data")).resolve()
    database_url: str = os.getenv("RAGTRUST_DATABASE_URL", "sqlite:///./data/ragtrust.db")
    
    # Microsoft Foundry connection settings
    project_connection_string: str | None = (
        os.getenv("PROJECT_CONNECTION_STRING") or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    )
    model_deployment_name: str = os.getenv("MODEL_DEPLOYMENT_NAME") or os.getenv("FOUNDRY_MODEL_NAME", "gpt-4o")
    azure_subscription_id: str | None = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group: str | None = os.getenv("RESOURCE_GROUP")
    foundry_resource_name: str | None = os.getenv("FOUNDRY_RESOURCE_NAME")
    project_name: str | None = os.getenv("PROJECT_NAME")
    appinsights_connection_string: str | None = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    use_deployed_agents: bool = os.getenv("FOUNDRY_USE_DEPLOYED_AGENTS", "true").lower() in {
        "1", "true", "yes", "on"
    }
    
    # Generation & evaluation limits
    max_candidates: int = int(os.getenv("RAGTRUST_MAX_CANDIDATES", "100"))
    max_repairs: int = int(os.getenv("RAGTRUST_MAX_REPAIRS", "2"))

    @property
    def has_foundry_config(self) -> bool:
        return bool(self.project_connection_string and self.model_deployment_name)

    def validate(self) -> None:
        if self.mode not in {"fixture", "foundry"}:
            raise ValueError("RAGTRUST_MODE must be 'fixture' or 'foundry'")
        if self.mode == "foundry" and not self.has_foundry_config:
            raise ValueError("Foundry mode requires PROJECT_CONNECTION_STRING and MODEL_DEPLOYMENT_NAME")


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
