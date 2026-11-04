"""User configuration (non-secret settings).

Secrets (API keys) never live here — see ``core.secrets``.
"""

from __future__ import annotations

import copy
from typing import Any

import yaml

from . import paths

DEFAULTS: dict[str, Any] = {
    "terms_accepted_version": None,
    "theme": "osint-dark",
    "enabled_tools": {},          # id -> bool
    "ai": {
        "active_provider": "opencode",  # Default to OpenCode (works out of box)
        "providers": {
            "ollama": {"base_url": "http://localhost:11434", "model": ""},
            "lmstudio": {"base_url": "http://localhost:1234/v1", "model": ""},
            "openai_compatible": {"base_url": "", "model": ""},
            "anthropic": {"base_url": "https://api.anthropic.com", "model": ""},
            "gemini": {"base_url": "https://generativelanguage.googleapis.com", "model": ""},
            "opencode": {"base_url": "http://localhost:4096", "model": "", "binary": "opencode"},
        },
        "require_approval_for_active": True,
        "allow_cloud": False,
    },
    "web": {"enabled": False, "host": "127.0.0.1", "port": 8765},
    "safety": {
        "active_tools_acknowledged": False,
        "request_delay_seconds": 1.0,
        "max_requests_per_minute": 30,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load() -> dict[str, Any]:
    path = paths.config_path()
    if not path.exists():
        return copy.deepcopy(DEFAULTS)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    return _deep_merge(DEFAULTS, data)


def save(config: dict[str, Any]) -> None:
    path = paths.config_path()
    path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def update(**changes: Any) -> dict[str, Any]:
    """Load, deep-merge top-level changes, save, and return the result."""
    config = load()
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key] = _deep_merge(config[key], value)
        else:
            config[key] = value
    save(config)
    return config
