from __future__ import annotations

import json
from pathlib import Path

from ragtrust.orchestrator import OrchestrationService
from ragtrust.services.calibration import EvaluatorCalibrationEngine


def test_cohens_kappa_perfect_agreement():
    kappa = EvaluatorCalibrationEngine.compute_cohens_kappa(tp=10, tn=10, fp=0, fn=0)
    assert kappa == 1.0


def test_cohens_kappa_random_agreement():
    kappa = EvaluatorCalibrationEngine.compute_cohens_kappa(tp=5, tn=5, fp=5, fn=5)
    assert kappa == 0.0


def test_evaluator_calibration_on_benchmark():
    demo_dir = Path(__file__).resolve().parent.parent / "demo_data"
    bench_file = demo_dir / "calibration_benchmark.json"
    assert bench_file.exists()

    cases = json.loads(bench_file.read_text())
    service = OrchestrationService()

    def eval_fn(case):
        return service.verifier.run(
            {
                "question": case.get("question"),
                "candidate_reference_answer": case.get("candidate_reference_answer"),
                "expected_behavior": case.get("expected_behavior", "answer"),
                "evidence_segments": case.get("evidence_segments", []),
                "evidence_refs": case.get("evidence_refs", []),
                "valid_locators": set(case.get("valid_locators", ["policy.txt:sec1", "policy.txt:sec2", "policy.txt:sec3", "policy.txt:sec4", "policy.txt:sec5", "policy.txt:sec6"])),
                "required_facts": case.get("required_facts", []),
            }
        )

    res = EvaluatorCalibrationEngine.evaluate_benchmark(cases, eval_fn)
    assert res.total_cases == 15
    assert res.accuracy >= 0.80
    assert res.defect_recall >= 0.80
    assert res.cohens_kappa > 0.60
    assert "TP" in res.confusion_matrix
