from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any

from ..schemas import CoveragePlan, GenerationConfig
from .base import BaseAgent
from .foundry_client import FoundryAgentClient


class PlanningAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="DatasetUnderstandingAgent", role="Dataset Understanding and Planning")

    def run(self, inputs: dict[str, Any], mode: str = "fixture") -> dict[str, Any]:
        start = time.time()
        golden_examples = inputs.get("golden_examples", [])
        evidence_segments = inputs.get("evidence_segments", [])
        config: GenerationConfig = inputs.get("config") or GenerationConfig()
        domain = inputs.get("domain", "general")

        if mode == "foundry":
            plan = self._run_foundry(golden_examples, evidence_segments, config, domain)
            latency = (time.time() - start) * 1000
            self.record_usage(latency, tokens_est=1200)
            return plan

        plan = self._run_fixture(golden_examples, evidence_segments, config, domain)
        latency = (time.time() - start) * 1000
        self.record_usage(latency, tokens_est=200)
        return plan

    def _run_fixture(
        self,
        golden_examples: list[dict[str, Any]],
        evidence_segments: list[dict[str, Any]],
        config: GenerationConfig,
        domain: str,
    ) -> dict[str, Any]:
        # Topic extraction from golden examples
        topic_counts = Counter(ex.get("topic", "general") for ex in golden_examples)
        if not topic_counts:
            topic_counts["general"] = 1

        topics = list(topic_counts.keys())
        total_target = config.candidate_target

        # Formulate quotas
        if config.topic_quotas:
            topic_quotas = config.topic_quotas
        else:
            total_golden = sum(topic_counts.values()) or 1
            raw = {t: (cnt / total_golden) * total_target for t, cnt in topic_counts.items()}
            topic_quotas = {t: int(value) for t, value in raw.items()}
            remaining = total_target - sum(topic_quotas.values())
            ranked = sorted(topics, key=lambda t: (raw[t] - topic_quotas[t], topic_counts[t]), reverse=True)
            for index in range(remaining):
                topic_quotas[ranked[index % len(ranked)]] += 1

        # Conflict and gap detection
        detected_gaps = []
        source_conflicts = []

        # Check for unreferenced topics
        evidence_texts = " ".join(s.get("text", "") for s in evidence_segments).lower()
        for t in topics:
            if t.lower() not in evidence_texts and len(t) > 3:
                detected_gaps.append(f"Topic '{t}' has limited coverage in provided source documents.")

        # Check for conflicts between golden examples and evidence
        for ex in golden_examples[:10]:
            ans = ex.get("trusted_answer", "")
            # Check for conflict cues
            if "not allowed" in ans.lower() and "permitted" in evidence_texts:
                source_conflicts.append(f"Potential conflict on '{ex.get('question')[:50]}': check allowance policy.")

        plan = CoveragePlan(
            domain=domain,
            topics=topics,
            topic_quotas=topic_quotas,
            difficulty_mix=config.difficulty_mix,
            question_types=config.question_types,
            detected_gaps=detected_gaps,
            source_conflicts=source_conflicts,
            total_planned=total_target,
        )
        return plan.model_dump()

    def _run_foundry(
        self,
        golden_examples: list[dict[str, Any]],
        evidence_segments: list[dict[str, Any]],
        config: GenerationConfig,
        domain: str,
    ) -> dict[str, Any]:
        client = FoundryAgentClient.get_instance()
        system_prompt = """
You are the Dataset Understanding & Planning Agent for RAGTrust.
Your responsibility:
1. Profile domain terminology, topics, and styles from golden examples.
2. Cross-reference source evidence to identify factual conflicts or coverage gaps.
3. Propose a balanced generation plan with topic quotas matching the target volume.
Return ONLY valid JSON matching this schema:
{
  "domain": "string",
  "topics": ["string"],
  "topic_quotas": {"topic": int},
  "difficulty_mix": {"easy": float, "medium": float, "hard": float},
  "question_types": ["string"],
  "detected_gaps": ["string"],
  "source_conflicts": ["string"],
  "total_planned": int
}
"""
        user_input = json.dumps(
            {
                "domain": domain,
                "candidate_target": config.candidate_target,
                "golden_examples": [
                    {"question": e.get("question"), "topic": e.get("topic"), "answer": e.get("trusted_answer")}
                    for e in golden_examples[:10]
                ],
                "evidence_snippets": [s.get("text")[:200] for s in evidence_segments[:8]],
            }
        )
        raw_output = client.run_agent_chat("PlanningAgent", system_prompt, user_input)
        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        return json.loads(cleaned)
