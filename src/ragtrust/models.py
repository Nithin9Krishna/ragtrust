from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(120), default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SourceAsset(Base):
    __tablename__ = "source_assets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(120))
    storage_path: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    extraction_status: Mapped[str] = mapped_column(String(60), default="pending")
    extraction_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EvidenceSegment(Base):
    __tablename__ = "evidence_segments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("source_assets.id"), index=True)
    locator: Mapped[str] = mapped_column(String(300))
    modality: Mapped[str] = mapped_column(String(30), default="text")
    text: Mapped[str] = mapped_column(Text, default="")
    start_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class GoldenExample(Base):
    __tablename__ = "golden_examples"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    question: Mapped[str] = mapped_column(Text)
    trusted_answer: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(200), default="general")
    evidence_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    benchmark_role: Mapped[str] = mapped_column(String(30), default="seed")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("project_id", "external_id"),)


class GenerationRun(Base):
    __tablename__ = "generation_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued")
    config_json: Mapped[dict] = mapped_column(JSON)
    plan_json: Mapped[dict] = mapped_column(JSON, default=dict)
    progress_json: Mapped[dict] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(30), default="fixture")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CandidateCase(Base):
    __tablename__ = "candidate_cases"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    parent_attempt_id: Mapped[str | None] = mapped_column(ForeignKey("candidate_cases.id"), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=0)
    question: Mapped[str] = mapped_column(Text)
    candidate_reference_answer: Mapped[str] = mapped_column(Text)
    expected_behavior: Mapped[str] = mapped_column(String(30), default="answer")
    topic: Mapped[str] = mapped_column(String(200))
    scenario_type: Mapped[str] = mapped_column(String(80))
    difficulty: Mapped[str] = mapped_column(String(30))
    modality: Mapped[str] = mapped_column(String(30), default="text")
    seed_ids: Mapped[list] = mapped_column(JSON, default=list)
    source_version_ids: Mapped[list] = mapped_column(JSON, default=list)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    required_facts: Mapped[list] = mapped_column(JSON, default=list)
    reference_origin: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(40), default="generated")
    failed_checks: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MetricAssessment(Base):
    __tablename__ = "metric_assessments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("candidate_cases.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(100))
    metric_version: Mapped[str] = mapped_column(String(100))
    evaluator_model_version: Mapped[str] = mapped_column(String(120))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale: Mapped[str] = mapped_column(String(50), default="0_to_1")
    applicability: Mapped[str] = mapped_column(String(40), default="assessed")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    failed_claims: Mapped[list] = mapped_column(JSON, default=list)
    concise_reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("candidate_cases.id"), index=True)
    decision: Mapped[str] = mapped_column(String(30))
    corrected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    reviewer: Mapped[str] = mapped_column(String(120), default="local-user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("generation_runs.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    manifest_json: Mapped[dict] = mapped_column(JSON)
    content_sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(1000))
    immutable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("project_id", "version_number"),)


class QualityReport(Base):
    __tablename__ = "quality_reports"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), unique=True)
    summary_json: Mapped[dict] = mapped_column(JSON)
    html_path: Mapped[str] = mapped_column(String(1000))
    json_path: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RagRun(Base):
    __tablename__ = "rag_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    endpoint_label: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="queued")
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

