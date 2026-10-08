from __future__ import annotations

import json
import logging
import threading
from contextvars import copy_context
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .agents.generator import GenerationAgent
from .agents.planner import PlanningAgent
from .agents.rag_eval import RagEvaluationAgent
from .agents.repair import RefinementRepairAgent
from .agents.verifier import ValidationAgent
from .config import settings
from .db import init_db, session_scope, workspace_data_dir
from .models import (
    CandidateCase,
    DatasetVersion,
    EvidenceSegment,
    GenerationRun,
    GoldenExample,
    MetricAssessment,
    Project,
    QualityReport,
    RagRun,
    ReviewDecision,
    SourceAsset,
    now,
    uid,
)
from .schemas import CandidatePayload, CaseStatus, GenerationConfig, RagEvalRequest, RunStatus
from .services.deterministic import DeterministicQualityEngine
from .services.export import DatasetExporter
from .services.reporting import QualityReportGenerator

logger = logging.getLogger("ragtrust.orchestrator")


class OrchestrationService:
    def __init__(self):
        init_db()
        self.planner = PlanningAgent()
        self.generator = GenerationAgent()
        self.verifier = ValidationAgent()
        self.repairer = RefinementRepairAgent()
        self.rag_evaluator = RagEvaluationAgent()
        self._jobs: dict[str, threading.Thread] = {}

    def enqueue_generation_run(
        self,
        project_id: str,
        config: GenerationConfig,
        mode: str | None = None,
    ) -> str:
        """Create a durable queued run and execute it in a local background worker."""
        run_mode = mode or settings.mode
        if settings.public_demo and run_mode != "fixture":
            raise ValueError("Public demo supports fixture generation only")
        if config.candidate_target > settings.max_candidates:
            raise ValueError(f"candidate_target exceeds configured maximum of {settings.max_candidates}")
        if settings.public_demo and any(worker.is_alive() for worker in self._jobs.values()):
            raise ValueError("Wait for your active generation run to finish before starting another")
        self._jobs = {key: worker for key, worker in self._jobs.items() if worker.is_alive()}
        with session_scope() as session:
            if not session.get(Project, project_id):
                raise ValueError("Project not found")
            run = GenerationRun(
                id=uid(), project_id=project_id, status=RunStatus.queued.value,
                config_json=config.model_dump(), mode=run_mode,
                progress_json={"stage": "queued", "completed": 0},
            )
            session.add(run); session.commit(); run_id = run.id
        context = copy_context()
        worker = threading.Thread(
            target=context.run,
            args=(self._execute_background, run_id, project_id, config, run_mode),
            daemon=True,
            name=f"ragtrust-{run_id[:8]}",
        )
        self._jobs[run_id] = worker; worker.start(); return run_id

    def _execute_background(self, run_id: str, project_id: str, config: GenerationConfig, mode: str) -> None:
        try:
            self.execute_generation_run(project_id, config, mode=mode, existing_run_id=run_id)
        except Exception as exc:
            logger.exception("Generation job %s failed", run_id)
            with session_scope() as session:
                run = session.get(GenerationRun, run_id)
                if run:
                    run.status = RunStatus.failed.value
                    run.error = f"{type(exc).__name__}: {exc}"
                    run.completed_at = now()
                    run.progress_json = {**(run.progress_json or {}), "stage": "failed"}
                    session.commit()

    def cancel_generation_run(self, run_id: str) -> None:
        with session_scope() as session:
            run = session.get(GenerationRun, run_id)
            if not run: raise ValueError("Run not found")
            if run.status in {RunStatus.completed.value, RunStatus.completed_shortfall.value, RunStatus.failed.value}:
                raise ValueError("Run is already terminal")
            run.cancel_requested = True; session.commit()

    def create_project(self, name: str, description: str = "", domain: str = "general") -> str:
        with session_scope() as session:
            p = Project(id=uid(), name=name, description=description, domain=domain)
            session.add(p)
            session.commit()
            return p.id

    def add_golden_examples(self, project_id: str, examples: list[dict[str, Any]]) -> int:
        with session_scope() as session:
            added = 0
            for ex in examples:
                ext_id = ex.get("external_id", uid())
                existing = session.scalar(
                    select(GoldenExample).where(
                        GoldenExample.project_id == project_id,
                        GoldenExample.external_id == ext_id,
                    )
                )
                if not existing:
                    g = GoldenExample(
                        id=uid(),
                        project_id=project_id,
                        external_id=ext_id,
                        question=ex.get("question", ""),
                        trusted_answer=ex.get("trusted_answer", ""),
                        topic=ex.get("topic", "general"),
                        evidence_ref=ex.get("evidence_ref"),
                        benchmark_role=ex.get("benchmark_role", "seed"),
                        metadata_json=ex.get("metadata_json", {}),
                    )
                    session.add(g)
                    added += 1
            session.commit()
            return added

    def add_source_asset(
        self,
        project_id: str,
        filename: str,
        media_type: str,
        content_sha256: str,
        storage_path: str,
        segments: list[dict[str, Any]],
        extraction_status: str = "completed",
        extraction_notes: str | None = None,
    ) -> str:
        with session_scope() as session:
            asset = SourceAsset(
                id=uid(),
                project_id=project_id,
                filename=filename,
                media_type=media_type,
                storage_path=storage_path,
                sha256=content_sha256,
                extraction_status=extraction_status,
                extraction_notes=extraction_notes or f"Extracted {len(segments)} segments.",
            )
            session.add(asset)
            session.flush()

            for seg in segments:
                s = EvidenceSegment(
                    id=uid(),
                    source_asset_id=asset.id,
                    locator=seg.get("locator", f"{filename}:seg"),
                    modality=seg.get("modality", "text"),
                    text=seg.get("text", ""),
                    start_seconds=seg.get("start_seconds"),
                    end_seconds=seg.get("end_seconds"),
                    metadata_json=seg.get("metadata_json", {}),
                )
                session.add(s)

            session.commit()
            return asset.id

    def execute_generation_run(
        self, project_id: str, config: GenerationConfig, mode: str | None = None,
        existing_run_id: str | None = None,
    ) -> str:
        run_mode = mode or settings.mode
        if settings.public_demo and run_mode != "fixture":
            raise ValueError("Public demo supports fixture generation only")
        if run_mode not in {"fixture", "foundry"}:
            raise ValueError("Unknown execution mode")
        if config.candidate_target > settings.max_candidates:
            raise ValueError("candidate_target exceeds configured maximum")
        with session_scope() as session:
            if not session.get(Project, project_id):
                raise ValueError("Project not found")
            if existing_run_id:
                run = session.get(GenerationRun, existing_run_id)
                if not run or run.project_id != project_id:
                    raise ValueError("Queued run not found in this project")
            else:
                run = GenerationRun(id=uid(), project_id=project_id, mode=run_mode,
                    status=RunStatus.queued.value, config_json=config.model_dump())
                session.add(run)
                session.commit()
            run_id = run.id
        try:
            return self._execute_generation_run(project_id, config, run_mode, run_id)
        except Exception as exc:
            with session_scope() as session:
                run = session.get(GenerationRun, run_id)
                run.status = RunStatus.failed.value
                run.error = f"{type(exc).__name__}: {str(exc)[:500]}"
                run.completed_at = now()
                run.progress_json = {**(run.progress_json or {}), "stage": "failed"}
                session.commit()
            raise

    def _execute_generation_run(
        self,
        project_id: str,
        config: GenerationConfig,
        mode: str | None = None,
        existing_run_id: str | None = None,
    ) -> str:
        run_mode = mode or settings.mode
        if config.candidate_target > settings.max_candidates:
            raise ValueError(f"candidate_target exceeds configured maximum of {settings.max_candidates}")
        with session_scope() as session:
            if existing_run_id:
                run = session.get(GenerationRun, existing_run_id)
                if not run: raise ValueError("Queued run not found")
                run.status = RunStatus.running.value; run.started_at = now()
                run.progress_json = {"stage": "running", "completed": 0}
            else:
                run = GenerationRun(
                    id=uid(), project_id=project_id, status=RunStatus.running.value,
                    config_json=config.model_dump(), mode=run_mode, started_at=now(),
                )
                session.add(run)
            session.commit()
            run_id = run.id

        # Fetch golden examples and evidence segments
        with session_scope() as session:
            golden = [
                {"id": g.id, "external_id": g.external_id, "question": g.question, "trusted_answer": g.trusted_answer, "topic": g.topic}
                for g in session.scalars(select(GoldenExample).where(GoldenExample.project_id == project_id, GoldenExample.benchmark_role == "seed")).all()
            ]
            proj = session.get(Project, project_id)
            domain = proj.domain if proj else "general"

            # Fetch segments joined with source assets
            raw_segs = session.execute(
                select(EvidenceSegment, SourceAsset).join(SourceAsset, EvidenceSegment.source_asset_id == SourceAsset.id).where(SourceAsset.project_id == project_id)
            ).all()

            evidence = [
                {
                    "id": seg.id,
                    "source_asset_id": asset.id,
                    "locator": seg.locator,
                    "modality": seg.modality,
                    "text": seg.text,
                    "start_seconds": seg.start_seconds,
                    "end_seconds": seg.end_seconds,
                }
                for seg, asset in raw_segs
            ]

        if not golden:
            raise ValueError("Import at least one golden seed example before generation.")
        if not evidence:
            # Golden-only operation is deliberately restricted to the trusted seed facts.
            evidence = [
                {"id": g["id"], "source_asset_id": None, "locator": f"golden:{g['id']}",
                 "modality": "text", "text": g["trusted_answer"], "start_seconds": None, "end_seconds": None}
                for g in golden
            ]
        valid_locators = {s["locator"] for s in evidence}

        # Step 1: Planning Agent
        plan = self.planner.run(
            {"golden_examples": golden, "evidence_segments": evidence, "config": config, "domain": domain},
            mode=run_mode,
        )

        with session_scope() as session:
            r = session.get(GenerationRun, run_id)
            if r:
                r.plan_json = plan
                session.commit()

        # Step 2: Generation Agent
        generation_count = min(config.candidate_target, max(1, config.budget_units // 2))
        candidates_raw = self.generator.run(
            {"plan": plan, "golden_examples": golden, "evidence_segments": evidence, "count": generation_count},
            mode=run_mode,
        )
        candidates_raw = [CandidatePayload.model_validate(c).model_dump() for c in candidates_raw[:generation_count]]

        # Step 3: Exact Deduplication Check. Assign IDs before checking so duplicate
        # identifiers are stable and actionable rather than empty placeholders.
        for candidate in candidates_raw:
            candidate.setdefault("id", uid())
        exact_dupes, exact_rate = DeterministicQualityEngine.detect_exact_duplicates(candidates_raw)

        # Step 4: Verification & Bounded Repair Loop
        accepted_count = 0
        rejected_count = 0
        review_count = 0
        repairs_count = 0

        created_cases: list[dict[str, Any]] = []

        with session_scope() as session:
            for cand_data in candidates_raw:
                current_run = session.get(GenerationRun, run_id)
                if current_run and current_run.cancel_requested:
                    current_run.status = RunStatus.cancelled.value
                    current_run.completed_at = now()
                    current_run.progress_json = {"stage": "cancelled", "generated": len(created_cases)}
                    session.commit()
                    return run_id
                c_id = cand_data["id"]
                is_exact_dupe = c_id in exact_dupes

                # Run independent Validation Agent
                val_output = self.verifier.run(
                    {
                        "question": cand_data["question"],
                        "candidate_reference_answer": cand_data["candidate_reference_answer"],
                        "expected_behavior": cand_data["expected_behavior"],
                        "evidence_segments": [s for s in evidence if s["locator"] in cand_data.get("evidence_refs", [])] or evidence[:3],
                        "evidence_refs": cand_data.get("evidence_refs", []),
                        "valid_locators": valid_locators,
                        "required_facts": cand_data.get("required_facts", []),
                    },
                    mode=run_mode,
                )

                initial_status = val_output.get("suggested_status", CaseStatus.needs_review)
                if is_exact_dupe:
                    initial_status = CaseStatus.rejected
                    val_output["failed_claims"].append("Exact duplicate detected.")
                    val_output["concise_reason"] = "Rejected: exact duplicate of another candidate."

                final_status = initial_status
                # Every repair is a new linked attempt, followed by independent verification.
                for attempt in range(min(config.max_repairs, settings.max_repairs)):
                    if final_status != CaseStatus.needs_revision:
                        break
                    repairs_count += 1
                    repair_res = self.repairer.run(
                        {
                            "candidate": cand_data,
                            "failed_claims": val_output.get("failed_claims", []),
                            "evidence_segments": evidence,
                            "max_repairs": min(config.max_repairs, settings.max_repairs),
                        },
                        mode=run_mode,
                    )
                    if repair_res.get("repaired"):
                        repaired_cand = repair_res["candidate"]
                        # Re-verify repaired candidate
                        reval_output = self.verifier.run(
                            {
                                "question": repaired_cand["question"],
                                "candidate_reference_answer": repaired_cand["candidate_reference_answer"],
                                "expected_behavior": repaired_cand["expected_behavior"],
                                "evidence_segments": [s for s in evidence if s["locator"] in repaired_cand.get("evidence_refs", [])] or evidence[:3],
                                "evidence_refs": repaired_cand.get("evidence_refs", []),
                                "valid_locators": valid_locators,
                                "required_facts": repaired_cand.get("required_facts", []),
                            },
                            mode=run_mode,
                        )
                        # Preserve the original failed attempt before creating a linked revision.
                        self._persist_case_and_metrics(
                            session, c_id, run_id, project_id, cand_data,
                            final_status, val_output, run_mode,
                        )
                        repaired_from_id = c_id
                        c_id = uid()
                        cand_data = repaired_cand
                        cand_data["id"] = c_id
                        cand_data["parent_attempt_id"] = repaired_from_id
                        cand_data["attempt_number"] = int(repaired_cand.get("attempt_number", 1))
                        val_output = reval_output
                        final_status = reval_output.get("suggested_status", CaseStatus.needs_review)
                    else:
                        final_status = repair_res.get("status", CaseStatus.needs_review)
                        break
                if final_status == CaseStatus.needs_revision:
                    final_status = CaseStatus.needs_review
                    val_output["concise_reason"] += " Repair budget exhausted; manual review required."

                # Track counters
                if final_status == CaseStatus.accepted:
                    accepted_count += 1
                elif final_status == CaseStatus.rejected:
                    rejected_count += 1
                else:
                    review_count += 1

                self._persist_case_and_metrics(
                    session, c_id, run_id, project_id, cand_data,
                    final_status, val_output, run_mode,
                )

                created_cases.append(
                    {
                        "id": c_id,
                        "question": cand_data["question"],
                        "candidate_reference_answer": cand_data["candidate_reference_answer"],
                        "expected_behavior": cand_data["expected_behavior"],
                        "topic": cand_data["topic"],
                        "scenario_type": cand_data["scenario_type"],
                        "difficulty": cand_data["difficulty"],
                        "modality": cand_data.get("modality", "text"),
                        "status": final_status.value if hasattr(final_status, "value") else str(final_status),
                        "evidence_refs": cand_data.get("evidence_refs", []),
                        "seed_ids": cand_data.get("seed_ids", []),
                        "metrics": {
                            "faithfulness": {"score": val_output.get("faithfulness_score")},
                            "factual_correctness": {"score": val_output.get("factual_f1")},
                            "completeness": {"score": val_output.get("completeness_score")},
                        },
                        "failed_checks": val_output.get("failed_claims", []),
                        "concise_reason": val_output.get("concise_reason", ""),
                    }
                )
                current_run.progress_json = {"stage": "verifying", "generated": len(created_cases),
                    "accepted": accepted_count, "rejected": rejected_count, "needs_review": review_count,
                    "repairs": repairs_count}
                session.commit()

            session.commit()

        # Step 5: Dataset-level evaluation
        topic_coverage = DeterministicQualityEngine.evaluate_topic_coverage(
            [c["topic"] for c in created_cases if c["status"] == CaseStatus.accepted.value],
            plan.get("topic_quotas", {}),
        )
        semantic_dupes = DeterministicQualityEngine.detect_semantic_duplicates(created_cases)

        # Jensen-Shannon divergence
        target_topic_dist = {t: float(q) for t, q in plan.get("topic_quotas", {}).items()}
        actual_topic_dist = {t: float(d["actual"]) for t, d in topic_coverage.get("breakdown", {}).items()}
        js_dist = DeterministicQualityEngine.compute_jensen_shannon_divergence(target_topic_dist, actual_topic_dist)

        accepted_with_scores = [
            c for c in created_cases
            if c["status"] == CaseStatus.accepted.value
            and c["metrics"]["faithfulness"]["score"] is not None
        ]
        avg_faithfulness = (
            sum(c["metrics"]["faithfulness"]["score"] for c in accepted_with_scores)
            / len(accepted_with_scores)
            if accepted_with_scores
            else None
        )

        dataset_metrics = {
            "topic_coverage": topic_coverage,
            "exact_duplicate_rate": exact_rate,
            "semantic_duplicate_pairs": semantic_dupes,
            "jensen_shannon_divergence": js_dist,
            "avg_faithfulness": round(avg_faithfulness, 4) if avg_faithfulness is not None else None,
            "coverage_population": "accepted final attempts",
            "similarity_method": "lexical n-gram cosine heuristic; not calibrated semantic embeddings",
            "metric_evaluated_count": len(accepted_with_scores),
        }

        # Step 6: Determine Run Status
        shortfall = max(0, config.accepted_target - accepted_count)
        if shortfall > 0:
            final_run_status = RunStatus.completed_shortfall
            limitations = [
                f"Accepted target was {config.accepted_target}, but only {accepted_count} passed validation. "
                "Quality thresholds were preserved without silent weakening."
            ]
            if generation_count < config.candidate_target:
                limitations.append(
                    f"The configured budget allowed {generation_count} candidates instead of the requested {config.candidate_target}; the target was not silently relaxed."
                )
        else:
            final_run_status = RunStatus.completed
            limitations = [
                "Dataset was generated from provided golden seeds and evidence.",
                "Faithfulness is an automated estimate of support based on extracted evidence.",
            ]

        progress_summary = {
            "run_id": run_id,
            "project_id": project_id,
            "generated": len(created_cases),
            "accepted": accepted_count,
            "rejected": rejected_count,
            "needs_review": review_count,
            "repairs": repairs_count,
            "shortfall": shortfall,
            "dataset_metrics": dataset_metrics,
            "limitations": limitations,
            "execution_provenance": {
                "model_or_engine": "fixture-rules-v1" if run_mode == "fixture" else settings.model_deployment_name,
                "foundry_agent_version": settings.agent_version if run_mode == "foundry" else None,
                "uses_deployed_agents": run_mode == "foundry" and settings.use_deployed_agents,
            },
        }
        progress_summary["limitations"].extend([
            "Factual correctness is not assessed without an independent trusted answer to the same question.",
            "Near-duplicate detection is a lexical heuristic, not a calibrated semantic judge.",
            "Budget units cap candidate volume; they are not Azure token or currency estimates.",
        ])

        with session_scope() as session:
            r = session.get(GenerationRun, run_id)
            if r:
                r.status = final_run_status.value
                r.progress_json = progress_summary
                r.completed_at = now()
                session.commit()

        return run_id

    def _persist_case_and_metrics(
        self,
        session: Session,
        case_id: str,
        run_id: str,
        project_id: str,
        data: dict[str, Any],
        status: Any,
        verification: dict[str, Any],
        mode: str,
    ) -> None:
        status_value = status.value if hasattr(status, "value") else str(status)
        row = CandidateCase(
            id=case_id, run_id=run_id, project_id=project_id,
            parent_attempt_id=data.get("parent_attempt_id"),
            attempt_number=int(data.get("attempt_number", 0)),
            question=data["question"],
            candidate_reference_answer=data["candidate_reference_answer"],
            expected_behavior=data["expected_behavior"], topic=data["topic"],
            scenario_type=data["scenario_type"], difficulty=data["difficulty"],
            modality=data.get("modality", "text"), seed_ids=data.get("seed_ids", []),
            source_version_ids=data.get("source_version_ids", []), evidence_refs=data.get("evidence_refs", []),
            required_facts=data.get("required_facts", []), reference_origin=data.get("reference_origin", "automatically_derived"),
            status=status_value, failed_checks=verification.get("failed_claims", []),
        )
        session.add(row); session.flush()
        metrics = [
            ("faithfulness", verification.get("faithfulness_score")),
            ("factual_f1", None),
            ("completeness", verification.get("completeness_score")),
            ("answer_relevance", verification.get("relevance_score")),
            ("answerability", verification.get("answerability_score")),
            ("citation_validity", 1.0 if verification.get("citation_valid") else 0.0),
        ]
        for name, score in metrics:
            session.add(MetricAssessment(
                id=uid(), case_id=case_id, metric_name=name,
                metric_version="ragtrust-1.0", evaluator_model_version=f"{mode}-evaluator-v1",
                score=score, scale="0_to_1",
                applicability="assessed" if score is not None else "not_assessed",
                evidence_ids=data.get("evidence_refs", []),
                failed_claims=verification.get("failed_claims", []),
                concise_reason=("Not assessed: no independent trusted reference for this exact generated question."
                    if name == "factual_f1" else verification.get("concise_reason", "")),
            ))

    def release_dataset_version(self, run_id: str) -> str:
        """
        Freezes an accepted dataset version and publishes exports and quality reports.
        """
        with session_scope() as session:
            run = session.get(GenerationRun, run_id)
            if not run:
                raise ValueError("Run not found")

            if run.status not in {RunStatus.completed.value, RunStatus.completed_shortfall.value}:
                raise ValueError("Only a completed run can be released")

            project_id = run.project_id
            existing_versions = session.scalars(
                select(DatasetVersion).where(DatasetVersion.project_id == project_id)
            ).all()
            version_number = len(existing_versions) + 1

            accepted_cases = session.scalars(
                select(CandidateCase).where(
                    CandidateCase.run_id == run_id,
                    CandidateCase.status == CaseStatus.accepted.value,
                )
            ).all()

            cases_data = [
                {
                    "case_id": c.id,
                    "question": c.question,
                    "candidate_reference_answer": c.candidate_reference_answer,
                    "expected_behavior": c.expected_behavior,
                    "topic": c.topic,
                    "scenario_type": c.scenario_type,
                    "difficulty": c.difficulty,
                    "modality": c.modality,
                    "seed_ids": c.seed_ids,
                    "source_version_ids": c.source_version_ids,
                    "evidence_refs": c.evidence_refs,
                    "required_facts": c.required_facts,
                    "reference_origin": c.reference_origin,
                    "status": c.status,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in accepted_cases
            ]

            all_cases_in_run = session.scalars(
                select(CandidateCase).where(CandidateCase.run_id == run_id)
            ).all()
            parent_ids = {c.parent_attempt_id for c in all_cases_in_run if c.parent_attempt_id}
            final_cases = [c for c in all_cases_in_run if c.id not in parent_ids]
            all_cases_data = []
            for c in all_cases_in_run:
                assessments = session.scalars(
                    select(MetricAssessment).where(MetricAssessment.case_id == c.id)
                ).all()
                all_cases_data.append({
                    "id": c.id, "parent_attempt_id": c.parent_attempt_id,
                    "attempt_number": c.attempt_number, "question": c.question,
                    "candidate_reference_answer": c.candidate_reference_answer,
                    "status": c.status, "failed_checks": c.failed_checks,
                    "topic": c.topic, "difficulty": c.difficulty, "scenario_type": c.scenario_type,
                    "modality": c.modality, "is_final_attempt": c.id not in parent_ids,
                    "evidence_refs": c.evidence_refs, "reference_origin": c.reference_origin,
                    "metrics": [
                        {"name": m.metric_name, "score": m.score, "scale": m.scale,
                         "applicability": m.applicability, "metric_version": m.metric_version,
                         "evaluator_version": m.evaluator_model_version,
                         "reason": m.concise_reason, "failed_claims": m.failed_claims}
                        for m in assessments
                    ],
                })
            assessment_lookup = {c["id"]: c for c in all_cases_data}
            for case in cases_data:
                case["metrics"] = {
                    ("factual_correctness" if m["name"] == "factual_f1" else m["name"]): m
                    for m in assessment_lookup[case["case_id"]]["metrics"]
                }
            accepted_coverage = DeterministicQualityEngine.evaluate_topic_coverage(
                [c.topic for c in accepted_cases], (run.plan_json or {}).get("topic_quotas", {}))
            accepted_scores = [m["score"] for c in accepted_cases for m in assessment_lookup[c.id]["metrics"]
                if m["name"] == "faithfulness" and m["score"] is not None]
            release_metrics = {**(run.progress_json or {}).get("dataset_metrics", {}),
                "topic_coverage": accepted_coverage,
                "jensen_shannon_divergence": DeterministicQualityEngine.compute_jensen_shannon_divergence(
                    (run.plan_json or {}).get("topic_quotas", {}),
                    {topic: sum(c.topic == topic for c in accepted_cases) for topic in {c.topic for c in accepted_cases}}),
                "avg_faithfulness": sum(accepted_scores) / len(accepted_scores) if accepted_scores else None,
                "metric_evaluated_count": len(accepted_scores),
                "before_filtering": {"final_candidate_count": len(final_cases)},
                "after_filtering": {"accepted_count": len(accepted_cases)},
                "slices": {
                    dimension: {
                        value: {"total": sum(getattr(c, dimension) == value for c in final_cases),
                            "accepted": sum(getattr(c, dimension) == value and c.status == "accepted" for c in final_cases)}
                        for value in sorted({getattr(c, dimension) for c in final_cases})
                    } for dimension in ("topic", "difficulty", "scenario_type", "modality")
                }}
            source_inventory = [
                {"source_id": src.id, "filename": src.filename, "sha256": src.sha256,
                 "version": src.version, "extraction_status": src.extraction_status}
                for src in session.scalars(select(SourceAsset).where(SourceAsset.project_id == project_id)).all()
            ]

        # Export canonical JSONL and flattened CSV
        rel_dir = workspace_data_dir() / "releases" / f"proj_{project_id}_v{version_number}"
        jsonl_path = rel_dir / "dataset.jsonl"
        csv_path = rel_dir / "dataset.csv"
        html_report_path = rel_dir / "quality_report.html"
        json_report_path = rel_dir / "summary.json"
        assessment_path = rel_dir / "case_assessments.jsonl"

        jsonl_sha = DatasetExporter.export_canonical_jsonl(cases_data, jsonl_path)
        csv_sha = DatasetExporter.export_flattened_csv(cases_data, csv_path)
        assessment_sha = DatasetExporter.export_canonical_jsonl(all_cases_data, assessment_path)

        # Generate reports
        run_payload = {
            **(run.progress_json or {"run_id": run_id, "project_id": project_id}),
            "execution_mode": run.mode,
            "configuration": run.config_json,
            "timing": {
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "usage_or_cost": "Not available from fixture mode" if run.mode == "fixture" else "Provider usage was not returned by this SDK path",
            },
            "source_inventory": source_inventory,
            "accepted": len(accepted_cases),
            "rejected": sum(c.status == CaseStatus.rejected.value for c in final_cases),
            "needs_review": sum(c.status in {CaseStatus.needs_review.value, CaseStatus.needs_revision.value} for c in final_cases),
            "shortfall": max(0, run.config_json.get("accepted_target", 0) - len(accepted_cases)),
            "provenance": {
                "dataset_version": version_number,
                "model_or_engine": "fixture-rules-v1" if run.mode == "fixture" else settings.model_deployment_name,
                "agent_prompt_version": "ragtrust-agent-prompts-v1",
                "metric_version": "ragtrust-1.0",
                "application_version": "0.1.0",
                **(run.progress_json or {}).get("execution_provenance", {}),
            },
        }
        summary_json = QualityReportGenerator.generate_summary_json(
            run_data=run_payload,
            dataset_metrics=release_metrics,
        )
        json_report_path.parent.mkdir(parents=True, exist_ok=True)
        json_report_path.write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

        QualityReportGenerator.generate_html_report(summary_json, all_cases_data, html_report_path)

        manifest = DatasetExporter.create_release_manifest(
            project_id=project_id,
            run_id=run_id,
            version_number=version_number,
            jsonl_path=jsonl_path,
            jsonl_sha=jsonl_sha,
            csv_path=csv_path,
            csv_sha=csv_sha,
            total_accepted=len(accepted_cases),
            metrics_summary=summary_json.get("dataset_metrics", {}),
            assessment_path=assessment_path,
            assessment_sha=assessment_sha,
        )

        with session_scope() as session:
            dv = DatasetVersion(
                id=uid(),
                project_id=project_id,
                run_id=run_id,
                version_number=version_number,
                manifest_json=manifest,
                content_sha256=jsonl_sha,
                storage_path=str(jsonl_path),
                immutable=True,
            )
            session.add(dv)
            session.flush()

            qr = QualityReport(
                id=uid(),
                dataset_version_id=dv.id,
                summary_json=summary_json,
                html_path=str(html_report_path),
                json_path=str(json_report_path),
            )
            session.add(qr)
            session.commit()
            return dv.id

    def review_case(self, case_id: str, decision: str, notes: str = "", corrected_answer: str | None = None) -> None:
        with session_scope() as session:
            case = session.get(CandidateCase, case_id)
            if not case:
                raise ValueError("Case not found")
            if decision not in {"approve", "reject", "correct"}:
                raise ValueError("Invalid review decision")
            if decision == "correct" and not (corrected_answer or "").strip():
                raise ValueError("A non-empty corrected answer is required")
            if session.scalar(select(CandidateCase).where(CandidateCase.parent_attempt_id == case_id)):
                raise ValueError("Review the latest attempt; this case has a newer revision")

            # Update status
            if decision == "approve":
                case.status = CaseStatus.accepted.value
                case.reference_origin = "human_verified"
            elif decision == "reject":
                case.status = CaseStatus.rejected.value
            elif decision == "correct":
                case.status = CaseStatus.accepted.value
                if corrected_answer:
                    case.candidate_reference_answer = corrected_answer
                case.reference_origin = "human_corrected"
                for metric in session.scalars(select(MetricAssessment).where(MetricAssessment.case_id == case_id)).all():
                    metric.score = None
                    metric.applicability = "not_assessed"
                    metric.concise_reason = "Answer changed by a reviewer; previous scores do not apply to the corrected text."

            rev = ReviewDecision(
                id=uid(),
                case_id=case_id,
                decision=decision,
                corrected_answer=corrected_answer,
                notes=notes,
                reviewer="auditor",
            )
            session.add(rev)
            session.commit()

    def run_rag_test(self, dataset_version_id: str, request: RagEvalRequest) -> dict[str, Any]:
        with session_scope() as session:
            dv = session.get(DatasetVersion, dataset_version_id)
            if not dv:
                raise ValueError("Dataset version not found")

            # Evaluate the frozen release, never mutable post-release case rows.
            cases_data = [json.loads(line) for line in Path(dv.storage_path).read_text().splitlines() if line.strip()]
            if settings.public_demo and len(cases_data) > 20:
                raise ValueError("Public RAG tests support at most 20 cases per release")
            for case in cases_data:
                case["id"] = case.get("case_id")

        results = self.rag_evaluator.run({"cases": cases_data, "config": request})

        with session_scope() as session:
            rag_run = RagRun(
                id=uid(),
                dataset_version_id=dataset_version_id,
                endpoint_label=request.endpoint_label,
                status="completed",
                result_json=results,
            )
            session.add(rag_run)
            session.commit()

        return results


if __name__ == "__main__":
    from .services.extractor import SourceExtractor, compute_sha256

    svc = OrchestrationService()
    print("=== RAGTrust Orchestrator CLI ===")
    demo_dir = Path(__file__).resolve().parent.parent.parent / "demo_data"
    print(f"Loading demo data from: {demo_dir}")
    pid = svc.create_project(
        name="Enterprise Security & Compliance 2026",
        description="Golden Q&A benchmark for corporate security and regulatory compliance.",
        domain="cybersecurity_compliance",
    )
    print(f"Created project: {pid}")

    csv_path = demo_dir / "golden_support_qa.csv"
    if csv_path.exists():
        exs = SourceExtractor.parse_golden_file(csv_path.read_text(), csv_path.name)
        added = svc.add_golden_examples(pid, [e.model_dump() for e in exs])
        print(f"Added {added} golden examples.")

    txt_path = demo_dir / "security_compliance_policy.txt"
    if txt_path.exists():
        txt = txt_path.read_text()
        segs = SourceExtractor.extract_text_segments(txt, "security_compliance_policy.txt", asset_id="")
        aid = svc.add_source_asset(pid, "security_compliance_policy.txt", "text/plain", compute_sha256(txt), str(txt_path), segs)
        print(f"Added policy source asset ({len(segs)} segments).")

    vid_path = demo_dir / "security_walkthrough_video.json"
    if vid_path.exists():
        vid = vid_path.read_text()
        v_segs = SourceExtractor.extract_text_segments(vid, "security_walkthrough_video.json", asset_id="")
        vid_id = svc.add_source_asset(pid, "security_walkthrough_video.json", "application/json", compute_sha256(vid), str(vid_path), v_segs)
        print(f"Added video source asset ({len(v_segs)} segments).")

    cfg = GenerationConfig(candidate_target=12, accepted_target=8, max_repairs=2)
    print(f"Starting generation run (target: {cfg.candidate_target}, accepted: {cfg.accepted_target})...")
    run_id = svc.execute_generation_run(pid, cfg, mode="fixture")
    print(f"Generation run completed! Run ID: {run_id}")

    v_id = svc.release_dataset_version(run_id)
    print(f"Dataset version released! Version ID: {v_id}")
    print("All artifacts generated successfully in data/releases/!")
