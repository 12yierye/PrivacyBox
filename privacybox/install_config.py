from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

INSTALL_FILENAME = "install.json"


def _get_install_config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "privacybox"


def _install_config_path() -> Path:
    return _get_install_config_dir() / INSTALL_FILENAME


def read_install_config() -> dict[str, Any]:
    path = _install_config_path()
    if not path.exists():
        return {}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {}


def write_install_config(config: dict[str, Any]) -> None:
    path = _install_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_data_dir() -> str | None:
    return read_install_config().get("data_dir") or os.environ.get("PRIVACYBOX_HOME")


def get_install_path() -> str | None:
    return read_install_config().get("install_path")
