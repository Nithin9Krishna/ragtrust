#!/usr/bin/env python3
"""Run a small, real Foundry-backed RAGTrust workflow and publish a local release."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from ragtrust.db import session_scope
from ragtrust.models import GenerationRun
from ragtrust.orchestrator import OrchestrationService
from ragtrust.schemas import GenerationConfig
from ragtrust.services.extractor import SourceExtractor, compute_sha256


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    demo_dir = project_root / "demo_data"
    service = OrchestrationService()
    project_id = service.create_project(
        name="RAGTrust live Foundry verification",
        description="Small live run used to verify the deployed Foundry agents.",
        domain="cybersecurity_compliance",
    )

    golden_path = demo_dir / "golden_support_qa.csv"
    golden = SourceExtractor.parse_golden_file(golden_path.read_text(), golden_path.name)
    service.add_golden_examples(project_id, [item.model_dump() for item in golden[:4]])

    policy_path = demo_dir / "security_compliance_policy.txt"
    policy_text = policy_path.read_text()
    segments = SourceExtractor.extract_text_segments(policy_text, policy_path.name, asset_id="")
    service.add_source_asset(
        project_id,
        policy_path.name,
        "text/plain",
        compute_sha256(policy_text),
        str(policy_path),
        segments[:5],
    )

    config = GenerationConfig(candidate_target=2, accepted_target=1, max_repairs=1, budget_units=20)
    run_id = service.execute_generation_run(project_id, config, mode="foundry")
    dataset_version_id = service.release_dataset_version(run_id)
    with session_scope() as session:
        run = session.scalar(select(GenerationRun).where(GenerationRun.id == run_id))
        summary = {
            "status": run.status,
            "progress": run.progress_json,
            "mode": run.mode,
        }
    print(
        json.dumps(
            {
                "project_id": project_id,
                "run_id": run_id,
                "dataset_version_id": dataset_version_id,
                **summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
