"""Deploy to an existing Azure web app; never provision or change its billing tier."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import zipfile

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def az(*args):
    return subprocess.run(["az", *args], check=True, capture_output=True, text=True).stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--agent-version", default="2")
    parser.add_argument("--public-demo", action="store_true", help="Publish isolated anonymous fixture workspaces without Foundry access")
    args = parser.parse_args()
    values = {**dotenv_values(ROOT / ".env"), **os.environ}
    endpoint = values.get("FOUNDRY_PROJECT_ENDPOINT") or values.get("PROJECT_CONNECTION_STRING")
    if not args.public_demo and not endpoint:
        raise SystemExit("Configure FOUNDRY_PROJECT_ENDPOINT first")
    password_path = ROOT / ".private" / "demo-password.txt"
    password = ""
    if not args.public_demo:
        password_path.parent.mkdir(mode=0o700, exist_ok=True)
        if not password_path.exists():
            fd = os.open(password_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as file:
                file.write(secrets.token_urlsafe(24))
        password = password_path.read_text().strip()
    config = {
        "RAGTRUST_ACCESS_PASSWORD": password,
        "FOUNDRY_PROJECT_ENDPOINT": endpoint or "", "PROJECT_CONNECTION_STRING": endpoint or "",
        "FOUNDRY_MODEL_NAME": values.get("FOUNDRY_MODEL_NAME") or values.get("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        "FOUNDRY_USE_DEPLOYED_AGENTS": "true", "FOUNDRY_AGENT_VERSION": args.agent_version,
        "RAGTRUST_MODE": "foundry", "RAGTRUST_MAX_CANDIDATES": "20", "RAGTRUST_MAX_REPAIRS": "2",
        "RAGTRUST_DATA_DIR": "/home/data", "RAGTRUST_DATABASE_URL": "sqlite:////home/data/ragtrust.db",
        "SCM_DO_BUILD_DURING_DEPLOYMENT": "true",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
        "OTEL_TRACES_SAMPLER": "microsoft.fixed_percentage",
        "OTEL_TRACES_SAMPLER_ARG": "1.0",
    }
    if args.public_demo:
        config.update({
            "RAGTRUST_PUBLIC_DEMO": "true", "RAGTRUST_MODE": "fixture",
            "RAGTRUST_ACCESS_PASSWORD": "", "RAGTRUST_MAX_REPAIRS": "1",
            "FOUNDRY_PROJECT_ENDPOINT": "", "PROJECT_CONNECTION_STRING": "",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
            "RAGTRUST_SERVICE": "ui", "STREAMLIT_SERVER_MAX_UPLOAD_SIZE": "5",
            "STREAMLIT_SERVER_DISCONNECTED_SESSION_TTL": "120",
        })
    else:
        config["RAGTRUST_PUBLIC_DEMO"] = "false"
    # Older revisions may not implement visitor isolation. Keep the app stopped
    # while changing from a shared private workspace to the public revision.
    if args.public_demo:
        az("webapp", "stop", "-g", args.resource_group, "-n", args.app)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as file:
        json.dump(config, file); file.flush()
        az("webapp", "config", "appsettings", "set", "-g", args.resource_group, "-n", args.app, "--settings", "@" + file.name)
    az("webapp", "config", "set", "-g", args.resource_group, "-n", args.app,
       "--startup-file", "sh scripts/start.sh")
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    archive = artifacts / "ragtrust-deploy.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for name in ["src/ragtrust", "scripts", "demo_data", ".streamlit", "README.md", "pyproject.toml", "requirements.txt"]:
            target = ROOT / name
            for path in target.rglob("*") if target.is_dir() else [target]:
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    output.write(path, path.relative_to(ROOT))
    if args.public_demo:
        print(f"Deploying {archive.name}; isolated public fixture demo enabled", flush=True)
    else:
        print(f"Deploying {archive.name}; access password saved privately at {password_path}", flush=True)
    result = az("webapp", "deploy", "-g", args.resource_group, "-n", args.app, "--src-path", str(archive),
       "--type", "zip", "--restart", "true", "--timeout", "900000")
    if args.public_demo:
        az("webapp", "start", "-g", args.resource_group, "-n", args.app)
    print(result)


if __name__ == "__main__":
    main()
