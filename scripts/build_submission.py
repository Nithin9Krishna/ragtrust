"""Create a clean, inspectable handoff without credentials or runtime databases."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
SOURCE_DIRS = ("src/ragtrust", "scripts", "tests", "docs", "demo_data")
SOURCE_FILES = ("README.md", "pyproject.toml", "requirements.txt", "Dockerfile",
    "docker-compose.yml", ".env.example", ".gitignore", ".dockerignore")
RELEASE_FILES = ("dataset.jsonl", "dataset.csv", "case_assessments.jsonl", "quality_report.html", "summary.json")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True, help="Existing measured release directory")
    args = parser.parse_args()
    release = args.release.resolve()
    if not release.is_relative_to(ROOT / "data/releases"):
        raise SystemExit("Choose an existing release under data/releases")
    evidence = {name: (release / name).read_bytes() for name in RELEASE_FILES}
    summary = json.loads(evidence["summary.json"])
    if summary["execution_mode"] != "foundry":
        raise SystemExit("The live evidence package requires a measured Foundry release")

    source_paths = [ROOT / name for name in SOURCE_FILES]
    for directory in SOURCE_DIRS:
        source_paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file()
            and "__pycache__" not in p.parts and p.suffix != ".pyc")
    source_paths.append(ROOT / "output/pdf/RAGTrust_Final_Report.pdf")
    contents = {str(p.relative_to(ROOT)): p.read_bytes() for p in sorted(set(source_paths))}
    private_path = ROOT / ".private/demo-password.txt"
    if private_path.exists():
        secret = private_path.read_bytes().strip()
        if secret and any(secret in data for data in [*contents.values(), *evidence.values()]):
            raise SystemExit("Private password detected: refusing to package")
    banned = {".env", ".private", ".venv", ".git", "__pycache__"}
    assert not any(banned.intersection(Path(name).parts) for name in contents)
    assert not any(Path(name).suffix in {".db", ".sqlite", ".pyc"} for name in contents)
    ARTIFACTS.mkdir(exist_ok=True)
    source_zip = ARTIFACTS / "RAGTrust_Source.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            archive.writestr("RAGTrust/" + name, data)
    evidence_zip = ARTIFACTS / "RAGTrust_Live_Evidence.zip"
    with zipfile.ZipFile(evidence_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in evidence.items():
            archive.writestr(name, data)

    manifest = {
        "packaged_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Text-first RAGTrust demonstration and owner-recorded course submission",
        "video_recorded": False, "course_submitted": False,
        "evidence_run_id": summary["run_id"],
        "evidence_generated_at": summary["generated_at"],
        "source_sha256": {name: sha256(data) for name, data in contents.items()},
        "evidence_sha256": {name: sha256(data) for name, data in evidence.items()},
    }
    bundle = ARTIFACTS / "RAGTrust_Submission_Bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source_zip, source_zip.name)
        archive.write(evidence_zip, evidence_zip.name)
        archive.writestr("RAGTrust_Final_Report.pdf", contents["output/pdf/RAGTrust_Final_Report.pdf"])
        for name, data in contents.items():
            if name.startswith("docs/"):
                archive.writestr(name, data)
        archive.writestr("package_manifest.json", json.dumps(manifest, indent=2))
    for path in (source_zip, evidence_zip, bundle):
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
        print(f"{path.name}: {path.stat().st_size:,} bytes; SHA256 {sha256(path.read_bytes())}")
    (ARTIFACTS / "SHA256SUMS.txt").write_text("\n".join(
        f"{sha256(p.read_bytes())}  {p.name}" for p in (source_zip, evidence_zip, bundle)) + "\n")


if __name__ == "__main__":
    main()
