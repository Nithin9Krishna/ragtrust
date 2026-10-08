from __future__ import annotations

import hashlib
from pathlib import Path

from .db import workspace_data_dir


class LocalStorage:
    """Project-isolated local storage with a Blob-compatible boundary."""

    def __init__(self, root: Path | None = None):
        self.root = root or workspace_data_dir() / "storage"
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe(self, value: str) -> str:
        return "".join(c for c in value if c.isalnum() or c in "-_.").strip(".") or "file"

    def put(self, project_id: str, category: str, filename: str, content: bytes) -> tuple[str, str]:
        digest = hashlib.sha256(content).hexdigest()
        folder = self.root / self._safe(project_id) / self._safe(category)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{digest[:12]}-{self._safe(Path(filename).name)}"
        path.write_bytes(content)
        return str(path), digest

    def read(self, path: str) -> bytes:
        resolved = Path(path).resolve()
        if self.root.resolve() not in resolved.parents:
            raise ValueError("Storage path is outside the configured root")
        return resolved.read_bytes()

    def release_dir(self, project_id: str, version: int) -> Path:
        path = self.root / self._safe(project_id) / "releases" / f"v{version}"
        path.mkdir(parents=True, exist_ok=False)
        return path
