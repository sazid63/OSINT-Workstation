"""Settings page: AI providers, secrets, safety, web view."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ... import config as config_mod
from ...core import safety, secrets as secrets_mod


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        header = QLabel("Settings")
        header.setObjectName("section")
        layout.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self._tab_ai(), "AI")
        tabs.addTab(self._tab_secrets(), "Secrets")
        tabs.addTab(self._tab_safety(), "Safety")
        tabs.addTab(self._tab_web(), "Web View")
        layout.addWidget(tabs)

        self._reload()

    def _tab_ai(self):
        tab = QWidget()
        v = QVBoxLayout(tab)
        self.terms = QLabel("")
        self.terms.setWordWrap(True)
        self.terms_accept = QPushButton("Accept responsible-use notice")
        v.addWidget(self.terms)
        v.addWidget(self.terms_accept)

        v.addSpacing(8)
        cfg = config_mod.load()
        ai = cfg.get("ai", {}).get("providers", {})

        g = QGroupBox("Ollama")
        gv = QVBoxLayout(g)
        self.ollama_base = QLineEdit(ai.get("ollama", {}).get("base_url", "http://localhost:11434"))
        self.ollama_model = QLineEdit(ai.get("ollama", {}).get("model", ""))
        gv.addWidget(QLabel("Base URL"))
        gv.addWidget(self.ollama_base)
        gv.addWidget(QLabel("Model (e.g. gemma3, llama3.1)"))
        gv.addWidget(self.ollama_model)
        v.addWidget(g)

        g2 = QGroupBox("LM Studio / OpenAI-compatible")
        gv2 = QVBoxLayout(g2)
        self.lm_base = QLineEdit(ai.get("lmstudio", {}).get("base_url", "http://localhost:1234/v1"))
        self.lm_model = QLineEdit(ai.get("lmstudio", {}).get("model", ""))
        gv2.addWidget(QLabel("Base URL"))
        gv2.addWidget(self.lm_base)
        gv2.addWidget(QLabel("Model"))
        gv2.addWidget(self.lm_model)
        v.addWidget(g2)

        g3 = QGroupBox("OpenAI-compatible (custom)")
        gv3 = QVBoxLayout(g3)
        self.oc_base = QLineEdit(ai.get("openai_compatible", {}).get("base_url", ""))
        self.oc_model = QLineEdit(ai.get("openai_compatible", {}).get("model", ""))
        gv3.addWidget(QLabel("Base URL"))
        gv3.addWidget(self.oc_base)
        gv3.addWidget(QLabel("Model"))
        gv3.addWidget(self.oc_model)
        v.addWidget(g3)

        g4 = QGroupBox("Anthropic")
        gv4 = QVBoxLayout(g4)
        self.anth_model = QLineEdit(ai.get("anthropic", {}).get("model", "claude-3-5-sonnet"))
        gv4.addWidget(QLabel("Model"))
        gv4.addWidget(self.anth_model)
        v.addWidget(g4)

        g5 = QGroupBox("Gemini")
        gv5 = QVBoxLayout(g5)
        self.gem_model = QLineEdit(ai.get("gemini", {}).get("model", "gemini-1.5-flash"))
        gv5.addWidget(QLabel("Model"))
        gv5.addWidget(self.gem_model)
        v.addWidget(g5)

        g6 = QGroupBox("OpenCode (local CLI)")
        gv6 = QVBoxLayout(g6)
        self.opc_base = QLineEdit(ai.get("opencode", {}).get("base_url", "http://localhost:4096"))
        self.opc_binary = QLineEdit(ai.get("opencode", {}).get("binary", "opencode"))
        gv6.addWidget(QLabel("Base URL (optional)"))
        gv6.addWidget(self.opc_base)
        gv6.addWidget(QLabel("CLI Binary (opencode or full path to .cmd/.bat)"))
        gv6.addWidget(self.opc_binary)
        v.addWidget(g6)

        save = QPushButton("Save AI settings")
        v.addWidget(save)
        v.addStretch(1)

        self.terms_accept.clicked.connect(self._accept_terms)
        save.clicked.connect(self._save_ai)
        return tab

    def _tab_secrets(self):
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.addWidget(QLabel("Keys are stored in your OS keychain if available; otherwise set them here.\nThey are never logged or sent to the app's developer."))
        keys = [
            ("OPENAI_API_KEY", ""),
            ("ANTHROPIC_API_KEY", ""),
            ("GEMINI_API_KEY", ""),
            ("OPENAI_COMPATIBLE_API_KEY", ""),
        ]
        self.secret_edits = {}
        for k, _ in keys:
            box = QHBoxLayout()
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.Password)
            edit.setPlaceholderText("Enter or replace " + k)
            show = QPushButton("Show")
            set_b = QPushButton("Save to keychain")
            clear = QPushButton("Clear")
            def _toggle(text=show, e=edit): text.setText("Hide" if e.echoMode()==QLineEdit.Password else "Show"); e.setEchoMode(QLineEdit.Normal if e.echoMode()==QLineEdit.Password else QLineEdit.Password)
            def _set(k2=k, e=edit): secrets_mod.set_secret(k2, e.text()); e.clear()
            def _del(k2=k): secrets_mod.delete_secret(k2)
            show.clicked.connect(_toggle)
            set_b.clicked.connect(_set)
            clear.clicked.connect(_del)
            box.addWidget(edit)
            box.addWidget(show)
            box.addWidget(set_b)
            box.addWidget(clear)
            v.addWidget(QLabel(k))
            v.addLayout(box)
            self.secret_edits[k] = edit
        v.addStretch(1)
        return tab

    def _tab_safety(self):
        tab = QWidget()
        v = QVBoxLayout(tab)
        self.active_ack = QCheckBox("I acknowledge active tools will only be run on systems I own or are explicitly authorized to test")
        self.active_ack.setChecked(safety.active_tools_acknowledged())
        v.addWidget(self.active_ack)
        save = QPushButton("Save safety settings")
        save.clicked.connect(self._save_safety)
        v.addWidget(save)
        v.addStretch(1)
        return tab

    def _tab_web(self):
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.addWidget(QLabel("Start the optional loopback web view (http://127.0.0.1) if you prefer a browser."))
        self.web_enabled = QCheckBox("Enable local web view")
        v.addWidget(self.web_enabled)
        row = QHBoxLayout()
        row.addWidget(QLabel("Port"))
        self.web_port = QSpinBox()
        self.web_port.setRange(1024, 65535)
        row.addWidget(self.web_port)
        v.addLayout(row)
        save = QPushButton("Save web settings")
        save.clicked.connect(self._save_web)
        v.addWidget(save)
        v.addStretch(1)
        return tab

    def _reload(self):
        cfg = config_mod.load()
        self.terms.setText("Responsible-use notice: ACCEPTED" if safety.terms_accepted() else "Responsible-use notice: NOT ACCEPTED (must accept before running tools)")
        self.terms_accept.setEnabled(not safety.terms_accepted())
        web = cfg.get("web", {})
        self.web_enabled.setChecked(web.get("enabled", False))
        self.web_port.setValue(web.get("port", 8765))

    def _accept_terms(self):
        safety.accept_terms()
        self._reload()

    def _save_ai(self):
        cfg = config_mod.load()
        ai = cfg.get("ai", {})
        providers = ai.get("providers", {})
        providers["ollama"] = {"base_url": self.ollama_base.text(), "model": self.ollama_model.text()}
        providers["lmstudio"] = {"base_url": self.lm_base.text(), "model": self.lm_model.text()}
        providers["openai_compatible"] = {"base_url": self.oc_base.text(), "model": self.oc_model.text()}
        providers["anthropic"] = {"base_url": "https://api.anthropic.com", "model": self.anth_model.text()}
        providers["gemini"] = {"base_url": "https://generativelanguage.googleapis.com", "model": self.gem_model.text()}
        providers["opencode"] = {"base_url": self.opc_base.text(), "model": "", "binary": self.opc_binary.text()}
        config_mod.update(ai={"providers": providers})

    def _save_safety(self):
        if self.active_ack.isChecked():
            safety.acknowledge_active_tools()
        else:
            from ... import config as config_mod
            config_mod.update(safety={"active_tools_acknowledged": False})

    def _save_web(self):
        config_mod.update(web={"enabled": self.web_enabled.isChecked(), "port": self.web_port.value()})