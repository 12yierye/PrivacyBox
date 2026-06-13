from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Generator, Optional

import docker
from docker.errors import DockerException

from privacybox.config.schema import PrivacyBoxConfig
from privacybox.config.loader import get_data_dir
from privacybox.runtime.base import RuntimeBackend
from privacybox.utils.types import (
    HealthStatus,
    RuntimeBackendType,
    ServiceInfo,
)


class DockerBackend(RuntimeBackend):
    """Docker runtime backend via docker-py."""

    def __init__(self, config: PrivacyBoxConfig):
        self.config = config
        self._client: Optional[docker.DockerClient] = None

    @property
    def backend_type(self) -> RuntimeBackendType:
        return RuntimeBackendType.DOCKER

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                socket = self.config.runtime.docker.socket
                if socket:
                    self._client = docker.DockerClient(base_url=socket)
                else:
                    self._client = docker.from_env()
                self._client.ping()
            except DockerException as e:
                raise RuntimeError(f"Docker 不可用: {e}") from e
        return self._client

    def is_available(self) -> bool:
        try:
            self._get_client().ping()
            return True
        except Exception:
            return False

    def deploy(
        self,
        compose_yaml: str,
        env: dict[str, str],
        project_name: str,
    ) -> str:
        client = self._get_client()

        with tempfile.TemporaryDirectory(prefix="privacybox_") as tmpdir:
            compose_path = Path(tmpdir) / "docker-compose.yml"
            compose_path.write_text(compose_yaml, encoding="utf-8")

            env_path = Path(tmpdir) / ".env"
            if env:
                env_content = "\n".join(f"{k}={v}" for k, v in env.items())
                env_path.write_text(env_content, encoding="utf-8")

            compose_cmd = ["docker", "compose", "-p", project_name, "up", "-d"]
            result = subprocess.run(
                compose_cmd,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"部署失败: {result.stderr.strip() or result.stdout.strip()}"
                )

            return project_name

    def list_services(self, label_filter: str = "privacybox.managed=true") -> list[ServiceInfo]:
        client = self._get_client()
        containers = client.containers.list(
            all=True,
            filters={"label": label_filter} if label_filter else None,
        )
        result = []
        for c in containers:
            labels = c.labels or {}
            result.append(ServiceInfo(
                name=labels.get("privacybox.name", c.name),
                status=c.status,
                runtime_backend=RuntimeBackendType.DOCKER,
            ))
        return result

    def get_logs(
        self,
        service_name: str,
        tail: int = 100,
        follow: bool = False,
    ) -> Generator[str, None, None]:
        client = self._get_client()
        try:
            container = client.containers.get(service_name)
        except docker.errors.NotFound:
            try:
                containers = client.containers.list(
                    all=True,
                    filters={"name": service_name},
                )
                if containers:
                    container = containers[0]
                else:
                    raise RuntimeError(f"容器 '{service_name}' 未找到")
            except Exception:
                raise RuntimeError(f"容器 '{service_name}' 未找到")

        logs = container.logs(tail=tail, stream=follow, follow=follow)
        if follow:
            for line in logs:
                yield line.decode("utf-8", errors="replace")
        else:
            yield logs.decode("utf-8", errors="replace")
            return

    def destroy(
        self,
        project_name: str,
        keep_volumes: bool = False,
    ) -> bool:
        client = self._get_client()
        vol_flag = "" if keep_volumes else "-v"
        cmd = ["docker", "compose", "-p", project_name, "down", vol_flag]
        cmd = [c for c in cmd if c]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0

    def get_service_info(self, service_name: str) -> Optional[ServiceInfo]:
        client = self._get_client()
        try:
            container = client.containers.get(service_name)
            labels = container.labels or {}
            return ServiceInfo(
                name=labels.get("privacybox.name", container.name),
                status=container.status,
                runtime_backend=RuntimeBackendType.DOCKER,
            )
        except docker.errors.NotFound:
            return None

    def health_check(self, service_name: str) -> HealthStatus:
        import time
        import httpx

        info = self.get_service_info(service_name)
        if not info or info.status != "running":
            return HealthStatus(healthy=False, message="服务未运行")

        start = time.time()
        try:
            resp = httpx.get(f"http://localhost/", timeout=5)
            elapsed = (time.time() - start) * 1000
            return HealthStatus(
                healthy=resp.is_success,
                message=f"HTTP {resp.status_code}",
                response_time_ms=round(elapsed, 1),
            )
        except Exception as e:
            return HealthStatus(healthy=False, message=str(e))

    def get_engine_version(self) -> str:
        client = self._get_client()
        info = client.version()
        return info.get("Version", "unknown")
