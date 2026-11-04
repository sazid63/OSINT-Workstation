"""Tool registry.

A *tool* is described by a YAML manifest. Built-in manifests ship inside the
package (``osint_toolkit/catalog``); user manifests live in the per-user plugins
directory. Both are merged into one catalog.

A manifest can run in one of three ways:

* ``adapter``  — ``"package.module:function"`` pure-Python entry point.
* ``command``  — an external binary, as an argv list (never a shell string).
* ``url``      — a manual tool: just open a website in the browser.

Inputs are declared so the UI can render a form, and the AI/MCP layer can call a
tool with validated, typed arguments.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .. import config as config_mod
from .. import paths


@dataclass
class InputSpec:
    name: str
    label: str = ""
    type: str = "text"          # text | select | bool
    required: bool = True
    help: str = ""
    placeholder: str = ""
    options: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.label:
            self.label = self.name.replace("_", " ").title()


@dataclass
class Tool:
    id: str
    name: str
    category: str
    description: str = ""
    how_to_use: str = ""
    important: str = ""
    what_to_connect: list[str] = field(default_factory=list)
    safety: str = "passive"          # passive | active
    license: str = "Unknown"
    homepage: str = ""
    tags: list[str] = field(default_factory=list)
    inputs: list[InputSpec] = field(default_factory=list)
    adapter: str | None = None
    command: list[str] | None = None
    url: str | None = None
    install: dict[str, Any] = field(default_factory=dict)
    source: str = "builtin"          # builtin | plugin

    @property
    def is_active_tool(self) -> bool:
        return self.safety.lower() == "active"

    @property
    def run_mode(self) -> str:
        if self.adapter:
            return "adapter"
        if self.command:
            return "command"
        if self.url:
            return "url"
        return "unknown"

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["run_mode"] = self.run_mode
        data["inputs"] = [dataclasses.asdict(i) for i in self.inputs]
        return data


def _parse_inputs(raw: Any) -> list[InputSpec]:
    specs: list[InputSpec] = []
    if not raw:
        return specs
    if isinstance(raw, dict):  # shorthand: {target: "Domain name"}
        for name, label in raw.items():
            specs.append(InputSpec(name=str(name), label=str(label)))
        return specs
    for item in raw:
        if isinstance(item, str):
            specs.append(InputSpec(name=item))
        elif isinstance(item, dict):
            specs.append(InputSpec(**item))
    return specs


def _load_file(path: Path, source: str) -> Tool | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not data.get("id") or not data.get("name"):
        return None
    known = {f.name for f in dataclasses.fields(Tool)}
    # A manifest may declare its own ``source`` ("builtin" / "plugin"); honor it
    # but never let it collide with the positional ``source`` argument.
    kwargs = {k: v for k, v in data.items() if k in known and k != "inputs" and k != "source"}
    kwargs.setdefault("source", source)
    return Tool(inputs=_parse_inputs(data.get("inputs")), **kwargs)


def _iter_manifests(root: Path, source: str):
    if not root.exists():
        return
    for path in sorted(root.rglob("*.yaml")):
        tool = _load_file(path, source)
        if tool:
            yield tool
    for path in sorted(root.rglob("*.yml")):
        tool = _load_file(path, source)
        if tool:
            yield tool


def load_catalog() -> list[Tool]:
    """Load, de-duplicate (builtin wins), and return every tool."""
    merged: dict[str, Tool] = {}
    for tool in _iter_manifests(paths.catalog_dir(), "builtin"):
        merged[tool.id] = tool
    for tool in _iter_manifests(paths.plugins_dir(), "plugin"):
        if tool.id not in merged:
            merged[tool.id] = tool
    return sorted(merged.values(), key=lambda t: (t.category, t.name.lower()))


def categories() -> list[str]:
    return sorted({t.category for t in load_catalog()})


def get_tool(tool_id: str) -> Tool | None:
    for tool in load_catalog():
        if tool.id == tool_id:
            return tool
    return None


def is_enabled(tool_id: str) -> bool:
    enabled = config_mod.load().get("enabled_tools", {})
    return bool(enabled.get(tool_id, True))


def set_enabled(tool_id: str, value: bool) -> None:
    enabled = dict(config_mod.load().get("enabled_tools", {}))
    enabled[tool_id] = value
    config_mod.update(enabled_tools=enabled)


def enabled_tools() -> list[Tool]:
    return [t for t in load_catalog() if is_enabled(t.id)]
