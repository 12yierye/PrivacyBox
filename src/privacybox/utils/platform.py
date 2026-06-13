from __future__ import annotations

import sys
from enum import Enum


class Platform(str, Enum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


def detect_platform() -> Platform:

    if sys.platform.startswith("linux"):
        return Platform.LINUX
    if sys.platform == "darwin":
        return Platform.MACOS
    if sys.platform == "win32":
        return Platform.WINDOWS
    return Platform.UNKNOWN


def get_docker_socket() -> str:
    plat = detect_platform()
    if plat == Platform.LINUX:
        return "unix:///var/run/docker.sock"
    if plat == Platform.MACOS:
        return "unix:///Users/Administrator/.docker/run/docker.sock"
    if plat == Platform.WINDOWS:
        return "npipe:////./pipe/docker_engine"
    return "unix:///var/run/docker.sock"


def get_podman_socket() -> str:
    return "unix:///run/podman/podman.sock"


def is_wsl() -> bool:
    import platform
    if sys.platform == "win32":
        return False
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


import sys
