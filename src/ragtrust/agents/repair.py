from __future__ import annotations

import json
import time
from typing import Any

from ..schemas import CaseStatus
from .base import BaseAgent
from .foundry_client import FoundryAgentClient


class RefinementRepairAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="CoverageAndRefinementAgent", role="Targeted Case Repair and Coverage Refinement")

    def run(self, inputs: dict[str, Any], mode: str = "fixture") -> dict[str, Any]:
        """
        Inputs:
        - candidate: dict containing question, candidate_reference_answer, evidence_refs, attempt_number
        - failed_claims: list[str]
        - evidence_segments: list[dict]
        - max_repairs: int (default 2)
        """
        start = time.time()
        candidate = inputs.get("candidate", {})
        failed_claims = inputs.get("failed_claims", [])
        evidence_segments = inputs.get("evidence_segments", [])
        max_repairs = inputs.get("max_repairs", 2)
        current_attempt = candidate.get("attempt_number", 0)

        # Enforce bounded retry policy
        if current_attempt >= max_repairs:
            latency = (time.time() - start) * 1000
            self.record_usage(latency, tokens_est=20)
            return {
                "repaired": False,
                "reason": f"Exhausted repair limit ({max_repairs} attempts). Routed to human review.",
                "status": CaseStatus.needs_review,
                "candidate": candidate,
            }

        if mode == "foundry":
            res = self._run_foundry(candidate, failed_claims, evidence_segments, current_attempt)
            latency = (time.time() - start) * 1000
            self.record_usage(latency, tokens_est=300)
            return res

        res = self._run_fixture(candidate, failed_claims, evidence_segments, current_attempt)
        latency = (time.time() - start) * 1000
        self.record_usage(latency, tokens_est=50)
        return res

    def _run_fixture(
        self,
        candidate: dict[str, Any],
        failed_claims: list[str],
        evidence_segments: list[dict[str, Any]],
        current_attempt: int,
    ) -> dict[str, Any]:
        old_answer = candidate.get("candidate_reference_answer", "")
        # Remove sentences that failed verification
        repaired_sentences = []
        for s in old_answer.split(". "):
            if not any(f.lower() in s.lower() for f in failed_claims):
                repaired_sentences.append(s.strip())

        # If answer was stripped empty, pull directly from evidence
        if not repaired_sentences and evidence_segments:
            seg = evidence_segments[0]
            new_answer = f"According to policy: {seg.get('text', '')[:140]}."
            candidate["evidence_refs"] = [seg.get("locator")]
        else:
            new_answer = ". ".join(repaired_sentences)
            if not new_answer.endswith("."):
                new_answer += "."

        repaired_candidate = dict(candidate)
        repaired_candidate["candidate_reference_answer"] = new_answer
        repaired_candidate["attempt_number"] = current_attempt + 1
        repaired_candidate["parent_attempt_id"] = candidate.get("id")

        return {
            "repaired": True,
            "status": CaseStatus.checking,
            "reason": f"Excised {len(failed_claims)} unsupported claim(s).",
            "candidate": repaired_candidate,
        }

    def _run_foundry(
        self,
        candidate: dict[str, Any],
        failed_claims: list[str],
        evidence_segments: list[dict[str, Any]],
        current_attempt: int,
    ) -> dict[str, Any]:
        client = FoundryAgentClient.get_instance()
        system_prompt = """
You are the Coverage & Refinement Repair Agent for RAGTrust.
Revise the candidate answer by strictly removing the failed/unsupported claims and replacing them with verified facts from the evidence.
Ensure all cited references exist.
Return ONLY valid JSON:
{
  "repaired": true,
  "repaired_answer": "string",
  "updated_evidence_refs": ["string"],
  "reason": "string"
}
"""
        user_input = json.dumps(
            {
                "question": candidate.get("question"),
                "original_answer": candidate.get("candidate_reference_answer"),
                "failed_claims": failed_claims,
                "evidence_segments": [
                    {"locator": s.get("locator"), "text": s.get("text")[:300]}
                    for s in evidence_segments[:6]
                ],
            }
        )
        raw_output = client.run_agent_chat("RepairAgent", system_prompt, user_input)
        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        data = json.loads(cleaned)

        repaired_candidate = dict(candidate)
        repaired_candidate["candidate_reference_answer"] = data.get("repaired_answer", candidate.get("candidate_reference_answer"))
        if data.get("updated_evidence_refs"):
            repaired_candidate["evidence_refs"] = data["updated_evidence_refs"]
        repaired_candidate["attempt_number"] = current_attempt + 1
        repaired_candidate["parent_attempt_id"] = candidate.get("id")

        return {
            "repaired": True,
            "status": CaseStatus.checking,
            "reason": data.get("reason", "Repaired via Foundry model"),
            "candidate": repaired_candidate,
        }
