from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


METRIC_DEFINITIONS = {
    "faithfulness": "Automated supported-claim ratio against supplied evidence; accepted final attempts only in the average.",
    "factual_correctness": "Not assessed without a trusted independent reference to the exact generated question.",
    "completeness": "Coverage of the question-specific required facts; generated checklists remain provisional.",
    "answer_relevance": "Foundry judge rubric in live mode; heuristic demonstration rule in fixture mode.",
    "topic_coverage": "Positive-quota topics meeting quota among accepted final attempts divided by positive-quota topics.",
    "exact_duplicates": "Repeated normalized questions / generated candidates; later exact duplicates are rejected.",
    "near_duplicates": "Character trigram cosine >= 0.82, a lexical heuristic, not semantic accuracy.",
    "distribution_distance": "Square root of Jensen-Shannon divergence, target versus accepted topic distribution; 0-1.",
    "human_correctness": "Not assessed until a representative audit is completed. Manual review is not automatically a representative audit.",
}


class QualityReportGenerator:
    @staticmethod
    def generate_summary_json(run_data: dict[str, Any], dataset_metrics: dict[str, Any], audit_metrics=None) -> dict[str, Any]:
        return {
            "report_id": f"rep-{run_data.get('run_id')}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_data.get("run_id"), "project_id": run_data.get("project_id"),
            "execution_mode": run_data.get("execution_mode", "unknown"),
            "configuration": run_data.get("configuration", {}), "timing": run_data.get("timing", {}),
            "source_inventory": run_data.get("source_inventory", []), "provenance": run_data.get("provenance", {}),
            "counts": {**{k: run_data.get(k, 0) for k in ["generated", "accepted", "rejected", "needs_review", "needs_revision", "shortfall"]}, "repairs_attempted": run_data.get("repairs", 0)},
            "acceptance_rate": round(run_data.get("accepted", 0) / run_data["generated"], 4) if run_data.get("generated") else None,
            "dataset_metrics": dataset_metrics, "metric_definitions": METRIC_DEFINITIONS,
            "human_audit": audit_metrics or {"sample_size": 0, "fully_correct_rate": None, "confidence_interval": "Not assessed: no representative human audit has been completed."},
            "limitations": run_data.get("limitations", []),
        }

    @classmethod
    def generate_html_report(cls, summary: dict[str, Any], candidate_cases: list[dict[str, Any]], output_path: Path) -> str:
        def e(value):
            return escape(str(value))
        def block(title, value):
            return f"<h2>{e(title)}</h2><pre>{e(json.dumps(value, indent=2, ensure_ascii=False))}</pre>"
        html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>RAGTrust Quality Report</title>
<style>body{font:15px/1.6 system-ui,sans-serif;color:#183044;background:#edf2f6;margin:0}main{max-width:1050px;margin:auto;background:white;padding:42px}h1{color:#123248}h2{margin-top:30px;border-bottom:2px solid #dbe4ec;padding-bottom:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f8fa;padding:18px;border-radius:8px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #dbe4ec;vertical-align:top}.note{border-left:4px solid #13857f;padding:12px;background:#eefaf7}.case{padding:16px;border:1px solid #dbe4ec;margin:12px 0;border-radius:8px}@media print{body{background:white}main{padding:10px}pre,.case{break-inside:avoid}}</style></head><body><main>'''
        html += f"<h1>RAGTrust - Dataset Quality Report</h1><p>Run: {e(summary.get('run_id'))}<br>Generated: {e(summary.get('generated_at'))}</p>"
        html += f"<p class='note'>Execution mode: <strong>{e(summary.get('execution_mode'))}</strong>. Automated support scores are not human-verified correctness. No universal acceptance benchmark is implied.</p>"
        html += block("Counts and target shortfall", summary.get("counts", {}))
        html += block("Dataset metrics, populations and slices", summary.get("dataset_metrics", {}))
        html += "<h2>Metric definitions</h2><table><tr><th>Metric</th><th>Interpretation</th></tr>"
        html += "".join(f"<tr><td>{e(name)}</td><td>{e(definition)}</td></tr>" for name, definition in METRIC_DEFINITIONS.items()) + "</table>"
        html += block("Human audit", summary.get("human_audit", {}))
        html += "<h2>Case assessments and evidence references</h2>"
        for case in candidate_cases:
            html += f"<section class='case'><strong>{e(case.get('id', case.get('case_id')))} - {e(case.get('status'))}</strong><p>{e(case.get('question'))}</p><p>{e(case.get('candidate_reference_answer'))}</p><p>Evidence: {e(case.get('evidence_refs', []))}</p><p>Failed checks: {e(case.get('failed_checks', []))}</p><pre>{e(json.dumps(case.get('metrics', []), indent=2))}</pre></section>"
        for title, field in [("Configuration", "configuration"), ("Source inventory", "source_inventory"), ("Timing and usage", "timing"), ("Provenance", "provenance"), ("Limitations", "limitations")]:
            html += block(title, summary.get(field, {}))
        html += "<h2>Recommended next actions</h2><p>Review unresolved cases against their evidence. Add sources for topic deficits, rerun with explicit quotas, and audit a representative sample before claiming correctness. Recalibrate the judge after material model or rubric changes.</p></main></body></html>"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return html
