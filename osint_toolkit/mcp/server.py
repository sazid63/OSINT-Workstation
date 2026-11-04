"""MCP tools server (stdio, JSON-RPC 2.0, newline-delimited).

Lets OpenCode and any other MCP client use the Toolkit's tools. Headless and
dependency-free: tools run through the same guarded runner as the GUI.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from ..core import logging_setup, registry, runner, safety, workspace as ws

log = logging_setup.get_logger("osint_toolkit.mcp")

TERMS_ENV = "OSINT_TOOLKIT_TERMS"
WORKSPACE_ENV = "OSINT_TOOLKIT_WORKSPACE"


def _mcp_tools() -> list[dict[str, Any]]:
    tools = []
    for tool in registry.enabled_tools():
        properties: dict[str, Any] = {}
        required: list[str] = []
        for inp in tool.inputs:
            kind = "boolean" if inp.type == "bool" else "string"
            props: dict[str, Any] = {"type": kind, "description": inp.help or inp.label}
            if inp.options:
                props["enum"] = inp.options
            properties[inp.name] = props
            if inp.required:
                required.append(inp.name)
        tools.append(
            {
                "name": tool.id,
                "description": f"{tool.description} [SAFETY: {tool.safety}]",
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        )
    return tools


def _active_workspace():
    name = os.environ.get(WORKSPACE_ENV) or "mcp"
    try:
        return ws.load(name)
    except Exception:  # noqa: BLE001
        return None


def _terms_ok() -> bool:
    return (os.environ.get(TERMS_ENV) == "accepted") or safety.terms_accepted()


def _call_tool(name: str, arguments: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    tool = registry.get_tool(name)
    if tool is None:
        return [{"type": "text", "text": f"Unknown tool '{name}'."}], True
    if not _terms_ok():
        return [
            {
                "type": "text",
                "text": (
                    "Responsible-use notice not accepted. Accept it once in the "
                    "GUI, or set the OSINT_TOOLKIT_TERMS=accepted environment "
                    "variable for scripted use."
                ),
            }
        ], True
    result = runner.run_tool(tool, arguments or {}, workspace=_active_workspace())
    body = json.dumps(result.to_dict(), default=str, ensure_ascii=False)
    return [{"type": "text", "text": body}], (not result.ok)


def _respond(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method", "")
    msg_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "osint-toolkit", "version": "0.1.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _mcp_tools()}}
    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        content, is_error = _call_tool(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"content": content, "isError": is_error},
        }
    if method.startswith("notifications/"):
        return None
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    log.info("MCP server starting (stdio)")
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except Exception:
            continue
        response = _respond(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()