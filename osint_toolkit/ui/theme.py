"""OSINT-themed dark palette and Qt stylesheet."""

from __future__ import annotations

BG = "#0b0f14"
PANEL = "#11161d"
PANEL_2 = "#161d26"
BORDER = "#1f2a36"
TEXT = "#c8d3e0"
MUTED = "#6b7a8d"
ACCENT = "#00e5a0"
ACCENT_DIM = "#0f8f66"
ACCENT2 = "#00b3d9"
WARN = "#ffb454"
DANGER = "#ff5c5c"

# Font with fallbacks: Consolas on Windows (installed by default), then
# Segoe UI (Windows system font), then any monospace, then sans-serif.
FONT = "Consolas, Segoe UI, \"JetBrains Mono\", \"Fira Code\", monospace, sans-serif"

QSS = f"""
* {{
    font-family: {FONT};
    font-size: 13px;
    color: {TEXT};
    /* When Consolas is missing, Qt's font fallback kicks in via the comma-separated list above. */
}}
QWidget {{ background-color: {BG}; }}
QMainWindow, QDialog {{ background-color: {BG}; }}

QFrame#panel, QWidget#panel {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel#title {{
    font-size: 20px;
    font-weight: bold;
    color: {ACCENT};
}}
QLabel#subtitle {{ color: {MUTED}; }}
QLabel#section {{ font-weight: bold; font-size: 15px; color: {ACCENT}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#danger {{ color: {DANGER}; font-weight: bold; }}
QLabel#warn {{ color: {WARN}; }}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 10px 12px;
    min-height: 34px;
    font-size: 14px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit::placeholder {{ color: {MUTED}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 24px;
    background: {PANEL_2};
    border: 1px solid {BORDER};
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {ACCENT_DIM}; }}

QPushButton {{
    background-color: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 14px;
    font-weight: bold;
}}
QPushButton:hover {{ border-color: {ACCENT2}; color: {ACCENT2}; }}
QPushButton#primary {{
    background-color: {ACCENT};
    color: {BG};
    border: none;
}}
QPushButton#primary:hover {{ background-color: #33f0b5; }}
QPushButton#danger {{
    background-color: transparent;
    color: {DANGER};
    border: 1px solid {DANGER};
}}
QPushButton#nav {{
    text-align: left;
    padding: 10px 16px;
    border: none;
    border-left: 3px solid transparent;
    background: transparent;
    color: {TEXT};
}}
QPushButton#nav:checked {{
    border-left: 3px solid {ACCENT};
    color: {ACCENT};
    background-color: {PANEL};
}}

QListWidget, QTableWidget, QTreeWidget {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    outline: none;
}}
QListWidget::item {{ padding: 6px; }}
QListWidget::item:selected {{ background-color: {PANEL_2}; color: {ACCENT}; }}
QHeaderView::section {{
    background-color: {PANEL_2};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    font-weight: bold;
}}

QCheckBox::indicator {{ width: 16px; height: 16px; }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QTabBar::tab {{
    background: {PANEL};
    padding: 8px 14px;
    border: 1px solid {BORDER};
    border-bottom: none;
}}
QTabBar::tab:selected {{ background: {BG}; color: {ACCENT}; }}
"""


def apply(app) -> None:
    app.setStyleSheet(QSS)