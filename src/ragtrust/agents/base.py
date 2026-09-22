from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.total_calls = 0
        self.total_tokens_est = 0
        self.total_latency_ms = 0.0

    def record_usage(self, latency_ms: float, tokens_est: int = 100):
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        self.total_tokens_est += tokens_est

    @abstractmethod
    def run(self, inputs: dict[str, Any], mode: str = "fixture") -> dict[str, Any]:
        """Execute the agent task in either fixture or foundry mode."""
        pass
