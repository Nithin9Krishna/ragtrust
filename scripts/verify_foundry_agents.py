#!/usr/bin/env python3
"""Smoke-test every persisted RAGTrust Foundry prompt agent."""

from __future__ import annotations

import json

from ragtrust.agents.foundry_client import FoundryAgentClient


REQUESTS = {
    "PlanningAgent": {
        "domain": "IT security",
        "candidate_target": 1,
        "golden_examples": [{"question": "When are access reviews required?", "topic": "access", "answer": "Quarterly."}],
        "evidence_snippets": ["Access reviews are required quarterly."],
    },
    "GenerationAgent": {
        "target_count": 1,
        "plan": {"topics": ["access"], "topic_quotas": {"access": 1}},
        "evidence_snippets": [{"id": "e1", "locator": "policy.txt:p1", "text": "Access reviews are required quarterly."}],
    },
    "ValidationAgent": {
        "question": "When are access reviews required?",
        "candidate_reference_answer": "Access reviews are required quarterly.",
        "expected_behavior": "answer",
        "evidence_segments": [{"locator": "policy.txt:p1", "text": "Access reviews are required quarterly."}],
        "evidence_refs": ["policy.txt:p1"],
        "required_facts": ["quarterly"],
    },
    "RepairAgent": {
        "question": "When are access reviews required?",
        "original_answer": "Access reviews are required monthly.",
        "failed_claims": ["Access reviews are required monthly."],
        "evidence_segments": [{"locator": "policy.txt:p1", "text": "Access reviews are required quarterly."}],
    },
}


def main() -> None:
    client = FoundryAgentClient.get_instance()
    if not client.openai_client:
        raise SystemExit("Foundry client is unavailable")

    results: dict[str, object] = {}
    for role, payload in REQUESTS.items():
        raw = client.run_agent_chat(role, "", json.dumps(payload))
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        results[role] = json.loads(cleaned)
    print(json.dumps({"status": "passed", "agents": results}, indent=2))


if __name__ == "__main__":
    main()
