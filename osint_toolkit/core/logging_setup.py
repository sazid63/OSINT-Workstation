"""Logging with secret redaction.

Anything written to the log is passed through the secret redactor first, so API
keys and tokens can never end up in a log file.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .. import paths
from . import secrets as secrets_mod

_CONFIGURED = False


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        try:
            secrets = secrets_mod.known_secret_values()
        except Exception:
            secrets = []
        original = super().format(record)
        return secrets_mod.redact(original, secrets)


def setup(level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger("osint_toolkit")
    if _CONFIGURED:
        return logger
    logger.setLevel(level)

    logfile = paths.log_dir() / "osint-toolkit.log"
    handler = RotatingFileHandler(logfile, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)

    stream = logging.StreamHandler()
    stream.setFormatter(RedactingFormatter("%(levelname)s: %(message)s"))
    logger.addHandler(stream)

    _CONFIGURED = True
    return logger


def get_logger(name: str = "osint_toolkit") -> logging.Logger:
    if not _CONFIGURED:
        setup()
    return logging.getLogger(name)
