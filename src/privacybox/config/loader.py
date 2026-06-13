from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from platformdirs import user_config_dir, user_data_dir, user_state_dir

from privacybox.config.schema import PrivacyBoxConfig
from privacybox.utils.platform import detect_platform
from privacybox.utils.platform import get_docker_socket, get_podman_socket


APP_NAME = "privacybox"


def get_config_dir() -> Path:
    return Path(user_config_dir(APP_NAME, ensure_exists=True))


def get_data_dir() -> Path:
    return Path(user_data_dir(APP_NAME, ensure_exists=True))


def get_state_dir() -> Path:
    return Path(user_state_dir(APP_NAME, ensure_exists=True))


def get_default_config_path() -> Path:
    return get_config_dir() / "config.yaml"


def get_db_path() -> Path:
    return get_state_dir() / "privacybox.db"


def get_credentials_dir() -> Path:
    return get_config_dir() / "credentials"


def _build_default_config() -> PrivacyBoxConfig:
    """Build a config with auto-detected platform defaults."""
    cfg = PrivacyBoxConfig()

    cfg.runtime.docker.socket = get_docker_socket()
    cfg.runtime.podman.socket = get_podman_socket()
    cfg.runtime.k8s.kubeconfig = os.path.expanduser("~/.kube/config")

    return cfg


def config_path_from_env() -> Path:
    env_path = os.environ.get("PRIVACYBOX_CONFIG")
    if env_path:
        return Path(env_path)
    return get_default_config_path()


def load_config(path: Optional[Path] = None) -> PrivacyBoxConfig:
    """Load config from file, merging with defaults."""
    defaults = _build_default_config()
    if path is None:
        path = config_path_from_env()

    if not path.exists():
        return defaults

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    merged = defaults.model_dump()
    _deep_merge(merged, data)
    return PrivacyBoxConfig(**merged)


def save_config(
    config: PrivacyBoxConfig,
    path: Optional[Path] = None,
) -> None:
    if path is None:
        path = config_path_from_env()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = yaml.dump(
        config.model_dump(),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    path.write_text(raw, encoding="utf-8")


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
