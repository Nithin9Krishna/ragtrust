from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import sys
import threading

import pytest
from sqlalchemy import select

import ragtrust.config as config
import ragtrust.db as db
import ragtrust.orchestrator as orchestrator
from ragtrust.agents.foundry_client import FoundryAgentClient
from ragtrust.models import CandidateCase, DatasetVersion, GenerationRun, Project
from ragtrust.schemas import GenerationConfig, RagEvalRequest
from ragtrust.storage import LocalStorage


@pytest.fixture
def public_settings(monkeypatch, tmp_path):
    original = config.settings
    public = replace(
        original,
        public_demo=True,
        mode="fixture",
        access_password="private-test-password",
        data_dir=tmp_path / "owner-data",
        database_url=f"sqlite:///{tmp_path / 'owner.db'}",
        max_candidates=20,
        max_repairs=1,
    )
    # Modules import settings by value; replace each existing reference together.
    replaced_modules = set()
    for name, module in list(sys.modules.items()):
        if name.startswith("ragtrust") and getattr(module, "settings", None) is original:
            monkeypatch.setattr(module, "settings", public)
            replaced_modules.add(name)
    token = db.activate_workspace(None)
    try:
        yield public
    finally:
        db.reset_workspace(token)
        # Imports performed inside a test also need their copied reference restored.
        for name, module in list(sys.modules.items()):
            if name.startswith("ragtrust") and name not in replaced_modules and getattr(module, "settings", None) is public:
                module.settings = original


@pytest.fixture
def workspaces(public_settings):
    visitors = (db.PublicWorkspace(), db.PublicWorkspace())
    yield visitors
    for workspace in visitors:
        workspace.close()


@contextmanager
def visitor(workspace):
    token = db.activate_workspace(workspace)
    try:
        yield
    finally:
        db.reset_workspace(token)


def seeded_project(service, name):
    project_id = service.create_project(name, domain="retention")
    service.add_golden_examples(project_id, [{
        "external_id": "logs",
        "question": "How long are audit logs retained?",
        "trusted_answer": "Audit logs are retained for 365 days.",
        "topic": "retention",
    }])
    content = b"Audit logs are retained for 365 days."
    storage = LocalStorage()
    path, digest = storage.put(project_id, "sources", "policy.txt", content)
    service.add_source_asset(
        project_id, "policy.txt", "text/plain", digest, path,
        [{"locator": "policy.txt:sec1", "text": content.decode(), "modality": "text"}],
    )
    return project_id, storage, path


def test_visitors_cannot_read_modify_or_export_each_others_workspaces(workspaces):
    alice, bob = workspaces
    with visitor(alice):
        alice_service = orchestrator.OrchestrationService()
        alice_project, alice_storage, alice_source = seeded_project(alice_service, "Alice")
        run_id = alice_service.execute_generation_run(
            alice_project, GenerationConfig(candidate_target=1, accepted_target=1), mode="fixture",
        )
        with db.session_scope() as session:
            case_id = session.scalar(select(CandidateCase).where(CandidateCase.run_id == run_id)).id
        alice_service.review_case(case_id, "approve")
        release_id = alice_service.release_dataset_version(run_id)
        with db.session_scope() as session:
            release_path = Path(session.get(DatasetVersion, release_id).storage_path)
        assert release_path.is_relative_to(alice.data_dir)
        assert release_path.exists()

    with visitor(bob):
        bob_service = orchestrator.OrchestrationService()
        bob_project, bob_storage, bob_source = seeded_project(bob_service, "Bob")
        assert db.workspace_data_dir() == bob.data_dir
        with db.session_scope() as session:
            assert [p.id for p in session.scalars(select(Project)).all()] == [bob_project]
            assert session.get(Project, alice_project) is None
            assert session.get(GenerationRun, run_id) is None
            assert session.get(DatasetVersion, release_id) is None
        with pytest.raises(ValueError, match="Project not found"):
            bob_service.execute_generation_run(alice_project, GenerationConfig(), mode="fixture")
        with pytest.raises(ValueError, match="Case not found"):
            bob_service.review_case(case_id, "reject")
        with pytest.raises(ValueError, match="Run not found"):
            bob_service.release_dataset_version(run_id)
        with pytest.raises(ValueError, match="Dataset version not found"):
            bob_service.run_rag_test(release_id, RagEvalRequest(demo_mode=True))
        with pytest.raises(ValueError, match="outside"):
            bob_storage.read(alice_source)
        with pytest.raises(ValueError, match="outside"):
            bob_storage.read(str(release_path))
        assert Path(bob_source).is_relative_to(bob.data_dir)

    with visitor(alice):
        assert db.workspace_data_dir() == alice.data_dir
        assert alice_storage.read(alice_source) == b"Audit logs are retained for 365 days."
        with db.session_scope() as session:
            assert [p.id for p in session.scalars(select(Project)).all()] == [alice_project]
            assert session.get(CandidateCase, case_id).status == "accepted"


def test_background_generation_keeps_visitor_context_after_caller_switches(workspaces, monkeypatch):
    alice, bob = workspaces
    started, continue_generation = threading.Event(), threading.Event()
    observed_directories = []
    with visitor(alice):
        service = orchestrator.OrchestrationService()
        project_id, _, _ = seeded_project(service, "Background visitor")
        original_run = service.generator.run

        def paused_generation(inputs, mode="fixture"):
            observed_directories.append(db.workspace_data_dir())
            started.set()
            assert continue_generation.wait(timeout=10), "Caller did not release the worker"
            return original_run(inputs, mode=mode)

        monkeypatch.setattr(service.generator, "run", paused_generation)
        run_id = service.enqueue_generation_run(
            project_id, GenerationConfig(candidate_target=1, accepted_target=1), mode="fixture",
        )
    try:
        assert started.wait(timeout=10), "The worker did not inherit a usable workspace"
        with visitor(bob):
            continue_generation.set()
            service._jobs[run_id].join(timeout=10)
            assert not service._jobs[run_id].is_alive()
            with db.session_scope() as session:
                assert session.get(GenerationRun, run_id) is None
                assert session.scalars(select(CandidateCase)).all() == []
        with visitor(alice):
            with db.session_scope() as session:
                run = session.get(GenerationRun, run_id)
                assert run.status in {"completed", "completed_shortfall"}
                assert run.error is None
                assert session.scalar(select(CandidateCase).where(CandidateCase.run_id == run_id)) is not None
        assert observed_directories == [alice.data_dir]
    finally:
        continue_generation.set()
        service._jobs[run_id].join(timeout=10)


def test_public_operations_without_a_visitor_fail_closed(public_settings):
    for operation in (db.session_scope, db.init_db, db.workspace_data_dir, LocalStorage, orchestrator.OrchestrationService):
        with pytest.raises(RuntimeError, match="isolated visitor workspace"):
            operation()
    assert not public_settings.data_dir.exists()
    assert not Path(public_settings.database_url.removeprefix("sqlite:///")).exists()


def test_public_foundry_and_explicit_foundry_generation_are_blocked(workspaces, monkeypatch):
    # A previously cached live client must not bypass the public-mode guard.
    monkeypatch.setattr(FoundryAgentClient, "_instance", object())
    with pytest.raises(ValueError, match="disabled in the public demo"):
        FoundryAgentClient.get_instance()
    direct_client = FoundryAgentClient()
    assert direct_client.project_client is None
    assert direct_client.openai_client is None

    with visitor(workspaces[0]):
        service = orchestrator.OrchestrationService()
        project_id = service.create_project("No public spend")
        for operation in (service.execute_generation_run, service.enqueue_generation_run):
            with pytest.raises(ValueError, match="fixture generation only"):
                operation(project_id, GenerationConfig(), mode="foundry")
        with db.session_scope() as session:
            assert session.scalars(select(GenerationRun)).all() == []


def test_public_api_cannot_expose_shared_data_even_with_owner_key(public_settings):
    from fastapi.testclient import TestClient
    import ragtrust.api as api

    with TestClient(api.app) as client:
        assert client.get("/health").status_code == 200
        for path in ("/projects", "/docs", "/openapi.json", "/datasets/unknown/export"):
            assert client.get(path).status_code == 403
            assert client.get(path, headers={"X-RAGTrust-Key": public_settings.access_password}).status_code == 403
        assert client.post("/projects", json={"name": "Public API bypass"}).status_code == 403


def element_by_label(elements, label):
    return next(element for element in elements if element.label == label)


def test_streamlit_public_sessions_load_generate_release_and_compare_independently(public_settings):
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parents[1] / "src/ragtrust/app.py"
    alice = AppTest.from_file(app_path, default_timeout=20).run()
    bob = AppTest.from_file(app_path, default_timeout=20).run()
    visitors = []
    try:
        assert not alice.exception
        assert not bob.exception
        visitors = [alice.session_state["_public_workspace"], bob.session_state["_public_workspace"]]
        assert visitors[0] is not visitors[1]
        assert visitors[0].data_dir != visitors[1].data_dir
        assert all(element.label != "Demo access password" for element in alice.text_input)
        assert len(alice.radio) == 1
        assert alice.radio[0].value == "fixture"
        assert len(alice.radio[0].options) == 1
        assert not any(element.label == "Select Project" for element in bob.selectbox)

        element_by_label(alice.button, "Load IT Security Demo Data").click().run()
        assert not alice.exception
        assert any(element.label == "Select Project" for element in alice.selectbox)
        bob.run()
        assert not bob.exception
        assert not any(element.label == "Select Project" for element in bob.selectbox)

        element_by_label(alice.button, "Start Generation & Verification Run").click().run()
        assert not alice.exception
        service = alice.session_state["_public_service"]
        run_id = alice.session_state["active_run_id"]
        service._jobs[run_id].join(timeout=10)
        assert not service._jobs[run_id].is_alive()
        alice.run()
        assert not alice.exception
        element_by_label(alice.button, "🔒 Freeze & Release Dataset Version").click().run()
        assert not alice.exception

        with visitor(visitors[0]):
            with db.session_scope() as session:
                dataset = session.scalar(select(DatasetVersion))
                assert dataset is not None
                frozen_cases = [json.loads(line) for line in Path(dataset.storage_path).read_text().splitlines() if line.strip()]
                project_id = dataset.project_id
        assert frozen_cases
        recordings = {case["question"]: case["candidate_reference_answer"] for case in frozen_cases}
        element_by_label(alice.text_area, "Or recorded responses as a JSON question-to-answer mapping").set_value(json.dumps(recordings))
        element_by_label(alice.button, "Run RAG Endpoint Evaluation").click().run()
        assert not alice.exception
        result = alice.session_state[f"rag_results_{project_id}"]
        assert result["evaluation_mode"] == "recorded"
        assert result["errors"] == 0
        assert result["total_cases_evaluated"] == len(frozen_cases)
        assert result["avg_reference_token_recall"] == 1.0
        bob.run()
        assert not bob.exception
        assert not any(element.label == "Select Project" for element in bob.selectbox)
        assert not any(element.label == "Select Approved Dataset Version" for element in bob.selectbox)
    finally:
        for workspace in visitors:
            workspace.close()
