"""Dashboard page: overview and quick access."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import __version__
from ... import config as config_mod
from ...core import registry, safety, workspace as ws_mod
from .. import theme


class _StatCard(QFrame):
    def __init__(self, title: str, value: str, note: str = ""):
        super().__init__()
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        label_title = QLabel(title)
        label_title.setObjectName("muted")
        label_value = QLabel(value)
        label_value.setObjectName("section")
        layout.addWidget(label_title)
        layout.addWidget(label_value)
        label_note = QLabel(note)
        label_note.setObjectName("muted")
        label_note.setWordWrap(True)
        layout.addWidget(label_note)


class DashboardPage(QWidget):
    def __init__(self, on_navigate, parent=None):
        super().__init__(parent)
        self.on_navigate = on_navigate
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("OSINT Toolkit")
        title.setObjectName("title")
        subtitle = QLabel(f"A local, open-source, educational OSINT toolkit · v{__version__}")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(14)

        cards_widget = QWidget()
        cards = QHBoxLayout(cards_widget)
        layout.addWidget(cards_widget)

        self.stat_cards: list[_StatCard] = []
        for label, key in [("Tools in catalog", "tools"), ("Workspaces", "workspaces"),
                           ("AI provider", "ai"), ("Status", "status")]:
            card = _StatCard(label, "…")
            self.stat_cards.append(card)
            cards.addWidget(card)

        layout.addSpacing(14)
        quick = QLabel("Quick actions")
        quick.setObjectName("section")
        layout.addWidget(quick)

        grid = QGridLayout()
        actions = [
            ("Browse tools", "tools", "Explore every tool with plain-English instructions"),
            ("Run a tool", "run", "Pick a tool, enter a target, run it"),
            ("AI assistant", "assistant", "Let a local or cloud AI use the toolkit for you"),
            ("Settings", "settings", "AI providers, web view, terms"),
        ]
        for row, (name, page, desc) in enumerate(actions):
            frame = QFrame()
            frame.setObjectName("panel")
            frame_layout = QVBoxLayout(frame)
            button = QPushButton(name)
            button.setObjectName("primary")
            button.clicked.connect(lambda _=False, p=page: self.on_navigate(p))
            label_desc = QLabel(desc)
            label_desc.setObjectName("muted")
            label_desc.setWordWrap(True)
            frame_layout.addWidget(button)
            frame_layout.addWidget(label_desc)
            grid.addWidget(frame, row // 2, row % 2)
        layout.addLayout(grid)
        layout.addStretch(1)

    def refresh(self) -> None:
        catalog = registry.load_catalog()
        enabled = sum(1 for t in catalog if registry.is_enabled(t.id))
        passive = sum(1 for t in catalog if not t.is_active_tool)
        active = len(catalog) - passive
        workspaces = len(ws_mod.list_workspaces())
        ai = config_mod.load().get("ai", {}).get("active_provider", "none")

        self.stat_cards[0].findChildren(QLabel)[1].setText(f"{len(catalog)} ({enabled} enabled)")
        self.stat_cards[0].findChildren(QLabel)[2].setText(f"{passive} passive · {active} active")
        self.stat_cards[1].findChildren(QLabel)[1].setText(str(workspaces))
        self.stat_cards[1].findChildren(QLabel)[2].setText("stored under your user profile")
        self.stat_cards[2].findChildren(QLabel)[1].setText(ai if ai != "none" else "not connected")
        self.stat_cards[2].findChildren(QLabel)[2].setText("local AI sends nothing off-machine")
        terms = "Notice accepted" if safety.terms_accepted() else "Notice NOT accepted"
        self.stat_cards[3].findChildren(QLabel)[1].setText(terms)
        self.stat_cards[3].findChildren(QLabel)[2].setText("see Settings to accept")