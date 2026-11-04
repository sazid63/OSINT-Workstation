"""Run a tool manually page."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ... import config as config_mod
from ...core import registry, safety, workspace as ws_mod
from .. import theme
from ..workers import ToolWorker


class RunPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        header = QLabel("Run a tool")
        header.setObjectName("section")
        layout.addWidget(header)

        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14, 12, 14, 12)

        row = QHBoxLayout()
        self.tool = QComboBox()
        row.addWidget(self.tool)
        self.run_btn = QPushButton("Run")
        self.run_btn.setObjectName("primary")
        row.addWidget(self.run_btn)
        pl.addLayout(row)

        self.note = QLabel("")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        pl.addWidget(self.note)

        self.inputs: list[tuple[str, QLineEdit]] = []
        self.inputs_panel = QVBoxLayout()
        pl.addLayout(self.inputs_panel)

        layout.addWidget(panel)

        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setPlaceholderText("Output will appear here.")
        layout.addWidget(self.out)

        self.run_btn.clicked.connect(self._run)
        self.tool.currentTextChanged.connect(self._on_tool_change)

        self._worker = None
        self._refresh_tools()
        self._on_tool_change()

    def _refresh_tools(self) -> None:
        self.tool.clear()
        self._cache = {t.id: t for t in registry.enabled_tools()}
        for tool in sorted(self._cache.values(), key=lambda t: (t.category, t.name)):
            self.tool.addItem(f"[{tool.safety}] {tool.name} — {tool.id}", tool.id)

    def _on_tool_change(self) -> None:
        # Clear inputs
        for _, w in self.inputs:
            w.setParent(None)
        self.inputs.clear()
        tid = self.tool.currentData()
        if tid is None:
            self.note.setText("")
            return
        tool = self._cache.get(tid)
        if not tool:
            return
        for inp in tool.inputs:
            w = QLineEdit()
            w.setPlaceholderText(inp.placeholder or inp.name)
            self.inputs_panel.addWidget(w)
            self.inputs.append((inp.name, w))
        note = ""
        if tool.important:
            note = tool.important
        elif tool.is_active_tool:
            note = "IMPORTANT: This is an ACTIVE tool. Run only on systems you own or are explicitly authorized to test."
        self.note.setText(note)

    def _run(self) -> None:
        tid = self.tool.currentData()
        if tid is None:
            return
        tool = self._cache.get(tid)
        if not tool:
            return
        if tool.is_active_tool and not safety.active_tools_acknowledged():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Active tool authorization",
                "Active tools require acknowledging you own or are authorized to test the target.\n\n"
                "Go to Settings → Safety to acknowledge.",
            )
            return
        try:
            if not safety.terms_accepted():
                safety.accept_terms()
        except Exception:
            pass
        args: dict[str, str] = {}
        for name, w in self.inputs:
            if w.text().strip():
                args[name] = w.text().strip()
        ws = ws_mod.list_workspaces()
        ws_obj = ws[0] if ws else ws_mod.create("Manual")
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running…")
        self._worker = ToolWorker(tool, args, workspace=ws_obj)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, result):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run")
        self.out.setPlainText(json.dumps(result.to_dict(), indent=2, default=str))

    def _on_fail(self, err: str):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run")
        self.out.setPlainText(f"Error: {err}")