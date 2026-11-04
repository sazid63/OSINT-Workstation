"""UI pages."""

from __future__ import annotations

from .dashboard import DashboardPage
from .tools import ToolsPage
from .run import RunPage
from .results import ResultsPage
from .assistant import AssistantPage
from .settings import SettingsPage

__all__ = [
    "DashboardPage",
    "ToolsPage",
    "RunPage",
    "ResultsPage",
    "AssistantPage",
    "SettingsPage",
]