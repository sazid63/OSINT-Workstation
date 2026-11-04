"""Background workers so long tool runs / AI turns don't freeze the UI."""

from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from ..core import runner as runner_mod
from ..core import workspace as ws_mod
from ..ai.agent import run_agent


class ToolWorker(QThread):
    """Run one tool in the background."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, tool, inputs, workspace=None, parent=None):
        super().__init__(parent)
        self._tool = tool
        self._inputs = inputs
        self._workspace = workspace

    def run(self) -> None:  # noqa: D102
        try:
            result = runner_mod.run_tool(self._tool, self._inputs, workspace=self._workspace)
            self.finished.emit(result)
        except runner_mod.safety.NotAcceptedError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class AgentWorker(QThread):
    """Run the guardrailed AI agent in the background, requesting approval on
    the GUI thread when an active tool is proposed."""

    finished = Signal(object)      # AgentOutput
    approval_needed = Signal(object)  # (tool_dict, arguments)
    failed = Signal(str)

    def __init__(self, prompt, provider, workspace=None, tools=None, parent=None):
        super().__init__(parent)
        self._prompt = prompt
        self._provider = provider
        self._workspace = workspace
        self._tools = tools
        self._approval_event = threading.Event()
        self._approval_result = False

    def set_approval(self, ok: bool) -> None:
        self._approval_result = bool(ok)
        self._approval_event.set()

    def _request_approval(self, tool_dict: dict, args: dict) -> bool:
        self._approval_result = False
        self._approval_event.clear()
        self.approval_needed.emit((tool_dict, args))
        self._approval_event.wait(timeout=600)
        return self._approval_result

    def run(self) -> None:  # noqa: D102
        try:
            output = run_agent(
                self._prompt,
                provider=self._provider,
                tools=self._tools,
                approval=self._request_approval,
                workspace=self._workspace,
            )
            self.finished.emit(output)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))