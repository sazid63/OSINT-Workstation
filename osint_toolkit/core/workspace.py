"""Local workspaces: where results are stored.

A workspace is a folder under the user's app-data directory that groups the
results of one investigation. Nothing here is ever written to the repository.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import paths


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60] or "workspace"


@dataclass
class Workspace:
    name: str
    path: Path

    @property
    def results_file(self) -> Path:
        return self.path / "results.jsonl"


def create(name: str) -> Workspace:
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    folder = paths.workspaces_dir() / f"{stamp}_{slugify(name)}"
    folder.mkdir(parents=True, exist_ok=True)
    meta = folder / "workspace.json"
    meta.write_text(
        json.dumps({"name": name, "created": stamp}, indent=2), encoding="utf-8"
    )
    return Workspace(name=name, path=folder)


def list_workspaces() -> list[Workspace]:
    out: list[Workspace] = []
    root = paths.workspaces_dir()
    for folder in sorted(root.iterdir(), reverse=True) if root.exists() else []:
        if folder.is_dir():
            name = folder.name
            meta = folder / "workspace.json"
            if meta.exists():
                try:
                    name = json.loads(meta.read_text(encoding="utf-8")).get("name", name)
                except Exception:
                    pass
            out.append(Workspace(name=name, path=folder))
    return out


def load(name: str) -> Workspace:
    return next((w for w in list_workspaces() if w.name == name), None) or create(name)


def append_result(ws: Workspace, record: dict[str, Any]) -> None:
    record.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
    with ws.results_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_results(ws: Workspace) -> list[dict[str, Any]]:
    if not ws.results_file.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in ws.results_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records
