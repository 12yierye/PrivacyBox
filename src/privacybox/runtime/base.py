from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generator, Optional

from privacybox.utils.types import (
    HealthStatus,
    RuntimeBackendType,
    ServiceInfo,
)


class RuntimeBackend(ABC):
    """Container runtime abstraction — each backend implements this."""

    @property
    @abstractmethod
    def backend_type(self) -> RuntimeBackendType:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this runtime is available on the system."""
        ...

    @abstractmethod
    def deploy(
        self,
        compose_yaml: str,
        env: dict[str, str],
        project_name: str,
    ) -> str:
        """Deploy services from a docker-compose YAML. Returns project name."""
        ...

    @abstractmethod
    def list_services(
        self,
        label_filter: str = "privacybox.managed=true",
    ) -> list[ServiceInfo]:
        """List managed services."""
        ...

    @abstractmethod
    def get_logs(
        self,
        service_name: str,
        tail: int = 100,
        follow: bool = False,
    ) -> Generator[str, None, None]:
        """Stream logs from a service."""
        ...

    @abstractmethod
    def destroy(
        self,
        project_name: str,
        keep_volumes: bool = False,
    ) -> bool:
        """Destroy a deployed project. Returns success."""
        ...

    @abstractmethod
    def get_service_info(self, service_name: str) -> Optional[ServiceInfo]:
        """Get detailed info about a single service."""
        ...

    @abstractmethod
    def health_check(self, service_name: str) -> HealthStatus:
        """Check if a service is responding."""
        ...

    @abstractmethod
    def get_engine_version(self) -> str:
        """Get the runtime engine version (e.g. Docker 24.0.7)."""
        ...
