"""Tool runner.

Executes a tool in one of three ways and returns a structured result. Safety
rules are enforced here:

* the responsible-use notice must be accepted;
* active tools additionally require the active-tools acknowledgment;
* external binaries are launched with an argv list (never a shell), with a
  timeout;
* outbound work is rate-limited and politely delayed;
* secrets are redacted from all captured output.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .. import paths
from . import logging_setup, safety, secrets as secrets_mod, workspace as ws_mod
from .registry import Tool

log = logging_setup.get_logger("osint_toolkit.runner")


@dataclass
class RunResult:
    tool_id: str
    tool_name: str
    ok: bool
    summary: str = ""
    data: Any = None
    error: str = ""
    duration: float = 0.0
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_adapter(spec: str):
    module_name, _, func_name = spec.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def _which(binary: str) -> str | None:
    local = paths.tools_bin_dir() / (binary + (".exe" if __import__("os").name == "nt" else ""))
    if local.exists():
        return str(local)
    return shutil.which(binary)


def _build_argv(command: list[str], inputs: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    for part in command:
        value = part
        for key, val in inputs.items():
            value = value.replace("{" + key + "}", str(val))
        argv.append(value)
    return argv


def _run_adapter(tool: Tool, inputs: dict[str, Any], timeout: int) -> RunResult:
    func = _load_adapter(tool.adapter)  # type: ignore[arg-type]
    output = func(**inputs)
    summary = ""
    data = output
    if isinstance(output, dict):
        summary = str(output.pop("summary", "") or "")
    return RunResult(
        tool_id=tool.id, tool_name=tool.name, ok=True, summary=summary, data=data
    )


def _run_command(tool: Tool, inputs: dict[str, Any], timeout: int) -> RunResult:
    assert tool.command
    binary = tool.command[0]
    resolved = _which(binary)
    if not resolved:
        hint = tool.install.get("url") or tool.homepage or "its official website"
        return RunResult(
            tool_id=tool.id,
            tool_name=tool.name,
            ok=False,
            error=f"'{binary}' is not installed. Install it from {hint} (the app "
            f"can auto-download some tools from Settings).",
        )
    argv = _build_argv(tool.command, inputs)
    argv[0] = resolved
    safety.polite_delay()
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return RunResult(
        tool_id=tool.id,
        tool_name=tool.name,
        ok=completed.returncode == 0,
        summary=(completed.stdout or "").strip()[:4000],
        data={"returncode": completed.returncode, "output": output.strip()},
        error="" if completed.returncode == 0 else f"exited with code {completed.returncode}",
    )


def _run_url(tool: Tool, inputs: dict[str, Any]) -> RunResult:
    url = tool.url or ""
    for key, val in inputs.items():
        url = url.replace("{" + key + "}", str(val))
    return RunResult(
        tool_id=tool.id,
        tool_name=tool.name,
        ok=True,
        summary=f"Manual tool. Open: {url}",
        data={"url": url},
    )


def run_tool(
    tool: Tool,
    inputs: dict[str, Any] | None = None,
    workspace: ws_mod.Workspace | None = None,
    timeout: int = 120,
    limiter: safety.RateLimiter | None = None,
) -> RunResult:
    inputs = inputs or {}
    safety.require_terms()
    if tool.is_active_tool:
        safety.require_active_authorization()

    if limiter is not None:
        limiter.acquire(tool.id)

    started = time.monotonic()
    try:
        if tool.run_mode == "adapter":
            result = _run_adapter(tool, inputs, timeout)
        elif tool.run_mode == "command":
            result = _run_command(tool, inputs, timeout)
        elif tool.run_mode == "url":
            result = _run_url(tool, inputs)
        else:
            result = RunResult(
                tool_id=tool.id,
                tool_name=tool.name,
                ok=False,
                error="Tool has no run method (adapter, command, or url).",
            )
    except subprocess.TimeoutExpired:
        result = RunResult(
            tool_id=tool.id, tool_name=tool.name, ok=False,
            error=f"Timed out after {timeout}s.",
        )
    except Exception as exc:  # noqa: BLE001 - surface any adapter error to the UI
        log.exception("Tool %s failed", tool.id)
        result = RunResult(
            tool_id=tool.id, tool_name=tool.name, ok=False, error=str(exc)
        )

    result.duration = round(time.monotonic() - started, 2)
    # Redact secrets from anything the user or the AI will see.
    if secrets_mod.known_secret_values():
        payload = json.dumps(result.to_dict(), default=str, ensure_ascii=False)
        result = RunResult(**json.loads(secrets_mod.redact(payload)))

    if workspace is not None:
        ws_mod.append_result(workspace, result.to_dict())
    return result
