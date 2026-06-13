from __future__ import annotations

import shutil
import subprocess

from privacybox.config.schema import PrivacyBoxConfig
from privacybox.utils.types import ServiceInfo


class Doctor:
    """Diagnose the environment for PrivacyBox compatibility."""

    def __init__(self, config: PrivacyBoxConfig):
        self.config = config

    def check_all(self) -> list[dict]:
        return [
            self.check_python(),
            self.check_docker(),
            self.check_docker_compose(),
            self.check_podman(),
            self.check_ollama(),
            self.check_git(),
        ]

    def check_python(self) -> dict:
        import sys
        return {
            "name": "Python",
            "status": "ok" if sys.version_info >= (3, 11) else "warn",
            "detail": f"Python {sys.version}",
        }

    def check_docker(self) -> dict:
        if not shutil.which("docker"):
            return {"name": "Docker", "status": "error", "detail": "未安装"}
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return {
                    "name": "Docker",
                    "status": "ok",
                    "detail": f"Docker {result.stdout.strip()}",
                }
            return {
                "name": "Docker",
                "status": "error",
                "detail": result.stderr.strip() or "Docker 守护进程未运行",
            }
        except Exception as e:
            return {"name": "Docker", "status": "error", "detail": str(e)}

    def check_docker_compose(self) -> dict:
        if not shutil.which("docker"):
            return {"name": "Docker Compose", "status": "warn", "detail": "Docker 未安装"}
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return {
                    "name": "Docker Compose",
                    "status": "ok",
                    "detail": result.stdout.strip(),
                }
            return {"name": "Docker Compose", "status": "error", "detail": "docker compose 插件未安装"}
        except Exception as e:
            return {"name": "Docker Compose", "status": "error", "detail": str(e)}

    def check_podman(self) -> dict:
        if not shutil.which("podman"):
            return {"name": "Podman", "status": "info", "detail": "未安装（可选）"}
        try:
            result = subprocess.run(
                ["podman", "version", "--format", "{{.Version}}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return {
                    "name": "Podman",
                    "status": "ok",
                    "detail": f"Podman {result.stdout.strip()}",
                }
            return {"name": "Podman", "status": "warn", "detail": "Podman 不可用"}
        except Exception:
            return {"name": "Podman", "status": "warn", "detail": "检测失败"}

    def check_ollama(self) -> dict:
        if not shutil.which("ollama"):
            return {"name": "Ollama", "status": "info", "detail": "未安装（可选）"}
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if resp.is_success:
                models = resp.json().get("models", [])
                model_list = ", ".join(m.get("name", "?") for m in models[:3]) if models else "无模型"
                return {
                    "name": "Ollama",
                    "status": "ok",
                    "detail": f"运行中 ({model_list})",
                }
            return {"name": "Ollama", "status": "warn", "detail": "服务未响应"}
        except Exception:
            return {"name": "Ollama", "status": "warn", "detail": "服务未运行"}

    def check_git(self) -> dict:
        if not shutil.which("git"):
            return {"name": "Git", "status": "info", "detail": "未安装（可选）"}
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return {
                "name": "Git",
                "status": "ok",
                "detail": result.stdout.strip(),
            }
        except Exception:
            return {"name": "Git", "status": "warn", "detail": "检测失败"}
