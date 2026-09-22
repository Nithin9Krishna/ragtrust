from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QualityReportGenerator:
    @staticmethod
    def generate_summary_json(
        run_data: dict[str, Any],
        dataset_metrics: dict[str, Any],
        audit_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "report_id": f"rep-{run_data.get('run_id')}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_data.get("run_id"),
            "project_id": run_data.get("project_id"),
            "execution_mode": run_data.get("execution_mode", "unknown"),
            "configuration": run_data.get("configuration", {}),
            "timing": run_data.get("timing", {}),
            "source_inventory": run_data.get("source_inventory", []),
            "provenance": run_data.get("provenance", {}),
            "counts": {
                "generated": run_data.get("generated", 0),
                "accepted": run_data.get("accepted", 0),
                "rejected": run_data.get("rejected", 0),
                "needs_review": run_data.get("needs_review", 0),
                "needs_revision": run_data.get("needs_revision", 0),
                "repairs_attempted": run_data.get("repairs", 0),
                "shortfall": run_data.get("shortfall", 0),
            },
            "acceptance_rate": (
                round(run_data.get("accepted", 0) / run_data.get("generated", 1), 4)
                if run_data.get("generated", 0) > 0
                else 0.0
            ),
            "dataset_metrics": dataset_metrics,
            "human_audit": audit_metrics
            or {
                "sample_size": 0,
                "fully_correct_rate": None,
                "confidence_interval": "Not assessed: no representative human audit has been completed.",
            },
            "limitations": run_data.get("limitations", []),
        }

    @classmethod
    def generate_html_report(
        cls,
        summary: dict[str, Any],
        candidate_cases: list[dict[str, Any]],
        output_path: Path,
    ) -> str:
        counts = summary.get("counts", {})
        ds_metrics = summary.get("dataset_metrics", {})
        audit = summary.get("human_audit", {})
        limitations = summary.get("limitations", [])

        # Slices and failures
        failed_cases = [c for c in candidate_cases if c.get("status") in {"rejected", "needs_revision", "needs_review"}]
        accepted_cases = [c for c in candidate_cases if c.get("status") == "accepted"]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RAGTrust Quality & Explainability Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px; background: #f8fafc; color: #1e293b; line-height: 1.5; }}
    .container {{ max-width: 1100px; margin: 0 auto; background: #ffffff; padding: 36px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
    .header {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; margin-bottom: 24px; }}
    h1 {{ color: #0f172a; margin: 0 0 8px 0; font-size: 28px; }}
    .subtitle {{ color: #64748b; font-size: 14px; margin: 0; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
    .badge-green {{ background: #dcfce7; color: #15803d; }}
    .badge-amber {{ background: #fef3c7; color: #b45309; }}
    .badge-blue {{ background: #e0f2fe; color: #0369a1; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 24px 0; }}
    .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; }}
    .card-num {{ font-size: 28px; font-weight: 700; color: #0f172a; margin: 4px 0; }}
    .card-label {{ font-size: 13px; color: #64748b; text-transform: uppercase; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
    th {{ background: #f1f5f9; color: #334155; font-weight: 600; }}
    tr:hover {{ background: #f8fafc; }}
    .section-title {{ font-size: 18px; font-weight: 700; color: #0f172a; margin: 32px 0 12px 0; }}
    .alert-box {{ background: #eff6ff; border-left: 4px solid #3b82f6; padding: 14px 18px; border-radius: 0 8px 8px 0; margin: 16px 0; font-size: 14px; }}
    .failure-item {{ background: #fff1f2; border: 1px solid #fecdd3; border-radius: 6px; padding: 12px; margin-bottom: 10px; }}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <div style="float: right;">
      <span class="badge badge-blue">Run ID: {summary.get('run_id')}</span>
    </div>
    <h1>🛡️ RAGTrust Evaluation Dataset Quality Report</h1>
    <p class="subtitle">Platform: RAGTrust Multi-Agent Architect &bull; Generated: {summary.get('generated_at')}</p>
  </div>

  {f'<div class="alert-box"><strong>Fixture disclosure:</strong> Generation and semantic evaluation used deterministic local demonstration rules, not live Foundry model calls. These results must not be presented as model-assessed quality.</div>' if summary.get('execution_mode') == 'fixture' else ''}

  <div class="grid">
    <div class="card">
      <div class="card-label">Total Generated</div>
      <div class="card-num">{counts.get('generated', 0)}</div>
    </div>
    <div class="card">
      <div class="card-label">Accepted Yield</div>
      <div class="card-num" style="color: #16a34a;">{counts.get('accepted', 0)} ({summary.get('acceptance_rate', 0)*100:.1f}%)</div>
    </div>
    <div class="card">
      <div class="card-label">Repaired Cases</div>
      <div class="card-num" style="color: #ea580c;">{counts.get('repairs_attempted', 0)}</div>
    </div>
    <div class="card">
      <div class="card-label">Rejected / Defective</div>
      <div class="card-num" style="color: #dc2626;">{counts.get('rejected', 0)}</div>
    </div>
    <div class="card">
      <div class="card-label">Review Queued</div>
      <div class="card-num" style="color: #d97706;">{counts.get('needs_review', 0)}</div>
    </div>
  </div>

  <div class="section-title">📊 Dataset-Level Quality & Diversity Metrics</div>
  <table>
    <thead>
      <tr>
        <th>Metric Dimension</th>
        <th>Measured Value</th>
        <th>Target Benchmark</th>
        <th>Interpretation & Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Topic Coverage Ratio</strong></td>
        <td>{ds_metrics.get('topic_coverage', {}).get('coverage_ratio', 1.0) * 100:.1f}%</td>
        <td>&ge; 80.0%</td>
        <td>{ds_metrics.get('topic_coverage', {}).get('met_topics', 0)} / {ds_metrics.get('topic_coverage', {}).get('total_topics', 0)} topics met quota</td>
      </tr>
      <tr>
        <td><strong>Exact Duplication Rate</strong></td>
        <td>{ds_metrics.get('exact_duplicate_rate', 0.0) * 100:.2f}%</td>
        <td>&le; 2.0%</td>
        <td>Normalized text SHA-256 hash collision rate</td>
      </tr>
      <tr>
        <td><strong>Semantic Redundancy (Near-Duplicates)</strong></td>
        <td>{len(ds_metrics.get('semantic_duplicate_pairs', []))} pairs</td>
        <td>&le; 3 pairs</td>
        <td>N-gram cosine similarity threshold &ge; 0.82</td>
      </tr>
      <tr>
        <td><strong>Jensen-Shannon Distribution Distance</strong></td>
        <td>{ds_metrics.get('jensen_shannon_divergence', 0.0):.4f}</td>
        <td>&le; 0.2500</td>
        <td>Divergence between target topic mix and generated volume</td>
      </tr>
      <tr>
        <td><strong>Average Faithfulness (Accepted)</strong></td>
        <td>{f"{ds_metrics.get('avg_faithfulness'):.3f}" if ds_metrics.get('avg_faithfulness') is not None else "Not assessed"}</td>
        <td>&ge; 0.900</td>
        <td>Supported factual claims / total claims against source evidence</td>
      </tr>
      <tr>
        <td><strong>Human-Audited Correctness Rate</strong></td>
        <td>{f"{audit.get('fully_correct_rate') * 100:.1f}%" if audit.get('fully_correct_rate') is not None else "Not assessed"}</td>
        <td>&ge; 90.0%</td>
        <td>Sample size: {audit.get('sample_size', 0)} ({audit.get('confidence_interval', '')})</td>
      </tr>
    </tbody>
  </table>

  <div class="section-title">🔍 Traceability & Failed Claim Explanations</div>
  <p style="font-size: 14px; color: #64748b;">
    In accordance with RAGTrust transparency rules, the evaluator does not simply assign a low score; it isolates exact failed factual claims and nonexistent citations:
  </p>
"""
        if failed_cases:
            for fc in failed_cases[:6]:
                fc_id = fc.get("id", fc.get("case_id", "case"))
                status = fc.get("status")
                badge_class = "badge-amber" if status == "needs_review" else "badge-green"
                reasons = fc.get("failed_checks") or [fc.get("concise_reason", "Verification threshold not met")]
                html += f"""
  <div class="failure-item">
    <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
      <strong>Case ID: {fc_id}</strong>
      <span class="badge {badge_class}">{status}</span>
    </div>
    <div style="font-size: 13px; margin-bottom: 4px;"><strong>Question:</strong> {fc.get('question')}</div>
    <div style="font-size: 13px; margin-bottom: 4px;"><strong>Answer:</strong> {fc.get('candidate_reference_answer')}</div>
    <div style="font-size: 12px; color: #991b1b;"><strong>Evaluator Diagnosis:</strong> {', '.join(reasons)}</div>
  </div>
"""
        else:
            html += "<p><em>No rejected or repairable candidates in this run.</em></p>"

        html += f"""
  <div class="section-title">⚠️ Limitations & Disclosures</div>
  <div class="alert-box">
    <strong>Auditor Disclosure:</strong>
    <ul>
      {"".join(f"<li>{lim}</li>" for lim in limitations)}
      <li>Model evaluation is an automated estimate of support based on extracted evidence, not independent proof of external reality.</li>
      <li>Do not treat thousands of paraphrases as independent statistical observations.</li>
    </ul>
  </div>
  <div class="section-title">📦 Provenance and Versions</div>
  <pre style="white-space: pre-wrap; background:#f8fafc; padding:14px; border:1px solid #e2e8f0;">{json.dumps(summary.get('provenance', {}), indent=2)}</pre>
</div>
</body>
</html>
"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return html
