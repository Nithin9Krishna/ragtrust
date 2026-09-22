from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from ragtrust.agents.repair import RefinementRepairAgent
from ragtrust.agents.planner import PlanningAgent
from ragtrust.agents.verifier import ValidationAgent
from ragtrust.db import session_scope
from ragtrust.models import CandidateCase, DatasetVersion
from ragtrust.orchestrator import OrchestrationService
from ragtrust.schemas import CaseStatus, GenerationConfig
from ragtrust.services.extractor import SourceExtractor


def verify(answer: str, *, refs=None, required=None, behavior="answer"):
    return ValidationAgent().run(
        {
            "question": "What does the policy require?",
            "candidate_reference_answer": answer,
            "expected_behavior": behavior,
            "evidence_segments": [{"locator": "policy:sec1", "text": "Passwords require 14 characters and numbers."}],
            "evidence_refs": refs if refs is not None else ["policy:sec1"],
            "valid_locators": {"policy:sec1"},
            "required_facts": required if required is not None else ["14 characters", "numbers"],
        },
        mode="fixture",
    )


def test_wrong_number_and_unsupported_claim_are_detected():
    result = verify("Passwords require 8 characters. Free pet insurance is included.")
    assert result["suggested_status"] == CaseStatus.rejected
    assert result["faithfulness_score"] < 1.0
    assert result["failed_claims"]


def test_incomplete_answer_requires_revision():
    result = verify("Passwords require 14 characters.")
    assert result["completeness_score"] < 1.0
    assert result["suggested_status"] in {CaseStatus.needs_revision, CaseStatus.rejected}


def test_invalid_citation_is_hard_failure():
    result = verify("Passwords require 14 characters and numbers.", refs=["missing:sec9"])
    assert result["citation_valid"] is False
    assert result["suggested_status"] == CaseStatus.rejected


def test_valid_unanswerable_case_is_accepted():
    result = verify(
        "The documentation does not provide enough information to answer.",
        refs=[], required=[], behavior="abstain",
    )
    assert result["answerability_score"] == 1.0
    assert result["suggested_status"] == CaseStatus.accepted


def test_bounded_repair_stops_at_limit():
    result = RefinementRepairAgent().run(
        {"candidate": {"attempt_number": 2}, "failed_claims": ["bad"], "evidence_segments": [], "max_repairs": 2},
        mode="fixture",
    )
    assert result["repaired"] is False
    assert result["status"] == CaseStatus.needs_review


def test_invalid_media_timestamp_is_rejected():
    payload = json.dumps({"segments": [{"start": 12, "end": 4, "text": "Impossible range"}]})
    with pytest.raises(ValueError, match="Invalid media timestamp"):
        SourceExtractor.extract_text_segments(payload, "bad.video.json", asset_id="asset")


def test_planner_never_creates_negative_topic_quotas():
    golden = [
        {"question": f"Q{i}", "trusted_answer": f"A{i}", "topic": f"topic-{i}"}
        for i in range(6)
    ]
    plan = PlanningAgent().run(
        {"golden_examples": golden, "evidence_segments": [], "config": GenerationConfig(candidate_target=4, accepted_target=2)},
        mode="fixture",
    )
    assert sum(plan["topic_quotas"].values()) == 4
    assert all(value >= 0 for value in plan["topic_quotas"].values())


def test_repairs_create_linked_attempt_and_releases_are_immutable(monkeypatch):
    service = OrchestrationService()
    project_id = service.create_project("Revision history test", domain="security")
    service.add_golden_examples(project_id, [{"external_id":"g-linked","question":"What is required?","trusted_answer":"Passwords require 14 characters and numbers.","topic":"access"}])
    service.add_source_asset(project_id,"policy.txt","text/plain","sha","storage/policy.txt",[{"locator":"policy:sec1","text":"Passwords require 14 characters and numbers.","modality":"text"}])

    candidate = {
        "question":"What does the password policy require?",
        "candidate_reference_answer":"Passwords require 14 characters. Numbers are required. Free pet insurance is included.",
        "expected_behavior":"answer","topic":"access","scenario_type":"direct","difficulty":"easy","modality":"text",
        "seed_ids":[],"source_version_ids":[],"evidence_refs":["policy:sec1"],"required_facts":["14 characters","numbers"],"reference_origin":"automatically_derived",
    }
    monkeypatch.setattr(service.generator, "run", lambda inputs, mode="fixture": [dict(candidate)])
    run_id = service.execute_generation_run(project_id, GenerationConfig(candidate_target=1,accepted_target=1,max_repairs=1,budget_units=5), mode="fixture")

    with session_scope() as session:
        cases = session.scalars(select(CandidateCase).where(CandidateCase.run_id == run_id)).all()
        assert len(cases) == 2
        child = next(c for c in cases if c.parent_attempt_id)
        root = next(c for c in cases if not c.parent_attempt_id)
        assert child.parent_attempt_id == root.id
        assert child.attempt_number == 1

    first = service.release_dataset_version(run_id)
    second = service.release_dataset_version(run_id)
    with session_scope() as session:
        releases = session.scalars(select(DatasetVersion).where(DatasetVersion.id.in_([first,second]))).all()
        assert {r.version_number for r in releases} == {1,2}
        assert all(r.immutable for r in releases)
