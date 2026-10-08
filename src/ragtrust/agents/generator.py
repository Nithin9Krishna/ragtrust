from __future__ import annotations

import json
import time
from typing import Any

from ..schemas import CandidatePayload
from .base import BaseAgent
from .foundry_client import FoundryAgentClient


class GenerationAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="GenerationAgent", role="Candidate Case Generation")

    def run(self, inputs: dict[str, Any], mode: str = "fixture") -> list[dict[str, Any]]:
        start = time.time()
        plan = inputs.get("plan", {})
        golden_examples = inputs.get("golden_examples", [])
        evidence_segments = inputs.get("evidence_segments", [])
        count = inputs.get("count", plan.get("total_planned", 10))

        if mode == "foundry":
            candidates = self._run_foundry(plan, golden_examples, evidence_segments, count)
            latency = (time.time() - start) * 1000
            self.record_usage(latency, tokens_est=count * 350)
            return candidates

        candidates = self._run_fixture(plan, golden_examples, evidence_segments, count)
        latency = (time.time() - start) * 1000
        self.record_usage(latency, tokens_est=count * 100)
        return candidates

    def _run_fixture(
        self,
        plan: dict[str, Any],
        golden_examples: list[dict[str, Any]],
        evidence_segments: list[dict[str, Any]],
        count: int,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        topics = plan.get("topics") or ["general"]
        question_types = plan.get("question_types") or ["direct", "paraphrase", "comparison", "multi_step", "unanswerable"]

        # Map segments by modality
        text_segments = [s for s in evidence_segments if s.get("modality") == "text"]
        video_segments = [s for s in evidence_segments if s.get("modality") == "video"]

        for i in range(count):
            topic = topics[i % len(topics)]
            scenario = question_types[i % len(question_types)]
            diff_roll = (i % 10) / 10.0
            difficulty = "easy" if diff_roll < 0.5 else ("medium" if diff_roll < 0.8 else "hard")

            # Link with seed example if available
            seed = golden_examples[i % len(golden_examples)] if golden_examples else None
            seed_ids = [seed.get("id") or seed.get("external_id")] if seed else []

            # Determine modality (e.g. 1 in 5 can be video if video segments exist)
            use_video = bool(video_segments and (i % 4 == 3))
            active_segments = video_segments if use_video else (text_segments or evidence_segments)
            seg = active_segments[i % len(active_segments)] if active_segments else None

            evidence_refs = [seg.get("locator")] if seg else []
            modality = "video" if use_video else "text"

            # Formulate question and reference answer based on scenario
            if scenario == "unanswerable":
                question = f"What is the required compensation package for third-party contractors under the {topic} policy?"
                candidate_answer = "The provided documentation does not specify contractor compensation packages."
                expected_behavior = "abstain"
                required_facts = ["Documentation does not cover contractor compensation"]
            elif scenario == "paraphrase" and seed:
                question = f"Could you clarify: {seed.get('question')}?"
                candidate_answer = seed.get("trusted_answer")
                expected_behavior = "answer"
                required_facts = [seed.get("trusted_answer")[:80]]
            elif scenario == "comparison" and len(evidence_segments) > 1:
                other_seg = evidence_segments[(i + 1) % len(evidence_segments)]
                evidence_refs.append(other_seg.get("locator"))
                question = f"How does the policy described in {evidence_refs[0]} compare with {evidence_refs[1]} regarding compliance requirements?"
                candidate_answer = f"The policy specifies distinct rules: {seg.get('text', '')[:100]} whereas {other_seg.get('text', '')[:100]}."
                expected_behavior = "answer"
                required_facts = [seg.get("text", "")[:50], other_seg.get("text", "")[:50]]
            elif scenario == "multi_step":
                question = f"What are the sequential steps to achieve compliance for {topic} according to the guidelines?"
                candidate_answer = f"First, review the policy terms. Second, follow the established protocol: {seg.get('text', '')[:120]}."
                expected_behavior = "answer"
                required_facts = ["Review policy terms", seg.get("text", "")[:60]]
            else:  # direct
                question = f"According to {topic} regulations, what are the primary operating criteria?"
                candidate_answer = f"According to the documentation: {seg.get('text', 'Operating guidelines apply.')[:140]}."
                expected_behavior = "answer"
                required_facts = [seg.get("text", "")[:80]]

            payload = CandidatePayload(
                question=question,
                candidate_reference_answer=candidate_answer,
                expected_behavior=expected_behavior,
                topic=topic,
                scenario_type=scenario,
                difficulty=difficulty,
                modality=modality,
                seed_ids=seed_ids,
                source_version_ids=[seg["source_asset_id"]] if seg and seg.get("source_asset_id") else [],
                evidence_refs=evidence_refs,
                required_facts=required_facts,
                reference_origin="automatically_derived",
            )
            candidates.append(payload.model_dump())

        return candidates

    def _run_foundry(
        self,
        plan: dict[str, Any],
        golden_examples: list[dict[str, Any]],
        evidence_segments: list[dict[str, Any]],
        count: int,
    ) -> list[dict[str, Any]]:
        client = FoundryAgentClient.get_instance()
        system_prompt = """
You are the Generation Agent for RAGTrust.
Generate diverse, high-quality RAG evaluation cases grounded strictly in the provided evidence.
Output JSON list of objects matching:
[
  {
    "question": "string",
    "candidate_reference_answer": "string",
    "expected_behavior": "answer" | "clarify" | "abstain",
    "topic": "string",
    "scenario_type": "direct" | "paraphrase" | "comparison" | "multi_step" | "unanswerable",
    "difficulty": "easy" | "medium" | "hard",
    "modality": "text" | "video",
    "seed_ids": ["string"],
    "source_version_ids": ["string"],
    "evidence_refs": ["string"],
    "required_facts": ["string"],
    "reference_origin": "automatically_derived"
  }
]
"""
        user_input = json.dumps(
            {
                "target_count": count,
                "plan": plan,
                "golden_examples": golden_examples[:20],
                "evidence_snippets": [
                    {"id": s.get("id"), "locator": s.get("locator"), "source_asset_id": s.get("source_asset_id"), "modality": s.get("modality", "text"), "text": s.get("text", "")[:2000]}
                    for s in evidence_segments[:24]
                ],
            }
        )
        raw_output = client.run_agent_chat("GenerationAgent", system_prompt, user_input)
        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        candidates = json.loads(cleaned)

        # The verifier's citation contract uses immutable human-readable locators.
        # Models occasionally copy a segment ID into evidence_refs even when both
        # fields are supplied, so normalize known IDs at this trust boundary.
        id_to_locator = {
            str(segment.get("id")): segment.get("locator")
            for segment in evidence_segments
            if segment.get("id") and segment.get("locator")
        }
        for candidate in candidates:
            candidate["evidence_refs"] = [
                id_to_locator.get(str(reference), reference)
                for reference in candidate.get("evidence_refs", [])
            ]
            cited = set(candidate["evidence_refs"])
            candidate["source_version_ids"] = sorted({
                str(s["source_asset_id"]) for s in evidence_segments
                if s.get("locator") in cited and s.get("source_asset_id")
            })
            seed_ids = {str(g.get("id")) for g in golden_examples}
            candidate["seed_ids"] = [str(s) for s in candidate.get("seed_ids", []) if str(s) in seed_ids]
            candidate["reference_origin"] = "automatically_derived"
        return [CandidatePayload.model_validate(candidate).model_dump() for candidate in candidates[:count]]
