from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class HookContext:
    event: str
    service_name: str
    project_name: str
    compose_yaml: str
    extra: dict[str, Any]


class Hook(ABC):
    """Lifecycle hook interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def run(self, context: HookContext) -> bool:
        """Execute hook. Return False to abort the operation."""
        ...


class ProxyPlugin(ABC):
    """Reverse proxy plugin interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def configure(
        self,
        domain: str,
        target_port: int,
        tls: bool = True,
    ) -> dict[str, Any]:
        """Return proxy configuration (YAML fragment) to inject into compose."""
        ...
