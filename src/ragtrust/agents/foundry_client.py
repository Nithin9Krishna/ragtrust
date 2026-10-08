from __future__ import annotations

import json
import logging
import os
from typing import Any

from ..config import settings
from .foundry_definitions import foundry_agent_name

logger = logging.getLogger("ragtrust.foundry")


class FoundryAgentClient:
    _instance: FoundryAgentClient | None = None

    def __init__(self):
        self.project_client = None
        self.openai_client = None
        self.tracing_configured = False
        self._init_client()

    @classmethod
    def get_instance(cls) -> FoundryAgentClient:
        if settings.public_demo:
            raise ValueError("Live Foundry calls are disabled in the public demo")
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_client(self):
        if settings.public_demo:
            return
        if not settings.has_foundry_config:
            logger.info("Microsoft Foundry credentials not provided; operating in fixture mode.")
            return

        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential

            self.project_client = AIProjectClient(
                endpoint=settings.project_connection_string,
                credential=DefaultAzureCredential(),
            )
            self.openai_client = self.project_client.get_openai_client()
            logger.info("Successfully connected to Microsoft Foundry project.")
            self._setup_tracing()
        except Exception as e:
            logger.warning(f"Could not connect to live Microsoft Foundry: {e}. Fallback to fixture engine available.")
            self.project_client = None
            self.openai_client = None

    def _setup_tracing(self):
        if self.tracing_configured:
            return
        conn_str = settings.appinsights_connection_string
        if not conn_str:
            return

        try:
            if os.getenv("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING") == "true":
                from azure.ai.projects.telemetry import AIProjectInstrumentor
                from azure.monitor.opentelemetry import configure_azure_monitor

                AIProjectInstrumentor().instrument()
                configure_azure_monitor(connection_string=conn_str, enable_live_metrics=True)
                self.tracing_configured = True
                logger.info("Azure Application Insights GenAI OpenTelemetry tracing configured.")
        except Exception as e:
            logger.warning(f"Failed to initialize Application Insights tracing: {e}")

    def run_agent_chat(
        self,
        agent_name: str,
        system_instructions: str,
        user_input: str,
        json_output: bool = True,
    ) -> str:
        """
        Runs an agent with system instructions against Azure AI Foundry models.
        """
        if settings.public_demo:
            raise ValueError("Live Foundry calls are disabled in the public demo")
        if not self.openai_client:
            raise RuntimeError("Live Microsoft Foundry client is not available. Check Azure credentials and settings.")

        # Create conversation and response using the Microsoft Foundry Responses API.
        # In deployed-agent mode the server-side, named prompt-agent definition owns
        # the system instructions. This keeps runtime behavior tied to an auditable
        # Foundry version rather than repeating an ephemeral prompt on every call.
        conversation = self.openai_client.conversations.create()
        try:
            if settings.use_deployed_agents:
                prompt = user_input
                if json_output:
                    prompt += "\n\nReturn only JSON that matches your configured schema."
                response = self.openai_client.responses.create(
                    input=prompt,
                    conversation=conversation.id,
                    extra_body={
                        "agent_reference": {
                            "name": foundry_agent_name(agent_name),
                            "type": "agent_reference",
                            **({"version": settings.agent_version} if settings.agent_version else {}),
                        }
                    },
                )
            else:
                full_prompt = f"SYSTEM INSTRUCTIONS:\n{system_instructions}\n\nUSER REQUEST:\n{user_input}"
                if json_output:
                    full_prompt += "\n\nCRITICAL: Respond ONLY with valid JSON matching the requested schema."
                response = self.openai_client.responses.create(
                    input=full_prompt,
                    conversation=conversation.id,
                    model=settings.model_deployment_name,
                )
            return response.output_text
        finally:
            try:
                self.openai_client.conversations.delete(conversation_id=conversation.id)
            except Exception:
                pass
