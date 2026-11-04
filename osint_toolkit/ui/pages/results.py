"""Results page."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core import workspace as ws_mod


class ResultsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        header = QLabel("Results")
        header.setObjectName("section")
        layout.addWidget(header)

        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(12, 10, 12, 10)

        self.workspace = QComboBox()
        self.refresh = QPushButton("Refresh")
        pl.addWidget(self.workspace)
        pl.addWidget(self.refresh)
        layout.addWidget(panel)

        self.view = QTextEdit()
        self.view.setReadOnly(True)
        layout.addWidget(self.view)

        self.refresh.clicked.connect(self._refresh)
        self.workspace.currentTextChanged.connect(self._load)
        self._refresh()

    def _refresh(self) -> None:
        self.workspace.clear()
        for ws in ws_mod.list_workspaces():
            self.workspace.addItem(ws.name, ws)
        if self.workspace.count() == 0:
            self.view.setPlainText("No workspaces yet. Run a tool to create results.")
        else:
            self._load()

    def _load(self) -> None:
        ws = self.workspace.currentData()
        if ws is None:
            return
        records = ws_mod.read_results(ws)
        if not records:
            self.view.setPlainText("No results yet in this workspace.")
            return
        self.view.setPlainText(json.dumps(records[-50:], indent=2, default=str))