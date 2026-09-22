from __future__ import annotations

from pathlib import Path

from ragtrust.config import settings
from ragtrust.orchestrator import OrchestrationService
from ragtrust.schemas import GenerationConfig


def test_orchestrator_end_to_end_flow():
    service = OrchestrationService()
    project_id = service.create_project(
        name="Test Security Project",
        description="End to end test project",
        domain="cybersecurity",
    )
    assert project_id is not None

    # Ingest golden examples
    golden = [
        {"question": "What is the password requirement?", "trusted_answer": "14 characters with numbers and symbols.", "topic": "Access Control"},
        {"question": "How long are audit logs kept?", "trusted_answer": "Audit logs are kept for 365 days.", "topic": "Data Retention"},
    ]
    added = service.add_golden_examples(project_id, golden)
    assert added == 2

    # Ingest source asset
    segments = [
        {"locator": "test_doc:sec1", "text": "All passwords must be at least 14 characters with numbers and symbols.", "modality": "text"},
        {"locator": "test_doc:sec2", "text": "Audit logs must be retained in cloud storage for 365 days.", "modality": "text"},
    ]
    aid = service.add_source_asset(
        project_id=project_id,
        filename="test_doc.txt",
        media_type="text/plain",
        content_sha256="fake_sha",
        storage_path="storage/test_doc.txt",
        segments=segments,
    )
    assert aid is not None

    # Run generation
    config = GenerationConfig(candidate_target=4, accepted_target=2, max_repairs=1)
    run_id = service.execute_generation_run(project_id, config, mode="fixture")
    assert run_id is not None

    # Freeze release
    v_id = service.release_dataset_version(run_id)
    assert v_id is not None

    # Check release files exist
    release_dir = settings.data_dir / "releases" / f"proj_{project_id}_v1"
    assert (release_dir / "dataset.jsonl").exists()
    assert (release_dir / "dataset.csv").exists()
    assert (release_dir / "quality_report.html").exists()
    assert (release_dir / "summary.json").exists()
