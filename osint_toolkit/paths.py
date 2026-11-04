"""Filesystem locations.

Everything the user creates (workspaces, plugins, config, logs) lives under the
operating system's per-user application-data directory — never inside the
repository or the source tree.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIRNAME = "OSINT Toolkit"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def _appdata_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base)
        return Path.home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))


def app_data_dir() -> Path:
    d = _appdata_root() / APP_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def workspaces_dir() -> Path:
    d = app_data_dir() / "workspaces"
    d.mkdir(parents=True, exist_ok=True)
    return d


def plugins_dir() -> Path:
    """Where users drop custom tool plugins."""
    d = app_data_dir() / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tools_bin_dir() -> Path:
    """Where auto-downloaded external binaries are installed."""
    d = app_data_dir() / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def downloads_dir() -> Path:
    d = app_data_dir() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_dir() -> Path:
    d = app_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return app_data_dir() / "config.yaml"


def state_path() -> Path:
    return app_data_dir() / "state.json"


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def catalog_dir() -> Path:
    """Built-in tool manifests shipped inside the package."""
    return package_dir() / "catalog"


def resource_path(*parts: str) -> Path:
    """Resolve a bundled resource whether running from source or frozen."""
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", package_dir()))
    else:
        base = package_dir()
    return base.joinpath(*parts)
