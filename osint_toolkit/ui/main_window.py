"""Main window and app entry."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, config
from ..core import logging_setup, safety
from . import theme, workers
from .pages import (
    DashboardPage,
    ToolsPage,
    RunPage,
    ResultsPage,
    AssistantPage,
    SettingsPage,
)


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle(f"OSINT Toolkit v{__version__}")
        self.setMinimumSize(1280, 820)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setObjectName("panel")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 14, 24, 14)
        title = QLabel("OSINT Toolkit")
        title.setObjectName("title")
        subtitle = QLabel("Local, open-source, educational OSINT · lawful use only")
        subtitle.setObjectName("subtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        nav = QWidget()
        nav.setObjectName("panel")
        nav_layout = QVBoxLayout(nav)
        self.nav_list = QListWidget()
        for name, key in [
            ("Dashboard", "dashboard"),
            ("Tools", "tools"),
            ("Run", "run"),
            ("Results", "results"),
            ("AI Assistant", "assistant"),
            ("Settings", "settings"),
        ]:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, key)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        nav_layout.addWidget(self.nav_list)

        self.stacked = QStackedWidget()
        self.pages: dict[str, QWidget] = {}
        self.pages["dashboard"] = DashboardPage(on_navigate=self._navigate)
        self.pages["tools"] = ToolsPage()
        self.pages["run"] = RunPage()
        self.pages["results"] = ResultsPage()
        self.pages["assistant"] = AssistantPage()
        self.pages["settings"] = SettingsPage()
        for key, w in self.pages.items():
            self.stacked.addWidget(w)

        splitter.addWidget(nav)
        splitter.addWidget(self.stacked)
        splitter.setSizes([200, 1080])

        self.status = QStatusBar(self)
        self.setStatusBar(self.status)

        self.nav_list.currentItemChanged.connect(self._on_nav)
        self._navigate("dashboard")
        self._check_terms()

    def _on_nav(self, item):
        if item is None:
            return
        key = item.data(Qt.UserRole)
        self._navigate(key)

    def _navigate(self, key: str) -> None:
        self.stacked.setCurrentIndex(list(self.pages.keys()).index(key))
        if key == "dashboard":
            self.pages[key].refresh()
        if key == "results":
            self.pages[key]._refresh()
        if key == "tools":
            self.pages[key]._populate()
        self.status.showMessage(f"Viewing: {key}")

    def _check_terms(self) -> None:
        if not safety.terms_accepted():
            self.status.showMessage("⚠️ Responsible-use notice not accepted — go to Settings")
        else:
            self.status.showMessage("Ready")


def main() -> None:
    log = logging_setup.setup()
    log.info("Launching OSINT Toolkit GUI")
    app = QApplication(sys.argv)
    theme.apply(app)
    win = MainWindow(app)
    win.show()
    sys.exit(app.exec())