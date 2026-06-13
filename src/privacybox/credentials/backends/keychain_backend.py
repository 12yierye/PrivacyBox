from __future__ import annotations

import sys
from typing import Optional

from privacybox.config.schema import PrivacyBoxConfig
from privacybox.credentials.backends.base import CredentialBackend
from privacybox.utils.types import CredentialRecord


class KeychainCredentialBackend(CredentialBackend):
    """System keychain credential storage.
    Uses keyring library for cross-platform support.
    """

    def __init__(self, config: PrivacyBoxConfig):
        self.config = config
        self._available = False
        self._init_keychain()

    def _init_keychain(self) -> None:
        try:
            import keyring
            keyring.get_keyring()
            self._available = True
        except Exception:
            self._available = False

    @property
    def backend_name(self) -> str:
        return "keychain"

    def is_available(self) -> bool:
        return self._available

    def _get_service_name(self) -> str:
        return "privacybox"

    def store(self, record: CredentialRecord, secret: str) -> bool:
        if not self._available:
            return False
        import keyring
        try:
            keyring.set_password(self._get_service_name(), record.id, secret)
            return True
        except Exception:
            return False

    def retrieve(self, record_id: str) -> Optional[str]:
        if not self._available:
            return None
        import keyring
        try:
            return keyring.get_password(self._get_service_name(), record_id)
        except Exception:
            return None

    def list_records(self, active_only: bool = True) -> list[CredentialRecord]:
        return []

    def delete(self, record_id: str) -> bool:
        if not self._available:
            return False
        import keyring
        try:
            keyring.delete_password(self._get_service_name(), record_id)
            return True
        except Exception:
            return False

    def update_secret(self, record_id: str, new_secret: str) -> bool:
        return self.store(
            CredentialRecord(id=record_id, backend="keychain"),
            new_secret,
        )
