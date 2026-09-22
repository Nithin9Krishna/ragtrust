from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class CaseStatus(StrEnum):
    generated = "generated"
    checking = "checking"
    accepted = "accepted"
    needs_revision = "needs_revision"
    needs_review = "needs_review"
    rejected = "rejected"


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    completed_shortfall = "completed_shortfall"
    cancelled = "cancelled"
    failed = "failed"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    domain: str = "general"


class SourceMapping(BaseModel):
    question_col: str = "question"
    answer_col: str = "answer"
    topic_col: str | None = "topic"
    evidence_col: str | None = "evidence_ref"
    id_col: str | None = "id"


class GoldenExampleCreate(BaseModel):
    external_id: str
    question: str
    trusted_answer: str
    topic: str = "general"
    evidence_ref: str | None = None
    benchmark_role: str = "seed"  # 'seed' | 'calibration' | 'held_out'
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class GenerationConfig(BaseModel):
    candidate_target: int = Field(default=12, ge=1, le=1000)
    accepted_target: int = Field(default=8, ge=1, le=1000)
    max_repairs: int = Field(default=2, ge=0, le=5)
    budget_units: int = Field(default=50, ge=1, le=10000)
    language: str = "English"
    objective: str = Field(default="representative", pattern="^(representative|stress_test)$")
    topic_quotas: dict[str, int] = Field(default_factory=dict)
    difficulty_mix: dict[str, float] = Field(default_factory=lambda: {"easy": 0.5, "medium": 0.4, "hard": 0.1})
    question_types: list[str] = Field(
        default_factory=lambda: ["direct", "paraphrase", "comparison", "multi_step", "unanswerable"]
    )
    demo_fault_injection: bool = False

    @model_validator(mode="after")
    def targets_are_consistent(self):
        if self.accepted_target > self.candidate_target:
            raise ValueError("accepted_target cannot exceed candidate_target")
        if abs(sum(self.difficulty_mix.values()) - 1.0) > 0.02:
            raise ValueError("difficulty_mix must sum to 1.0")
        return self


class CoveragePlan(BaseModel):
    domain: str
    topics: list[str]
    topic_quotas: dict[str, int]
    difficulty_mix: dict[str, float]
    question_types: list[str]
    detected_gaps: list[str] = Field(default_factory=list)
    source_conflicts: list[str] = Field(default_factory=list)
    total_planned: int


class CandidatePayload(BaseModel):
    question: str
    candidate_reference_answer: str
    expected_behavior: str = Field(default="answer", pattern="^(answer|clarify|abstain)$")
    topic: str
    scenario_type: str
    difficulty: str
    modality: str = "text"
    seed_ids: list[str] = Field(default_factory=list)
    source_version_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)
    reference_origin: str = "automatically_derived"


class ClaimAssessment(BaseModel):
    claim_text: str
    is_supported: bool
    evidence_id: str | None = None
    citation_valid: bool = True
    contradiction: bool = False
    reason: str = ""


class VerificationOutput(BaseModel):
    faithfulness_score: float
    factual_precision: float
    factual_recall: float
    factual_f1: float
    completeness_score: float
    relevance_score: float
    answerability_score: float
    citation_valid: bool
    claims: list[ClaimAssessment]
    failed_claims: list[str] = Field(default_factory=list)
    suggested_status: CaseStatus
    concise_reason: str


class ReviewInput(BaseModel):
    decision: str = Field(pattern="^(approve|reject|correct)$")
    corrected_answer: str | None = None
    notes: str = ""


class MetricResult(BaseModel):
    name: str
    score: float | None
    scale: str = "0_to_1"
    applicability: str = "assessed"
    reason: str
    failed_claims: list[str] = Field(default_factory=list)
    metric_version: str = "ragtrust-deterministic-1.0"
    evaluator_version: str = "fixture-rules-1.0"


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus
    generated: int
    accepted: int
    rejected: int
    needs_review: int
    needs_revision: int
    repairs: int
    accepted_target: int
    shortfall: int
    limitations: list[str] = Field(default_factory=list)
    completed_at: datetime | None = None
    dataset_metrics: dict[str, Any] = Field(default_factory=dict)


class CalibrationResult(BaseModel):
    total_cases: int
    accuracy: float
    defect_precision: float
    defect_recall: float
    defect_f1: float
    cohens_kappa: float
    confusion_matrix: dict[str, int]
    details: list[dict[str, Any]] = Field(default_factory=list)


class RagEvalRequest(BaseModel):
    endpoint_url: str | None = None
    endpoint_label: str = "mock-production-rag"
    mock_responses: dict[str, str] = Field(default_factory=dict)


class RagEvalSummary(BaseModel):
    total_cases_evaluated: int
    avg_faithfulness: float
    avg_relevance: float
    abstention_accuracy: float
    avg_latency_ms: float
    results: list[dict[str, Any]] = Field(default_factory=list)
