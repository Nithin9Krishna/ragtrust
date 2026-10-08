import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ragtrust.agents.rag_eval import RagEvaluationAgent, validate_public_endpoint
from ragtrust.agents.verifier import ValidationAgent
from ragtrust.db import session_scope
from ragtrust.models import CandidateCase, DatasetVersion, GenerationRun, MetricAssessment
from ragtrust.orchestrator import OrchestrationService
from ragtrust.schemas import GenerationConfig, RagEvalRequest, VerificationOutput
from ragtrust.services.reporting import QualityReportGenerator


def project():
    svc = OrchestrationService()
    pid = svc.create_project("Release hardening test")
    svc.add_golden_examples(pid, [{"question": "How long are logs kept?", "trusted_answer": "Logs are retained for 365 days.", "topic": "retention"}])
    return svc, pid


def test_live_contract_cannot_accept_invalid_citations(monkeypatch):
    output = dict(faithfulness_score=1, factual_precision=1, factual_recall=1, factual_f1=1,
        completeness_score=1, relevance_score=1, answerability_score=1, citation_valid=True,
        claims=[{"claim_text": "a", "is_supported": True}], suggested_status="accepted", concise_reason="ok")
    result = ValidationAgent.enforce_evidence_contract(
        {"expected_behavior": "answer", "evidence_refs": ["fake"], "valid_locators": {"real"}, "evidence_segments": [{"text": "a"}]}, output)
    assert result["suggested_status"] == "rejected"
    assert result["citation_valid"] is False
    output["failed_claims"] = [{"claim_text": "Unsupported claim", "reason": "Not in evidence"}]
    from ragtrust.agents.foundry_client import FoundryAgentClient
    monkeypatch.setattr(FoundryAgentClient, "get_instance", lambda: SimpleNamespace(
        run_agent_chat=lambda *args: json.dumps(output)))
    result = ValidationAgent().run(
        {"expected_behavior": "answer", "evidence_refs": ["real"], "valid_locators": {"real"}, "evidence_segments": [{"text": "a"}]}, mode="foundry")
    assert result["suggested_status"] == "needs_revision"
    assert "Unsupported claim" in result["failed_claims"][0]
    assert "Not in evidence" in result["failed_claims"][0]


def test_failed_generation_is_persisted_and_cannot_be_released(monkeypatch):
    svc, pid = project()
    def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr(svc.generator, "run", fail)
    with pytest.raises(RuntimeError):
        svc.execute_generation_run(pid, GenerationConfig(candidate_target=1, accepted_target=1))
    with session_scope() as session:
        run = session.scalar(select(GenerationRun).where(GenerationRun.project_id == pid))
        assert run.status == "failed"
        assert "provider unavailable" in run.error
    with pytest.raises(ValueError, match="completed"):
        svc.release_dataset_version(run.id)


def test_calibration_rows_do_not_leak_into_generation(monkeypatch):
    svc, pid = project()
    svc.add_golden_examples(pid, [{"question": "SECRET held-out question", "trusted_answer": "held-out", "benchmark_role": "held_out"}])
    original = svc.generator.run
    def inspect(inputs, mode):
        assert all("SECRET" not in row["question"] for row in inputs["golden_examples"])
        return original(inputs, mode=mode)
    monkeypatch.setattr(svc.generator, "run", inspect)
    svc.execute_generation_run(pid, GenerationConfig(candidate_target=1, accepted_target=1))


def test_frozen_release_rag_test_does_not_use_later_corrections():
    svc, pid = project()
    rid = svc.execute_generation_run(pid, GenerationConfig(candidate_target=1, accepted_target=1))
    with session_scope() as session:
        case = session.scalar(select(CandidateCase).where(CandidateCase.run_id == rid))
        cid = case.id
    svc.review_case(cid, "approve")
    release = svc.release_dataset_version(rid)
    with session_scope() as session:
        version = session.get(DatasetVersion, release)
        from pathlib import Path
        summary = json.loads((Path(version.storage_path).parent / "summary.json").read_text())
        assert summary["provenance"]["model_or_engine"] == "fixture-rules-v1"
        assert summary["provenance"]["foundry_agent_version"] is None
        assert summary["dataset_metrics"]["after_filtering"]["accepted_count"] == 1
    svc.review_case(cid, "correct", corrected_answer="Changed after publication")
    result = svc.run_rag_test(release, RagEvalRequest(demo_mode=True))
    assert result["results"][0]["reference_answer"] != "Changed after publication"
    with session_scope() as session:
        metrics = session.scalars(select(MetricAssessment).where(MetricAssessment.case_id == cid)).all()
        assert all(m.score is None for m in metrics)


def test_rag_adapter_no_implicit_mock_or_fabricated_quality():
    agent = RagEvaluationAgent()
    with pytest.raises(ValueError, match="Provide"):
        agent.run({"cases": []})
    result = agent.run({"cases": [{"question": "q", "candidate_reference_answer": "a"}], "config": RagEvalRequest(mock_responses={"q": "a"})})
    assert result["avg_faithfulness"] is None
    assert result["avg_relevance"] is None
    assert result["abstention_accuracy"] is None
    assert result["avg_reference_token_recall"] == 1.0


def test_missing_recorded_response_is_error_not_low_score():
    result = RagEvaluationAgent().run({"cases": [{"question": "q"}], "config": RagEvalRequest(mock_responses={"other": "a"})})
    assert result["errors"] == 1
    assert result["total_cases_evaluated"] == 0
    assert result["avg_reference_token_recall"] is None


def test_local_rag_endpoints_are_rejected():
    with pytest.raises(ValueError):
        validate_public_endpoint("https://127.0.0.1/test")


def test_report_escapes_source_and_model_text(tmp_path):
    html = QualityReportGenerator.generate_html_report(
        {"run_id": "x", "execution_mode": "fixture", "limitations": ["<script>bad()</script>"]},
        [{"question": "<script>bad()</script>", "candidate_reference_answer": "<img src=x onerror=bad()>", "status": "rejected"}],
        tmp_path / "report.html")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_api_access_gate_protects_data_and_leaves_health_public(monkeypatch):
    import ragtrust.api as api
    monkeypatch.setattr(api, "settings", SimpleNamespace(access_password="test-private-key", public_demo=False))
    client = TestClient(api.app)
    assert client.get("/health").status_code == 200
    assert client.get("/projects").status_code == 401
    assert client.get("/projects", headers={"X-RAGTrust-Key": "test-private-key"}).status_code == 200
