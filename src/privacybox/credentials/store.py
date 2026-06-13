from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from privacybox.config.loader import get_credentials_dir, get_config_dir
from privacybox.config.schema import PrivacyBoxConfig
from privacybox.credentials.backends.base import CredentialBackend
from privacybox.state.database import Database
from privacybox.utils.types import CredentialRecord


class FileCredentialBackend(CredentialBackend):
    """Encrypted file-based credential storage."""

    def __init__(self, config: PrivacyBoxConfig):
        self.config = config
        self._key = self._get_or_create_key()

    @property
    def backend_name(self) -> str:
        return "file"

    def _get_or_create_key(self) -> bytes:
        key_file = get_config_dir() / ".cred_key"
        if key_file.exists():
            return key_file.read_bytes()
        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)
        key_file.chmod(0o600)
        return key

    def _encrypt(self, plaintext: str) -> str:
        f = Fernet(self._key)
        return f.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        f = Fernet(self._key)
        return f.decrypt(ciphertext.encode()).decode()

    def _record_path(self, record_id: str) -> Path:
        return get_credentials_dir() / f"{record_id}.enc"

    def is_available(self) -> bool:
        return True

    def store(self, record: CredentialRecord, secret: str) -> bool:
        encrypted = self._encrypt(secret)
        path = self._record_path(record.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encrypted, encoding="utf-8")
        path.chmod(0o600)
        return True

    def retrieve(self, record_id: str) -> Optional[str]:
        path = self._record_path(record_id)
        if not path.exists():
            return None
        encrypted = path.read_text(encoding="utf-8")
        return self._decrypt(encrypted)

    def list_records(self, active_only: bool = True) -> list[CredentialRecord]:
        cred_dir = get_credentials_dir()
        if not cred_dir.exists():
            return []
        records = []
        for f in cred_dir.glob("*.enc"):
            record_id = f.stem
            records.append(CredentialRecord(
                id=record_id,
                backend="file",
            ))
        return records

    def delete(self, record_id: str) -> bool:
        path = self._record_path(record_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def update_secret(self, record_id: str, new_secret: str) -> bool:
        return self.store(
            CredentialRecord(id=record_id, backend="file"),
            new_secret,
        )


class CredentialStore:
    """Main credential manager with dual-backend support and provenance."""

    def __init__(self, config: PrivacyBoxConfig, db: Database):
        self.config = config
        self.db = db
        self._backends: dict[str, CredentialBackend] = {
            "file": FileCredentialBackend(config),
        }
        self._init_keychain_backend()

    def _init_keychain_backend(self) -> None:
        try:
            from privacybox.credentials.backends.keychain_backend import KeychainCredentialBackend
            kc = KeychainCredentialBackend(self.config)
            if kc.is_available():
                self._backends["keychain"] = kc
        except Exception:
            pass

    def _get_backend(self, name: Optional[str] = None) -> CredentialBackend:
        backend_name = name or self.config.credentials.backend
        if backend_name not in self._backends:
            backend_name = "file"
        return self._backends[backend_name]

    def _compute_checksum(self, secret: str) -> str:
        return hashlib.sha256(secret.encode()).hexdigest()[:16]

    def store(self, record: CredentialRecord, secret: str) -> bool:
        backend = self._get_backend()
        record.backend = backend.backend_name
        record.checksum = self._compute_checksum(secret)
        record.migrated_from = None

        if backend.store(record, secret):
            self.db.save_credential(record)
            return True
        return False

    def retrieve(self, record_id: str) -> Optional[str]:
        """Retrieve secret, checking current backend first, then fallback."""
        record = self.db.get_credential(record_id)
        if not record:
            return None

        backend = self._get_backend(record.backend)
        secret = backend.retrieve(record_id)

        if secret is None and record.migrated_from:
            fallback = self._get_backend(record.migrated_from)
            secret = fallback.retrieve(record_id)

        return secret

    def delete(self, record_id: str) -> bool:
        record = self.db.get_credential(record_id)
        if not record:
            return False
        backend = self._get_backend(record.backend)
        if backend.delete(record_id):
            self.db.conn.execute(
                "UPDATE credentials SET active = 0 WHERE id = ?",
                (record_id,),
            )
            self.db.conn.commit()
            return True
        return False

    def migrate_all(self, to_backend: str) -> bool:
        """Migrate all active credentials to a different backend."""
        target = self._backends.get(to_backend)
        if not target or not target.is_available():
            return False

        source_backend_name = self.config.credentials.backend
        records = self.db.list_credentials(active_only=True)

        for record in records:
            if record.backend == to_backend:
                continue

            secret = self.retrieve(record.id)
            if secret is None:
                continue

            record.backend = to_backend
            record.migrated_from = source_backend_name
            from datetime import datetime
            record.migrated_at = datetime.now()

            if target.store(record, secret):
                db_record = self.db.get_credential(record.id)
                if db_record:
                    self.db.conn.execute(
                        """UPDATE credentials SET
                           backend = ?, migrated_from = ?, migrated_at = ?,
                           last_rotated_at = ?, checksum = ?
                           WHERE id = ?""",
                        (to_backend, source_backend_name,
                         record.migrated_at.isoformat(),
                         record.migrated_at.isoformat(),
                         record.checksum, record.id),
                    )
                else:
                    self.db.save_credential(record)

                self.db.conn.execute(
                    """INSERT INTO credential_migrations
                       (credential_id, from_backend, to_backend, status)
                       VALUES (?, ?, ?, 'success')""",
                    (record.id, source_backend_name, to_backend),
                )

        self.db.conn.commit()
        self.config.credentials.backend = to_backend

        from privacybox.config.loader import save_config
        save_config(self.config)

        return True

    def verify_all(self) -> dict[str, bool]:
        records = self.db.list_credentials(active_only=True)
        results = {}
        for record in records:
            secret = self.retrieve(record.id)
            if secret:
                expected = record.checksum
                actual = self._compute_checksum(secret)
                results[record.id] = expected == actual
            else:
                results[record.id] = False
        return results
