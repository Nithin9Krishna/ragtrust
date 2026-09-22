from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .extractor import compute_sha256


class DatasetExporter:
    @staticmethod
    def export_canonical_jsonl(cases: list[dict[str, Any]], target_path: Path) -> str:
        """
        Exports cases to canonical JSONL, keeping nested evidence, seeds, and metric metadata.
        """
        lines = [json.dumps(c, default=str) for c in cases]
        content = "\n".join(lines) + ("\n" if lines else "")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return compute_sha256(content)

    @staticmethod
    def export_flattened_csv(cases: list[dict[str, Any]], target_path: Path) -> str:
        """
        Exports cases to flattened CSV for easy spreadsheet inspection.
        """
        output = io.StringIO()
        fieldnames = [
            "case_id",
            "question",
            "candidate_reference_answer",
            "expected_behavior",
            "topic",
            "scenario_type",
            "difficulty",
            "modality",
            "status",
            "reference_origin",
            "faithfulness_score",
            "factual_f1",
            "completeness_score",
            "evidence_refs",
            "seed_ids",
            "created_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for c in cases:
            row = {
                "case_id": c.get("id") or c.get("case_id"),
                "question": c.get("question"),
                "candidate_reference_answer": c.get("candidate_reference_answer"),
                "expected_behavior": c.get("expected_behavior"),
                "topic": c.get("topic"),
                "scenario_type": c.get("scenario_type"),
                "difficulty": c.get("difficulty"),
                "modality": c.get("modality"),
                "status": c.get("status"),
                "reference_origin": c.get("reference_origin"),
                "faithfulness_score": c.get("metrics", {}).get("faithfulness", {}).get("score"),
                "factual_f1": c.get("metrics", {}).get("factual_correctness", {}).get("score"),
                "completeness_score": c.get("metrics", {}).get("completeness", {}).get("score"),
                "evidence_refs": ";".join(c.get("evidence_refs", [])),
                "seed_ids": ";".join(c.get("seed_ids", [])),
                "created_at": c.get("created_at"),
            }
            writer.writerow(row)

        csv_content = output.getvalue()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(csv_content, encoding="utf-8")
        return compute_sha256(csv_content)

    @staticmethod
    def create_release_manifest(
        project_id: str,
        run_id: str,
        version_number: int,
        jsonl_path: Path,
        jsonl_sha: str,
        csv_path: Path,
        csv_sha: str,
        total_accepted: int,
        metrics_summary: dict[str, Any],
        assessment_path: Path | None = None,
        assessment_sha: str | None = None,
    ) -> dict[str, Any]:
        manifest = {
            "project_id": project_id,
            "run_id": run_id,
            "version_number": version_number,
            "total_accepted_cases": total_accepted,
            "files": {
                "jsonl": {
                    "filename": jsonl_path.name,
                    "path": str(jsonl_path),
                    "sha256": jsonl_sha,
                },
                "csv": {
                    "filename": csv_path.name,
                    "path": str(csv_path),
                    "sha256": csv_sha,
                },
            },
            "metrics_summary": metrics_summary,
            "generator": "RAGTrust Golden-Guided Platform v1.0",
        }
        if assessment_path and assessment_sha:
            manifest["files"]["case_assessments"] = {
                "filename": assessment_path.name,
                "path": str(assessment_path),
                "sha256": assessment_sha,
            }
        return manifest
