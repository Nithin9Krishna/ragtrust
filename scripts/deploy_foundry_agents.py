#!/usr/bin/env python3
"""Create immutable versions of the four RAGTrust prompt agents in Foundry."""

from __future__ import annotations

import json

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

from ragtrust.agents.foundry_definitions import FOUNDRY_AGENT_DEFINITIONS
from ragtrust.config import settings


def main() -> None:
    if not settings.project_connection_string:
        raise SystemExit("FOUNDRY_PROJECT_ENDPOINT is required")

    project = AIProjectClient(
        endpoint=settings.project_connection_string,
        credential=DefaultAzureCredential(),
    )
    deployed: list[dict[str, str]] = []
    for role, spec in FOUNDRY_AGENT_DEFINITIONS.items():
        agent = project.agents.create_version(
            agent_name=spec["name"],
            definition=PromptAgentDefinition(
                model=settings.model_deployment_name,
                instructions=spec["instructions"],
                temperature=0.1,
            ),
            description=spec["description"],
            metadata={"application": "ragtrust", "application_role": role, "release": "0.1.0"},
        )
        deployed.append(
            {
                "application_role": role,
                "name": agent.name,
                "version": str(agent.version),
                "id": str(agent.id),
            }
        )

    print(json.dumps({"deployed_agents": deployed}, indent=2))


if __name__ == "__main__":
    main()
