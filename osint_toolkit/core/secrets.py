"""Secret storage.

Secrets are kept in the operating system keychain (via ``keyring``) when
available, with an environment-variable fallback. They are never written to the
repo, never to logs, and are redacted from anything sent to an AI provider.
"""

from __future__ import annotations

import os
import re
from typing import Iterable

SERVICE = "osint-toolkit"

try:  # keyring is optional at runtime; degrade gracefully
    import keyring

    _HAS_KEYRING = True
except Exception:  # pragma: no cover - environment dependent
    keyring = None  # type: ignore
    _HAS_KEYRING = False


# Names of secrets the app understands, so we can redact them everywhere.
KNOWN_SECRETS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY",
    "SHODAN_API_KEY",
    "VIRUSTOTAL_API_KEY",
)


def keyring_available() -> bool:
    if not _HAS_KEYRING:
        return False
    try:
        backend = keyring.get_keyring()
        name = type(backend).__name__
        return "fail" not in name.lower()
    except Exception:
        return False


def get_secret(name: str) -> str | None:
    """Return a secret from the keychain, else the environment."""
    if _HAS_KEYRING:
        try:
            value = keyring.get_password(SERVICE, name)
            if value:
                return value
        except Exception:
            pass
    return os.environ.get(name) or None


def set_secret(name: str, value: str) -> bool:
    """Store a secret in the keychain. Returns False if keyring is unavailable."""
    if not _HAS_KEYRING:
        return False
    try:
        if value:
            keyring.set_password(SERVICE, name, value)
        else:
            delete_secret(name)
        return True
    except Exception:
        return False


def delete_secret(name: str) -> None:
    if not _HAS_KEYRING:
        return
    try:
        keyring.delete_password(SERVICE, name)
    except Exception:
        pass


def known_secret_values(extra: Iterable[str] = ()) -> list[str]:
    values: list[str] = []
    for name in list(KNOWN_SECRETS) + list(extra):
        value = get_secret(name)
        if value:
            values.append(value)
    # Also sweep the environment for anything that looks like a key.
    for key, value in os.environ.items():
        if value and re.search(r"API_?KEY|SECRET|TOKEN", key, re.I):
            values.append(value)
    return list({v for v in values if v and len(v) >= 6})


def redact(text: str, secrets: Iterable[str] | None = None) -> str:
    """Replace known secret values in ``text`` with a placeholder."""
    if not text:
        return text
    for value in secrets if secrets is not None else known_secret_values():
        if value and value in text:
            text = text.replace(value, "***REDACTED***")
    return text
