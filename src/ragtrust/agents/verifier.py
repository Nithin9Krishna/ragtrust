from __future__ import annotations

import json
import re
import time
from typing import Any

from ..schemas import CaseStatus, ClaimAssessment, VerificationOutput
from ..services.deterministic import DeterministicQualityEngine
from .base import BaseAgent
from .foundry_client import FoundryAgentClient


class ValidationAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="ValidationAgent", role="Independent Case Validation and Claim Verification")

    def run(self, inputs: dict[str, Any], mode: str = "fixture") -> dict[str, Any]:
        """
        Inputs MUST contain:
        - question
        - candidate_reference_answer
        - evidence_segments (list of relevant text/video segments)
        - evidence_refs (cited locators)
        - expected_behavior ('answer' | 'abstain' | 'clarify')
        - valid_locators (set of all known valid locators in project)
        - required_facts (optional checklist)

        DOES NOT RECEIVE GENERATOR SELF-SCORE OR RATIONALE.
        """
        start = time.time()
        if mode == "foundry":
            res = self._run_foundry(inputs)
            res = self.enforce_evidence_contract(inputs, res)
            latency = (time.time() - start) * 1000
            self.record_usage(latency, tokens_est=450)
            return res

        res = self._run_fixture(inputs)
        res = self.enforce_evidence_contract(inputs, res)
        latency = (time.time() - start) * 1000
        self.record_usage(latency, tokens_est=80)
        return res

    @staticmethod
    def enforce_evidence_contract(inputs: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        """A model cannot override missing evidence, invalid citations, or its own failed claims."""
        # Some Foundry judges return structured failure explanations. Preserve all
        # fields as text; never drop the failure or turn it into a passing claim.
        output = {**output, "failed_claims": [
            json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else item
            for item in output.get("failed_claims", [])
        ]}
        result = VerificationOutput.model_validate(output).model_dump()
        refs = inputs.get("evidence_refs", [])
        valid = set(inputs.get("valid_locators", []))
        invalid = [ref for ref in refs if ref not in valid]
        answerable = inputs.get("expected_behavior", "answer") == "answer"
        absent = answerable and (not refs or not inputs.get("evidence_segments"))
        if inputs.get("expected_behavior") == "abstain" and not refs:
            result["citation_valid"] = True
        if invalid or absent:
            result["citation_valid"] = False
            result["suggested_status"] = CaseStatus.rejected
            result["failed_claims"].append("Missing supporting evidence or invalid citation locator.")
            result["concise_reason"] = "Rejected by deterministic evidence checks."
        elif result["suggested_status"] == CaseStatus.accepted and (
            not result["citation_valid"] or result["failed_claims"]
            or any(not c["is_supported"] or c["contradiction"] for c in result["claims"])
        ):
            result["suggested_status"] = CaseStatus.needs_revision
            result["concise_reason"] = "Revision required: verifier reported unsupported claims or citation failures."
        if answerable and not result["claims"]:
            result["suggested_status"] = CaseStatus.needs_review
            result["concise_reason"] = "No claim assessments returned; manual review is required."
        return result

    def _run_fixture(self, inputs: dict[str, Any]) -> dict[str, Any]:
        question = inputs.get("question", "")
        answer = inputs.get("candidate_reference_answer", "")
        evidence_segments = inputs.get("evidence_segments", [])
        evidence_refs = inputs.get("evidence_refs", [])
        expected_behavior = inputs.get("expected_behavior", "answer")
        valid_locators = set(inputs.get("valid_locators", []))
        required_facts = inputs.get("required_facts", [])

        # Step 1: Citation existence check
        citations_ok, invalid_citations = DeterministicQualityEngine.validate_citations(
            evidence_refs, valid_locators
        ) if valid_locators else (True, [])

        # Aggregate evidence text
        evidence_corpus = " ".join(s.get("text", "") for s in evidence_segments).lower()

        # Step 2: Claim extraction
        # Decompose answer into clauses/sentences
        raw_sentences = [s.strip() for s in re.split(r"[.!?]\s+", answer) if len(s.strip()) > 5]
        if not raw_sentences:
            raw_sentences = [answer.strip()] if answer.strip() else []

        claims: list[ClaimAssessment] = []
        supported_count = 0
        failed_claims = []

        # Handle unanswerable / abstention cases
        if expected_behavior == "abstain":
            abstains_well = any(w in answer.lower() for w in ["not specify", "does not cover", "not provide", "no information", "cannot be determined"])
            if abstains_well:
                output = VerificationOutput(
                    faithfulness_score=1.0,
                    factual_precision=1.0,
                    factual_recall=1.0,
                    factual_f1=1.0,
                    completeness_score=1.0,
                    relevance_score=1.0,
                    answerability_score=1.0,
                    citation_valid=citations_ok,
                    claims=[
                        ClaimAssessment(
                            claim_text="Properly abstains from answering out-of-scope query.",
                            is_supported=True,
                            reason="Question is unanswerable from evidence and answer correctly declines.",
                        )
                    ],
                    suggested_status=CaseStatus.accepted,
                    concise_reason="Valid abstention: correctly declines out-of-scope query with verified evidence citation.",
                )
                return output.model_dump()
            else:
                output = VerificationOutput(
                    faithfulness_score=0.0,
                    factual_precision=0.0,
                    factual_recall=0.0,
                    factual_f1=0.0,
                    completeness_score=0.0,
                    relevance_score=0.2,
                    answerability_score=0.0,
                    citation_valid=citations_ok,
                    claims=[
                        ClaimAssessment(
                            claim_text=answer,
                            is_supported=False,
                            contradiction=True,
                            reason="Hallucinated answer for unanswerable question.",
                        )
                    ],
                    failed_claims=["Failed to abstain on unanswerable query."],
                    suggested_status=CaseStatus.rejected,
                    concise_reason="Failed abstention: provided affirmative claims when evidence does not support query.",
                )
                return output.model_dump()

        # Step 3: Verify each claim against evidence
        for sentence in raw_sentences:
            words = set(re.findall(r"\w+", sentence.lower()))
            # Remove common stop words for matching
            meaningful_words = [w for w in words if len(w) > 3 and w not in {"according", "documentation", "described", "provides", "policy"}]
            
            if not meaningful_words:
                claims.append(ClaimAssessment(claim_text=sentence, is_supported=True, reason="Grammatical/connective sentence."))
                supported_count += 1
                continue

            # Check overlap with evidence corpus
            matches = [w for w in meaningful_words if w in evidence_corpus]
            overlap_ratio = len(matches) / len(meaningful_words) if meaningful_words else 0.0

            # Check numbers: any sequence of digits in sentence should appear in evidence corpus
            sentence_numbers = set(re.findall(r"\b\d+\b", sentence))
            evidence_numbers = set(re.findall(r"\b\d+\b", evidence_corpus))
            unsupported_numbers = sentence_numbers - evidence_numbers

            # Check unsupported strong terms
            unsupported_terms = [
                t for t in ["free", "indefinitely", "lifetime", "complimentary", "reimbursable", "pet insurance", "unlimited"]
                if t in sentence.lower() and t not in evidence_corpus
            ]

            contradicts = bool(unsupported_numbers) or bool(unsupported_terms)
            is_supported = (overlap_ratio >= 0.40) and not contradicts

            if is_supported:
                supported_count += 1
                claims.append(
                    ClaimAssessment(
                        claim_text=sentence,
                        is_supported=True,
                        citation_valid=citations_ok,
                        reason=f"Supported by evidence ({len(matches)} matching terms).",
                    )
                )
            else:
                failed_claims.append(sentence)
                claims.append(
                    ClaimAssessment(
                        claim_text=sentence,
                        is_supported=False,
                        contradiction=contradicts,
                        citation_valid=citations_ok,
                        reason="Claim contains unsupported facts not present in cited evidence.",
                    )
                )

        total_claims = len(claims)
        faithfulness = DeterministicQualityEngine.calculate_faithfulness(supported_count, total_claims)

        # Completeness check against required_facts
        covered_facts = 0
        for fact in required_facts:
            fact_words = [w for w in re.findall(r"\w+", fact.lower()) if len(w) > 3]
            if any(w in answer.lower() for w in fact_words):
                covered_facts += 1
        completeness = covered_facts / len(required_facts) if required_facts else 1.0

        # Factual precision, recall, f1
        f1_dict = DeterministicQualityEngine.calculate_factual_f1(
            tp=supported_count,
            fp=total_claims - supported_count,
            fn=max(0, len(required_facts) - covered_facts),
        )

        # Determine status
        reasons = []
        if not citations_ok:
            reasons.append(f"Invalid citations: {invalid_citations}")
        if failed_claims:
            reasons.append(f"{len(failed_claims)} unsupported claim(s)")

        if not citations_ok or (faithfulness < 0.60):
            suggested_status = CaseStatus.rejected
            concise_reason = f"Hard rejection: {'; '.join(reasons)}"
        elif failed_claims or completeness < 0.70:
            suggested_status = CaseStatus.needs_revision
            concise_reason = f"Revision needed: {'; '.join(reasons)}"
        else:
            suggested_status = CaseStatus.accepted
            concise_reason = f"Verified: {supported_count}/{total_claims} claims supported with valid citations."

        output = VerificationOutput(
            faithfulness_score=faithfulness,
            factual_precision=f1_dict["precision"],
            factual_recall=f1_dict["recall"],
            factual_f1=f1_dict["f1"],
            completeness_score=round(completeness, 4),
            relevance_score=0.95,
            answerability_score=1.0,
            citation_valid=citations_ok,
            claims=claims,
            failed_claims=failed_claims,
            suggested_status=suggested_status,
            concise_reason=concise_reason,
        )
        return output.model_dump()

    def _run_foundry(self, inputs: dict[str, Any]) -> dict[str, Any]:
        client = FoundryAgentClient.get_instance()
        system_prompt = """
You are the Independent Validation Agent for RAGTrust.
Analyze the candidate answer STRICTLY against the provided evidence snippets.
Decompose the answer into atomic claims.
For each claim, verify if it is supported or unsupported.
Check if citations are valid and accurate.
Return ONLY valid JSON matching:
{
  "faithfulness_score": float (0.0 to 1.0),
  "factual_precision": float,
  "factual_recall": float,
  "factual_f1": float,
  "completeness_score": float,
  "relevance_score": float,
  "answerability_score": float,
  "citation_valid": bool,
  "claims": [
    {
      "claim_text": "string",
      "is_supported": bool,
      "evidence_id": "string",
      "citation_valid": bool,
      "contradiction": bool,
      "reason": "string"
    }
  ],
  "failed_claims": ["string"],
  "suggested_status": "accepted" | "needs_revision" | "needs_review" | "rejected",
  "concise_reason": "string"
}
"""
        user_input = json.dumps(
            {
                "question": inputs.get("question"),
                "candidate_reference_answer": inputs.get("candidate_reference_answer"),
                "expected_behavior": inputs.get("expected_behavior"),
                "evidence_segments": [
                    {"locator": s.get("locator"), "text": s.get("text", "")[:4000]}
                    for s in inputs.get("evidence_segments", [])
                ],
                "evidence_refs": inputs.get("evidence_refs", []),
                "required_facts": inputs.get("required_facts", []),
                "valid_locators": sorted(inputs.get("valid_locators", [])),
            }
        )
        raw_output = client.run_agent_chat("ValidationAgent", system_prompt, user_input)
        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        # run() normalizes failure explanations and validates the complete
        # evidence contract. Do not validate before that normalization boundary.
        return json.loads(cleaned)
