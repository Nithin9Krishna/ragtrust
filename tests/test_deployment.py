import importlib.util
import json
import sys
import zipfile
from pathlib import Path


def test_public_deployment_keeps_legacy_gate_and_excludes_private_data(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("deploy_web", Path(__file__).parents[1] / "scripts/deploy_web.py")
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)
    for relative, content in {
        ".private/demo-password.txt": "legacy-test-password",
        ".env": "FOUNDRY_PROJECT_ENDPOINT=https://private-project.example/",
        "data/owner.db": "private-owner-data",
        "src/ragtrust/app.py": "print('public app')",
        ".streamlit/config.toml": "[server]\nmaxUploadSize = 5\n",
        "README.md": "demo", "pyproject.toml": "", "requirements.txt": "",
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    monkeypatch.setattr(deploy, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["deploy_web.py", "--app", "test-app", "--resource-group", "test-group", "--public-demo"])
    calls, configurations = [], []
    def azure(*args):
        calls.append(args)
        if args[:4] == ("webapp", "config", "appsettings", "set"):
            configurations.append(json.loads(Path(args[-1][1:]).read_text()))
        return "{}"
    monkeypatch.setattr(deploy, "az", azure)
    deploy.main()
    config = configurations[0]
    assert config["RAGTRUST_PUBLIC_DEMO"] == "true"
    assert config["RAGTRUST_MODE"] == "fixture"
    assert config["RAGTRUST_ACCESS_PASSWORD"] == "legacy-test-password"
    assert config["FOUNDRY_PROJECT_ENDPOINT"] == ""
    assert config["PROJECT_CONNECTION_STRING"] == ""
    assert config["APPLICATIONINSIGHTS_CONNECTION_STRING"] == ""
    assert all(call[:2] != ("webapp", "stop") for call in calls)
    deployment = next(call for call in calls if call[:2] == ("webapp", "deploy"))
    assert deployment[deployment.index("--track-status") + 1] == "false"
    with zipfile.ZipFile(tmp_path / "artifacts/ragtrust-deploy.zip") as archive:
        assert ".streamlit/config.toml" in archive.namelist()
        assert "src/ragtrust/app.py" in archive.namelist()
        assert all(not name.startswith((".env", ".private/", "data/")) for name in archive.namelist())
