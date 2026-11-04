"""Provider-independent AI types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str = ""
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class AIToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    text: str = ""
    tool_calls: list[AIToolCall] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class AIProvider:
    """Interface every provider implements."""

    id = "base"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def warmup(self) -> str:
        """Return provider readiness or an error string."""
        raise NotImplementedError

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AIResponse:
        raise NotImplementedError