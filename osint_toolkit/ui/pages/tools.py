"""Tools list page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core import registry
from .. import theme


class ToolsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        left = QWidget()
        left.setObjectName("panel")
        v = QVBoxLayout(left)
        v.setContentsMargins(8, 8, 8, 8)
        search_box = QHBoxLayout()
        self.search = QComboBox()
        self.search.setEditable(True)
        self.search.lineEdit().setPlaceholderText("Search by name, category or tag")
        self.category = QComboBox()
        self.category.addItem("All categories")
        self.safety = QComboBox()
        self.safety.addItem("All safety levels")
        self.safety.addItem("passive")
        self.safety.addItem("active")
        search_box.addWidget(self.search)
        search_box.addWidget(self.category)
        search_box.addWidget(self.safety)
        v.addLayout(search_box)

        self.list = QListWidget()
        v.addWidget(self.list)

        right = QWidget()
        right.setObjectName("panel")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 10, 12, 10)
        self.title = QLabel("Select a tool")
        self.title.setObjectName("section")
        rv.addWidget(self.title)
        self.description = QLabel("Choose a tool from the list to see instructions.")
        self.description.setWordWrap(True)
        self.description.setObjectName("muted")
        rv.addWidget(self.description)

        self.tags = QLabel("")
        self.tags.setObjectName("muted")
        rv.addWidget(self.tags)

        self.how = QTextEdit()
        self.how.setReadOnly(True)
        self.how.setPlaceholderText("How to use (plain English)")
        self.how.setMinimumHeight(160)
        rv.addWidget(self.how)

        self.important = QTextEdit()
        self.important.setReadOnly(True)
        self.important.setMinimumHeight(70)
        rv.addWidget(self.important)

        self.connects = QTextEdit()
        self.connects.setReadOnly(True)
        self.connects.setMinimumHeight(90)
        rv.addWidget(self.connects)

        self.enabled = QCheckBox("Enabled")
        rv.addWidget(self.enabled)

        bottom = QHBoxLayout()
        self.info = QLabel("License: —")
        self.info.setObjectName("muted")
        bottom.addWidget(self.info)
        rv.addLayout(bottom)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([260, 640])
        layout.addWidget(splitter)

        self.search.lineEdit().textChanged.connect(self._filter)
        self.category.currentTextChanged.connect(self._filter)
        self.safety.currentTextChanged.connect(self._filter)
        self.list.currentItemChanged.connect(self._on_select)
        self.enabled.toggled.connect(self._on_toggle)

        self._tools = registry.load_catalog()
        self._populate()

    def _populate(self) -> None:
        self.category.clear()
        self.category.addItem("All categories")
        for c in registry.categories():
            self.category.addItem(c)
        self.list.clear()
        for tool in self._tools:
            item = QListWidgetItem(f"[{tool.safety}] {tool.name}")
            item.setData(Qt.UserRole, tool.id)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _filter(self) -> None:
        text = self.search.currentText().lower()
        cat = self.category.currentText()
        saf = self.safety.currentText()
        for i in range(self.list.count()):
            item = self.list.item(i)
            tool_id = item.data(Qt.UserRole)
            tool = next((t for t in self._tools if t.id == tool_id), None)
            if not tool:
                item.setHidden(True)
                continue
            matches = text in tool.name.lower() or text in tool.category.lower() or text in " ".join(tool.tags).lower()
            matches &= (cat == "All categories" or tool.category == cat)
            matches &= (saf == "All safety levels" or tool.safety == saf)
            item.setHidden(not matches)

    def _on_select(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        tool = next((t for t in self._tools if t.id == item.data(Qt.UserRole)), None)
        if not tool:
            return
        self.title.setText(tool.name)
        self.description.setText(f"{tool.category} · {tool.description}")
        self.tags.setText("Tags: " + (", ".join(tool.tags) or "—"))
        self.how.setPlainText(tool.how_to_use or "No instructions provided.")
        self.important.setPlainText(tool.important or "")
        self.important.setVisible(bool(tool.important))
        conn = tool.what_to_connect or []
        self.connects.setPlainText("\n".join(f"• {c}" for c in conn) or "Nothing to connect.")
        self.info.setText(f"License: {tool.license} · Mode: {tool.run_mode} · Source: {tool.source}")
        self.enabled.blockSignals(True)
        self.enabled.setChecked(registry.is_enabled(tool.id))
        self.enabled.blockSignals(False)

    def _on_toggle(self, value: bool) -> None:
        item = self.list.currentItem()
        if not item:
            return
        tool_id = item.data(Qt.UserRole)
        registry.set_enabled(tool_id, value)