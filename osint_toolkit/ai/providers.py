"""Concrete AI providers.

All network provider calls go through ``requests`` directly to the provider's
public API. Secrets are pulled from the keychain at call time and never logged.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

import requests

from ..core import logging_setup, secrets as secrets_mod
from .base import AIProvider, AIResponse, ChatMessage

log = logging_setup.get_logger("osint_toolkit.ai")

TIMEOUT = 90


class ProviderError(RuntimeError):
    pass


def _http_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None,
               timeout: int = TIMEOUT) -> dict[str, Any]:
    resp = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
    if resp.status_code >= 400:
        raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


# --------------------------------------------------------------------------
# Tool schema (OpenAI "function" shape is shared by OpenAI-compat & Ollama)
# --------------------------------------------------------------------------

def openai_tool_schemas(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schemas = []
    for t in tools:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for inp in t.get("inputs", []):
            kind = "string"
            if inp.get("type") == "bool":
                kind = "boolean"
            props: dict[str, Any] = {"type": kind, "description": inp.get("help") or inp.get("label", inp.get("name", ""))}
            if inp.get("options"):
                props["enum"] = inp["options"]
            properties[inp["name"]] = props
            if inp.get("required", True):
                required.append(inp["name"])
        desc = f"{t.get('description','')} [SAFETY LEVEL: {t.get('safety','passive')}]"
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": t["id"],
                    "description": desc,
                    "parameters": {"type": "object", "properties": properties, "required": required},
                },
            }
        )
    return schemas


def _msgs_openai(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id or "", "content": m.content})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def _parse_openai_response(data: dict[str, Any]) -> AIResponse:
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {}) or {}
    text = message.get("content") or ""
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {}) or {}
        try:
            arguments = json.loads(fn.get("arguments") or "{}")
        except Exception:
            arguments = {}
        calls.append(
            {
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "arguments": arguments,
            }
        )
    return AIResponse(text=str(text), tool_calls=calls)


class OpenAICompatibleProvider(AIProvider):
    id = "openai_compatible"

    def warmup(self) -> str:
        base = (self.config.get("base_url") or "").rstrip("/")
        if not base:
            return "No base URL configured."
        if not secrets_mod.get_secret("OPENAI_COMPATIBLE_API_KEY"):
            return "No API key set for this provider."
        return "ready"

    def chat(self, messages, tools=None, **kwargs: Any):
        base = (self.config.get("base_url") or "").rstrip("/")
        model = self.config.get("model") or ""
        key = secrets_mod.get_secret("OPENAI_COMPATIBLE_API_KEY")
        if not base or not model:
            return AIResponse(error="Provider not configured (base URL and model required).")
        headers = {"Authorization": f"Bearer {key or ''}"}
        payload: dict[str, Any] = {
            "model": model,
            "messages": _msgs_openai(messages),
        }
        if tools:
            payload["tools"] = openai_tool_schemas(tools)
            payload["tool_choice"] = "auto"
        data = _http_json(f"{base}/chat/completions", payload, headers)
        response = _parse_openai_response(data)
        if kwargs.get("warn_key"):
            log.info("OpenAI-compatible chat completed (%s)", model)
        return response


class OllamaProvider(AIProvider):
    id = "ollama"

    def warmup(self) -> str:
        base = (self.config.get("base_url") or "http://localhost:11434").rstrip("/")
        try:
            requests.get(f"{base}/api/tags", timeout=5).raise_for_status()
            return "ready" if self.config.get("model") else "Ollama is running; pick a model in Settings."
        except Exception as exc:  # noqa: BLE001
            return f"Ollama not reachable at {base}: {exc}"

    def chat(self, messages, tools=None, **kwargs: Any):
        base = (self.config.get("base_url") or "http://localhost:11434").rstrip("/")
        model = self.config.get("model") or ""
        if not model:
            return AIResponse(error="No model selected for Ollama.")
        payload: dict[str, Any] = {"model": model, "messages": _msgs_openai(messages), "stream": False}
        if tools:
            payload["tools"] = openai_tool_schemas(tools)
        data = _http_json(f"{base}/api/chat", payload)
        message = data.get("message", {}) or {}
        text = message.get("content") or ""
        calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {}) or {}
            calls.append(
                {
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", {}) or {},
                }
            )
        return AIResponse(text=str(text), tool_calls=calls)


class AnthropicProvider(AIProvider):
    id = "anthropic"

    def warmup(self) -> str:
        if not secrets_mod.get_secret("ANTHROPIC_API_KEY"):
            return "No Anthropic API key set."
        if not self.config.get("model"):
            return "Pick an Anthropic model in Settings."
        return "ready"

    def chat(self, messages, tools=None, **kwargs: Any):
        model = self.config.get("model") or ""
        key = secrets_mod.get_secret("ANTHROPIC_API_KEY")
        if not model or not key:
            return AIResponse(error="Anthropic not configured (model and API key required).")
        system = "\n".join(m.content for m in messages if m.role == "system")
        conv: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                content = [{"type": "tool_result", "tool_use_id": m.tool_call_id or "", "content": m.content}]
                conv.append({"role": "user", "content": content})
            else:
                conv.append({"role": m.role, "content": m.content})
        payload: dict[str, Any] = {"model": model, "max_tokens": 4096, "messages": conv}
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {"name": t["id"], "description": t.get("description", ""),
                 "input_schema": t["function"]["parameters"]}
                for t in openai_tool_schemas(tools)
            ]
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        data = _http_json("https://api.anthropic.com/v1/messages", payload, headers)
        text = ""
        calls = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                calls.append(
                    {"id": block.get("id", ""), "name": block.get("name", ""),
                     "arguments": block.get("input", {}) or {}}
                )
        return AIResponse(text=text, tool_calls=calls)


class GeminiProvider(AIProvider):
    id = "gemini"

    def warmup(self) -> str:
        if not secrets_mod.get_secret("GEMINI_API_KEY"):
            return "No Gemini API key set."
        if not self.config.get("model"):
            return "Pick a Gemini model in Settings."
        return "ready"

    def chat(self, messages, tools=None, **kwargs: Any):
        model = self.config.get("model") or ""
        base = (self.config.get("base_url") or "https://generativelanguage.googleapis.com").rstrip("/")
        key = secrets_mod.get_secret("GEMINI_API_KEY")
        if not model or not key:
            return AIResponse(error="Gemini not configured (model and API key required).")
        contents: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                contents.append(
                    {"role": "function", "parts": [
                        {"functionResponse": {"name": m.name or "", "response": {"result": m.content}}}]}
                )
            else:
                contents.append({"role": m.role, "parts": [{"text": m.content}]})
        payload: dict[str, Any] = {"contents": contents}
        if tools:
            payload["tools"] = [
                {"functionDeclarations": [
                    {"name": t["id"], "description": t.get("description", ""),
                     "parameters": t["function"]["parameters"]}
                    for t in openai_tool_schemas(tools)
                ]}
            ]
        url = f"{base}/v1beta/models/{model}:generateContent"
        data = _http_json(f"{url}?key={key}", payload)
        parts = ((data.get("candidates") or [{}])[0].get("content", {}) or {}).get("parts", []) or []
        text = ""
        calls = []
        for part in parts:
            if "text" in part:
                text += part["text"]
            if "functionCall" in part:
                fc = part["functionCall"]
                calls.append({"id": fc.get("name", "fc"), "name": fc.get("name", ""),
                              "arguments": fc.get("args", {}) or {}})
        return AIResponse(text=text, tool_calls=calls)


class OpenCodeProvider(AIProvider):
    """Drives a local OpenCode CLI agent (which can in turn use this toolkit
    through its MCP server). No API key needed."""

    id = "opencode"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.binary = (config or {}).get("binary") or "opencode"

    def _resolve_binary(self) -> str:
        """Resolve binary path, handling Windows .CMD/.BAT files."""
        import os
        from shutil import which
        if os.path.isabs(self.binary):
            return self.binary
        path = which(self.binary)
        if path:
            return path
        # On Windows, .CMD/.BAT files need shell=True or explicit cmd.exe
        if os.name == "nt":
            for ext in (".cmd", ".bat", ".exe"):
                path = which(self.binary + ext)
                if path:
                    return path
        return self.binary  # let subprocess handle the error

    def warmup(self) -> str:
        import os
        path = self._resolve_binary()
        if not path or not os.path.exists(path):
            return f"OpenCode CLI '{self.binary}' not found on PATH."
        return "ready"

    def chat(self, messages, tools=None, **kwargs: Any):
        import os
        prompt = "\n".join(m.content for m in messages if m.role in ("user", "assistant"))
        if not prompt.strip():
            return AIResponse(error="Empty prompt for OpenCode.")
        # OpenCode CLI: positional message argument, --format json
        binary = self._resolve_binary()
        # On Windows, .CMD/.BAT needs shell=True
        use_shell = os.name == "nt" and binary.lower().endswith((".cmd", ".bat"))
        cmd = [binary, "run", "--format", "json", prompt]
        try:
            completed = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, shell=use_shell
            )
        except FileNotFoundError:
            return AIResponse(error=f"OpenCode CLI '{self.binary}' not found.")
        except subprocess.TimeoutExpired:
            return AIResponse(error="OpenCode run timed out.")
        if completed.returncode != 0:
            return AIResponse(error=f"OpenCode exited {completed.returncode}: {completed.stderr[:400]}")
        # OpenCode streams JSON lines - take the last text part
        raw = completed.stdout.strip()
        text = ""
        for line in raw.splitlines():
            try:
                data = json.loads(line)
                if data.get("type") == "text":
                    part = data.get("part", {})
                    text = part.get("text", "") or text
            except Exception:
                pass
        if not text:
            text = raw  # fallback
        return AIResponse(text=str(text))


PROVIDERS: dict[str, type[AIProvider]] = {
    "ollama": OllamaProvider,
    "lmstudio": OpenAICompatibleProvider,  # OpenAI-compatible endpoint
    "openai_compatible": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "opencode": OpenCodeProvider,
}


def list_providers() -> list[str]:
    return [
        "ollama", "lmstudio", "openai_compatible", "anthropic", "gemini", "opencode"
    ]


def get_provider(provider_id: str, config: dict[str, Any] | None = None):
    cls = PROVIDERS.get(provider_id)
    if cls is None:
        return None
    return cls(config or {})