from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select

from .db import session_scope
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
)
from .orchestrator import OrchestrationService
from .schemas import (
    CalibrationResult,
    GenerationConfig,
    ProjectCreate,
    RagEvalRequest,
    ReviewInput,
    SourceMapping,
)
from .services.calibration import EvaluatorCalibrationEngine
from .services.extractor import SourceExtractor, compute_sha256
from .storage import LocalStorage

app = FastAPI(
    title="RAGTrust API",
    description="Golden-Guided Synthetic Evaluation Data Platform for RAG Systems",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = OrchestrationService()
storage = LocalStorage()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "platform": "RAGTrust v1.0", "mode": "fixture/foundry"}


@app.post("/projects", tags=["Projects"])
def create_project(data: ProjectCreate) -> dict[str, Any]:
    project_id = service.create_project(
        name=data.name, description=data.description, domain=data.domain
    )
    return {
        "id": project_id,
        "project_id": project_id,
        "name": data.name,
        "domain": data.domain,
        "status": "created",
    }


@app.get("/projects", tags=["Projects"])
def list_projects() -> list[dict[str, Any]]:
    with session_scope() as session:
        projects = session.scalars(select(Project).order_by(Project.created_at.desc())).all()
        return [
            {
                "id": p.id,
                "project_id": p.id,
                "name": p.name,
                "description": p.description,
                "domain": p.domain,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in projects
        ]


@app.post("/projects/{id}/golden-examples", tags=["Ingestion"])
async def import_golden_examples(
    id: str,
    request: Request,
    benchmark_role: str = "seed",
) -> dict[str, Any]:
    with session_scope() as session:
        proj = session.get(Project, id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

    content_type = request.headers.get("content-type", "")
    records = []
    if "application/json" in content_type:
        body = await request.json()
        if isinstance(body, list):
            records = body
        elif isinstance(body, dict):
            records = body.get("examples", [body])
    elif "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if file and hasattr(file, "read"):
            content = await file.read()
            mapping_str = form.get("mapping_json")
            mapping = json.loads(mapping_str) if mapping_str else SourceMapping()
            if isinstance(mapping, dict):
                mapping = SourceMapping(**mapping)
            parsed = SourceExtractor.parse_golden_file(content, getattr(file, "filename", "golden.csv"), mapping, benchmark_role)
            records = [p.model_dump() for p in parsed]

    added = service.add_golden_examples(id, records)
    return {"project_id": id, "id": id, "added_examples": added, "imported": added}


@app.post("/projects/{id}/sources", tags=["Ingestion"])
async def upload_source_asset(
    id: str,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    with session_scope() as session:
        proj = session.get(Project, id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    sha = compute_sha256(content)
    segments = SourceExtractor.extract_text_segments(content, file.filename or "upload.txt", asset_id="")
    stored_path, stored_sha = storage.put(id, "sources", file.filename or "upload", content)
    scanned_pdf = (file.filename or "").lower().endswith(".pdf") and not segments
    extraction_status = "needs_ocr" if scanned_pdf else "completed"
    extraction_notes = (
        "No extractable PDF text was found. OCR is required; no text or scores were fabricated."
        if scanned_pdf
        else f"Extracted {len(segments)} evidence segments."
    )

    asset_id = service.add_source_asset(
        project_id=id,
        filename=file.filename or "upload.txt",
        media_type=file.content_type or "text/plain",
        content_sha256=stored_sha,
        storage_path=stored_path,
        segments=segments,
        extraction_status=extraction_status,
        extraction_notes=extraction_notes,
    )
    return {
        "id": asset_id,
        "source_asset_id": asset_id,
        "filename": file.filename,
        "extracted_segments": len(segments),
        "status": extraction_status,
        "notes": extraction_notes,
    }


@app.post("/projects/{id}/profile", tags=["Planning"])
def profile_project(
    id: str,
    config: GenerationConfig | None = None,
) -> dict[str, Any]:
    with session_scope() as session:
        proj = session.get(Project, id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

        golden = [
            {"id": g.id, "external_id": g.external_id, "question": g.question, "trusted_answer": g.trusted_answer, "topic": g.topic}
            for g in session.scalars(select(GoldenExample).where(GoldenExample.project_id == id)).all()
        ]
        raw_segs = session.execute(
            select(EvidenceSegment, SourceAsset).join(SourceAsset, EvidenceSegment.source_asset_id == SourceAsset.id).where(SourceAsset.project_id == id)
        ).all()
        evidence = [{"id": seg.id, "locator": seg.locator, "text": seg.text} for seg, _ in raw_segs]

    plan = service.planner.run(
        {
            "golden_examples": golden,
            "evidence_segments": evidence,
            "config": config or GenerationConfig(),
            "domain": proj.domain,
        }
    )
    return plan


@app.post("/projects/{id}/generation-runs", tags=["Runs"])
def create_generation_run(
    id: str,
    config: GenerationConfig,
    mode: str = Query("fixture", pattern="^(fixture|foundry)$"),
) -> dict[str, str]:
    with session_scope() as session:
        proj = session.get(Project, id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

    run_id = service.execute_generation_run(project_id=id, config=config, mode=mode)
    return {"id": run_id, "run_id": run_id, "status": "completed", "mode": mode}


@app.post("/projects/{id}/generation-jobs", tags=["Runs"])
def create_background_generation_job(
    id: str,
    config: GenerationConfig,
    mode: str = Query("fixture", pattern="^(fixture|foundry)$"),
) -> dict[str, str]:
    run_id = service.enqueue_generation_run(project_id=id, config=config, mode=mode)
    return {"id": run_id, "run_id": run_id, "status": "queued", "mode": mode}


@app.post("/generation-runs/{id}/cancel", tags=["Runs"])
def cancel_generation_job(id: str) -> dict[str, str]:
    service.cancel_generation_run(id)
    return {"id": id, "status": "cancellation_requested"}


@app.get("/generation-runs/{id}", tags=["Runs"])
def get_run_details(id: str) -> dict[str, Any]:
    with session_scope() as session:
        run = session.get(GenerationRun, id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "id": run.id,
            "run_id": run.id,
            "project_id": run.project_id,
            "status": run.status,
            "mode": run.mode,
            "plan": run.plan_json,
            "progress": run.progress_json,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }


@app.get("/generation-runs/{id}/cases", tags=["Runs"])
def list_run_cases(
    id: str,
    status: str | None = None,
    topic: str | None = None,
    modality: str | None = None,
) -> list[dict[str, Any]]:
    with session_scope() as session:
        stmt = select(CandidateCase).where(CandidateCase.run_id == id)
        if status:
            stmt = stmt.where(CandidateCase.status == status)
        if topic:
            stmt = stmt.where(CandidateCase.topic == topic)
        if modality:
            stmt = stmt.where(CandidateCase.modality == modality)

        cases = session.scalars(stmt).all()
        return [
            {
                "id": c.id,
                "question": c.question,
                "candidate_reference_answer": c.candidate_reference_answer,
                "candidate_answer": c.candidate_reference_answer,
                "expected_behavior": c.expected_behavior,
                "topic": c.topic,
                "scenario_type": c.scenario_type,
                "difficulty": c.difficulty,
                "modality": c.modality,
                "status": c.status,
                "failed_checks": c.failed_checks,
                "evidence_refs": c.evidence_refs,
                "attempt_number": c.attempt_number,
                "parent_attempt_id": c.parent_attempt_id,
                "reference_origin": c.reference_origin,
            }
            for c in cases
        ]


@app.post("/cases/{id}/review", tags=["Review"])
def review_case(id: str, data: ReviewInput) -> dict[str, str]:
    service.review_case(
        case_id=id,
        decision=data.decision,
        notes=data.notes,
        corrected_answer=data.corrected_answer,
    )
    return {"id": id, "case_id": id, "status": "reviewed"}


@app.post("/generation-runs/{id}/releases", tags=["Releases"])
def freeze_dataset_release(id: str) -> dict[str, Any]:
    dv_id = service.release_dataset_version(id)
    return {"id": dv_id, "dataset_version_id": dv_id, "status": "released"}


@app.get("/datasets/{id}/report", tags=["Releases"])
def get_dataset_report(id: str, format: str = Query("json", pattern="^(json|html)$")):
    with session_scope() as session:
        qr = session.scalar(select(QualityReport).where(QualityReport.dataset_version_id == id))
        if not qr:
            raise HTTPException(status_code=404, detail="Report not found for dataset version")

        if format == "html":
            p = Path(qr.html_path)
            if p.exists():
                return HTMLResponse(content=p.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>Report file not found</h1>", status_code=404)
        return qr.summary_json


@app.get("/datasets/{id}/export", tags=["Releases"])
def export_dataset(id: str, format: str = Query("jsonl", pattern="^(jsonl|csv|assessments)$")):
    with session_scope() as session:
        dv = session.get(DatasetVersion, id)
        if not dv:
            raise HTTPException(status_code=404, detail="Dataset version not found")

        manifest = dv.manifest_json or {}
        files = manifest.get("files", {})
        if format == "assessments":
            path_str = files.get("case_assessments", {}).get("path")
            media = "application/jsonlines"
            name = f"case_assessments_v{dv.version_number}.jsonl"
        elif format == "csv":
            path_str = files.get("csv", {}).get("path")
            media = "text/csv"
            name = f"dataset_v{dv.version_number}.csv"
        else:
            path_str = files.get("jsonl", {}).get("path")
            media = "application/jsonlines"
            name = f"dataset_v{dv.version_number}.jsonl"

        if path_str and Path(path_str).exists():
            return FileResponse(path=path_str, media_type=media, filename=name)
        raise HTTPException(status_code=404, detail="Export file not found")


@app.post("/datasets/{id}/rag-runs", tags=["RAG Testing"])
def test_target_rag_system(id: str, request: RagEvalRequest) -> dict[str, Any]:
    return service.run_rag_test(id, request)


@app.post("/evaluator/calibrate", tags=["Calibration"])
def run_calibration_benchmark(benchmark_cases: list[dict[str, Any]]) -> CalibrationResult:
    """
    Validates the evaluator against ground-truth cases with known defects.
    """
    def eval_fn(case: dict[str, Any]) -> dict[str, Any]:
        return service.verifier.run(
            {
                "question": case.get("question"),
                "candidate_reference_answer": case.get("candidate_reference_answer"),
                "expected_behavior": case.get("expected_behavior", "answer"),
                "evidence_segments": case.get("evidence_segments", []),
                "evidence_refs": case.get("evidence_refs", []),
                "valid_locators": set(case.get("valid_locators", [])),
                "required_facts": case.get("required_facts", []),
            }
        )

    return EvaluatorCalibrationEngine.evaluate_benchmark(benchmark_cases, eval_fn)
