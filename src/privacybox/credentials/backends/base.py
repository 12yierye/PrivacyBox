from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from privacybox.utils.types import CredentialRecord


class CredentialBackend(ABC):
    """Storage backend for credentials — file or system keychain."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def store(self, record: CredentialRecord, secret: str) -> bool:
        ...

    @abstractmethod
    def retrieve(self, record_id: str) -> Optional[str]:
        """Retrieve secret by record ID. Returns None if not found."""
        ...

    @abstractmethod
    def list_records(self, active_only: bool = True) -> list[CredentialRecord]:
        ...

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        ...

    @abstractmethod
    def update_secret(self, record_id: str, new_secret: str) -> bool:
        ...
