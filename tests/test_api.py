from __future__ import annotations

from fastapi.testclient import TestClient

from ragtrust.api import app

client = TestClient(app)


def test_api_create_project_and_profile():
    # 1. Create project
    resp = client.post("/projects", json={"name": "API Test Project", "domain": "compliance"})
    assert resp.status_code == 200
    p_id = resp.json()["project_id"]

    # 2. List projects
    resp = client.get("/projects")
    assert resp.status_code == 200
    assert any(p["id"] == p_id for p in resp.json())

    # 3. Add golden examples
    resp = client.post(
        f"/projects/{p_id}/golden-examples",
        json=[
            {"external_id": "seed-1", "question": "What is MFA?", "trusted_answer": "Multi-factor authentication", "topic": "Access"}
        ],
    )
    assert resp.status_code == 200
    assert resp.json()["added_examples"] == 1

    # 4. Upload source file
    file_content = b"All user accounts require Multi-factor authentication."
    resp = client.post(
        f"/projects/{p_id}/sources",
        files={"file": ("source.txt", file_content, "text/plain")},
    )
    assert resp.status_code == 200
    assert resp.json()["extracted_segments"] >= 1

    # 5. Profile project
    resp = client.post(f"/projects/{p_id}/profile", json={})
    assert resp.status_code == 200
    plan = resp.json()
    assert "topic_quotas" in plan
    assert "topics" in plan

    # 6. Execute generation run
    resp = client.post(
        f"/projects/{p_id}/generation-runs?mode=fixture",
        json={"candidate_target": 4, "accepted_target": 2, "max_repairs": 1},
    )
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    # 7. Get run details
    resp = client.get(f"/generation-runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run_id

    # 8. List cases
    resp = client.get(f"/generation-runs/{run_id}/cases")
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) == 4

    # 9. Review a case
    first_case_id = cases[0]["id"]
    resp = client.post(
        f"/cases/{first_case_id}/review",
        json={"decision": "approve", "notes": "Audited via API"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"

    # 10. Release dataset version
    resp = client.post(f"/generation-runs/{run_id}/releases")
    assert resp.status_code == 200
    dv_id = resp.json()["dataset_version_id"]

    # 11. Fetch report JSON & HTML
    resp = client.get(f"/datasets/{dv_id}/report?format=json")
    assert resp.status_code == 200
    assert "counts" in resp.json()

    resp = client.get(f"/datasets/{dv_id}/report?format=html")
    assert resp.status_code == 200
    assert "<html" in resp.text.lower()
