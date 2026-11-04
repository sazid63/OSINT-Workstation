"""AI Assistant page."""

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
from ...ai.providers import get_provider, list_providers
from ..workers import AgentWorker


class AssistantPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        header = QLabel("AI Assistant")
        header.setObjectName("section")
        layout.addWidget(header)
        self.note = QLabel("Only registered tools are available to the assistant. Local AI sends nothing off-machine.")
        self.note.setObjectName("muted")
        layout.addWidget(self.note)

        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(12, 10, 12, 10)
        row = QHBoxLayout()
        self.provider = QComboBox()
        for p in list_providers():
            self.provider.addItem(p)
        row.addWidget(self.provider)
        self.start = QPushButton("Start")
        self.start.setObjectName("primary")
        row.addWidget(self.start)
        pl.addLayout(row)
        layout.addWidget(panel)

        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText("What do you want to investigate? Example: 'Find public infrastructure for example.com'")
        self.prompt.setMinimumHeight(100)
        layout.addWidget(self.prompt)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Answer and tool steps will appear here.")
        layout.addWidget(self.output)

        self.status = QLabel("")
        self.status.setObjectName("muted")
        layout.addWidget(self.status)

        self.start.clicked.connect(self._start)
        self._worker = None
        cfg = config_mod.load()
        pid = cfg.get("ai", {}).get("active_provider", "ollama")
        idx = self.provider.findText(pid)
        if idx >= 0:
            self.provider.setCurrentIndex(idx)

    def _start(self) -> None:
        pid = self.provider.currentText()
        cfg = config_mod.load()
        pconfig = (cfg.get("ai", {}).get("providers", {}).get(pid, {}))
        provider = get_provider(pid, pconfig)
        if provider is None:
            self.output.setPlainText(f"Unknown provider '{pid}'.")
            return
        check = provider.warmup()
        if check != "ready":
            self.status.setText(f"Provider status: {check}")
        else:
            self.status.setText("Provider: ready")
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            return
        from ...core import workspace as ws_mod
        ws = ws_mod.list_workspaces()
        ws_obj = ws[0] if ws else ws_mod.create("AI")
        self.start.setEnabled(False)
        self.start.setText("Running…")
        self.output.setPlainText("Working — planning and calling tools.")
        self._worker = AgentWorker(prompt, provider, workspace=ws_obj)
        self._worker.approval_needed.connect(self._approve)
        self._worker.finished.connect(self._done)
        self._worker.failed.connect(self._fail)
        self._worker.start()

    def _approve(self, payload):
        tool_dict, args = payload
        from PySide6.QtWidgets import QMessageBox
        text = (
            f"An ACTIVE tool was proposed:\n\n{tool_dict.get('name')} [{tool_dict.get('id')}] "
            f"(safety: {tool_dict.get('safety')})\n\nArguments: {json.dumps(args)}\n\n"
            f"Run only on targets you own or are authorized to test.\nApprove this single run?"
        )
        res = QMessageBox.question(self, "Approve active tool", text)
        ok = (res == QMessageBox.Yes)
        if self._worker is not None:
            self._worker.set_approval(ok)

    def _done(self, output):
        self.start.setEnabled(True)
        self.start.setText("Start")
        parts = [output.text]
        if output.warnings:
            parts.append("\n--- WARNINGS ---\n" + "\n".join(output.warnings))
        self.output.setPlainText("\n".join(p for p in parts if p))

    def _fail(self, err):
        self.start.setEnabled(True)
        self.start.setText("Start")
        self.output.setPlainText(f"Error: {err}")