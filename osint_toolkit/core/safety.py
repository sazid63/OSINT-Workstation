"""Safety layer: responsible-use gating and rate limiting.

The Toolkit is for lawful, authorized, educational use. This module enforces
that contract in code rather than trusting a checkbox:

* a one-time responsible-use notice must be accepted;
* active/intrusive tools require an explicit acknowledgment;
* outbound requests are rate-limited to be polite to third-party services.
"""

from __future__ import annotations

import enum
import threading
import time
from dataclasses import dataclass, field

from .. import TERMS_VERSION
from .. import config as config_mod

RESPONSIBLE_USE_TEXT = """\
OSINT Toolkit - Responsible Use Notice

This tool helps you gather information from PUBLIC sources using free and
open-source software. It is for lawful, educational, and authorized use only.

By continuing you agree that:

  1. You will only investigate targets you own or are legally authorized to
     investigate, and you will comply with all applicable laws and with the
     terms of service of any site or API you contact.
  2. You are solely responsible for your actions and any consequences.
  3. You will not use this tool to harass, stalk, defraud, or harm anyone, or to
     attempt to bypass logins, paywalls, CAPTCHAs, or access controls.
  4. The authors provide this software "as is", with no warranty, and accept no
     liability for its use.

Tools marked ACTIVE send traffic directly to a target. Use them only on systems
you own or are explicitly authorized to test.
"""


class SafetyLevel(str, enum.Enum):
    PASSIVE = "passive"
    ACTIVE = "active"

    @classmethod
    def parse(cls, value: str | None) -> "SafetyLevel":
        try:
            return cls((value or "passive").strip().lower())
        except ValueError:
            return cls.PASSIVE


class NotAcceptedError(RuntimeError):
    """Raised when a gated action is attempted before acceptance."""


def terms_accepted() -> bool:
    return config_mod.load().get("terms_accepted_version") == TERMS_VERSION


def accept_terms() -> None:
    config_mod.update(terms_accepted_version=TERMS_VERSION)


def require_terms() -> None:
    if not terms_accepted():
        raise NotAcceptedError("The Responsible Use Notice must be accepted first.")


def active_tools_acknowledged() -> bool:
    return bool(config_mod.load().get("safety", {}).get("active_tools_acknowledged"))


def acknowledge_active_tools() -> None:
    config_mod.update(safety={"active_tools_acknowledged": True})


def require_active_authorization() -> None:
    """Gate for active/intrusive tools."""
    require_terms()
    if not active_tools_acknowledged():
        raise NotAcceptedError(
            "Active tools require acknowledging that you own or are authorized "
            "to test the target."
        )


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------

@dataclass
class _Bucket:
    tokens: float
    updated: float = field(default_factory=time.monotonic)


class RateLimiter:
    """A simple per-key token bucket, thread-safe."""

    def __init__(self, per_minute: int = 30, burst: int | None = None):
        self.per_minute = max(1, per_minute)
        self.burst = burst if burst is not None else self.per_minute
        self._rate = self.per_minute / 60.0
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str, block: bool = True) -> bool:
        while True:
            with self._lock:
                now = time.monotonic()
                bucket = self._buckets.get(key)
                if bucket is None:
                    bucket = _Bucket(tokens=float(self.burst))
                    self._buckets[key] = bucket
                elapsed = now - bucket.updated
                bucket.tokens = min(self.burst, bucket.tokens + elapsed * self._rate)
                bucket.updated = now
                if bucket.tokens >= 1.0:
                    bucket.tokens -= 1.0
                    return True
                wait = (1.0 - bucket.tokens) / self._rate
            if not block:
                return False
            time.sleep(min(wait, 5.0))


def default_limiter() -> RateLimiter:
    cfg = config_mod.load().get("safety", {})
    return RateLimiter(per_minute=int(cfg.get("max_requests_per_minute", 30)))


def polite_delay() -> None:
    delay = float(config_mod.load().get("safety", {}).get("request_delay_seconds", 1.0))
    if delay > 0:
        time.sleep(delay)
