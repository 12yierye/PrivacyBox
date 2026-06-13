from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from privacybox.config.loader import get_db_path
from privacybox.utils.types import (
    CredentialRecord,
    PortMapping,
    PrivacyTier,
    ServiceInfo,
    VolumeMount,
)


class Database:
    """SQLite-based state database with migration tracking."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_migrations()

    def _ensure_migrations(self) -> None:
        current_version = self._get_current_version()
        for migration in MIGRATIONS:
            if migration.version > current_version:
                self._apply_migration(migration)

    def _get_current_version(self) -> int:
        try:
            row = self.conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()
            return row[0] or 0
        except sqlite3.OperationalError:
            return 0

    def _apply_migration(self, migration: Migration) -> None:
        checksum = hashlib.sha256(migration.sql.encode()).hexdigest()
        self.conn.executescript(migration.sql)
        self.conn.execute(
            "INSERT INTO schema_migrations (version, description, checksum) VALUES (?, ?, ?)",
            (migration.version, migration.description, checksum),
        )
        self.conn.commit()

    # ---- Service CRUD ----

    def save_service(self, service: ServiceInfo) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO services
               (id, name, status, compose_yaml, privacy_tier, runtime_backend,
                template_name, llm_provider, llm_conversation,
                created_at, updated_at, deployed_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                service.id, service.name, service.status, service.compose_yaml,
                int(service.privacy_tier), service.runtime_backend,
                service.template_name, service.llm_provider, service.llm_conversation,
                service.created_at.isoformat(), service.updated_at.isoformat(),
                service.deployed_at.isoformat() if service.deployed_at else None,
                json.dumps(service.metadata),
            ),
        )
        self._save_ports(service)
        self._save_volumes(service)
        self.conn.commit()

    def _save_ports(self, service: ServiceInfo) -> None:
        self.conn.execute("DELETE FROM ports WHERE service_id = ?", (service.id,))
        for p in service.ports:
            self.conn.execute(
                """INSERT INTO ports (id, service_id, host_ip, host_port, container_port, protocol, privacy_tier)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (p.host_ip or "127.0.0.1", service.id, p.host_ip or "127.0.0.1",
                 p.host_port, p.container_port, p.protocol, int(p.privacy_tier)),
            )

    def _save_volumes(self, service: ServiceInfo) -> None:
        self.conn.execute("DELETE FROM volumes WHERE service_id = ?", (service.id,))
        for v in service.volumes:
            self.conn.execute(
                """INSERT INTO volumes (id, service_id, host_path, container_path, encrypted, size_bytes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (v.host_path, service.id, v.host_path, v.container_path,
                 int(v.encrypted), v.size_bytes),
            )

    def list_services(self, status: Optional[str] = None) -> list[ServiceInfo]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM services WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM services ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_service(r) for r in rows]

    def get_service(self, name: str) -> Optional[ServiceInfo]:
        row = self.conn.execute(
            "SELECT * FROM services WHERE name = ? OR id = ?", (name, name)
        ).fetchone()
        return self._row_to_service(row) if row else None

    def delete_service(self, name: str) -> bool:
        svc = self.get_service(name)
        if not svc:
            return False
        self.conn.execute("DELETE FROM ports WHERE service_id = ?", (svc.id,))
        self.conn.execute("DELETE FROM volumes WHERE service_id = ?", (svc.id,))
        self.conn.execute("DELETE FROM services WHERE id = ?", (svc.id,))
        self.conn.commit()
        return True

    def update_service_status(self, name: str, status: str) -> None:
        self.conn.execute(
            "UPDATE services SET status = ?, updated_at = ? WHERE name = ?",
            (status, datetime.now().isoformat(), name),
        )
        self.conn.commit()

    def _row_to_service(self, row: sqlite3.Row) -> ServiceInfo:
        ports = [
            PortMapping(
                host_ip=r["host_ip"],
                host_port=r["host_port"],
                container_port=r["container_port"],
                protocol=r["protocol"],
                privacy_tier=PrivacyTier(r["privacy_tier"]),
            )
            for r in self.conn.execute(
                "SELECT * FROM ports WHERE service_id = ?", (row["id"],)
            ).fetchall()
        ]
        volumes = [
            VolumeMount(
                host_path=r["host_path"],
                container_path=r["container_path"],
                encrypted=bool(r["encrypted"]),
                size_bytes=r["size_bytes"],
            )
            for r in self.conn.execute(
                "SELECT * FROM volumes WHERE service_id = ?", (row["id"],)
            ).fetchall()
        ]
        return ServiceInfo(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            compose_yaml=row["compose_yaml"] or "",
            privacy_tier=PrivacyTier(row["privacy_tier"]),
            runtime_backend=row["runtime_backend"],
            template_name=row["template_name"],
            llm_provider=row["llm_provider"],
            llm_conversation=row["llm_conversation"],
            ports=ports,
            volumes=volumes,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deployed_at=datetime.fromisoformat(row["deployed_at"]) if row.get("deployed_at") else None,
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
        )

    # ---- Credential CRUD ----

    def save_credential(self, record: CredentialRecord) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO credentials
               (id, provider, backend, label, created_at, last_accessed_at,
                last_rotated_at, migrated_from, migrated_at, checksum, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id, record.provider, record.backend, record.label,
                record.created_at.isoformat(),
                record.last_accessed_at.isoformat() if record.last_accessed_at else None,
                record.last_rotated_at.isoformat() if record.last_rotated_at else None,
                record.migrated_from, record.migrated_at.isoformat() if record.migrated_at else None,
                record.checksum, int(record.active),
            ),
        )
        self.conn.commit()

    def list_credentials(self, active_only: bool = True) -> list[CredentialRecord]:
        if active_only:
            rows = self.conn.execute(
                "SELECT * FROM credentials WHERE active = 1"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM credentials"
            ).fetchall()
        return [self._row_to_credential(r) for r in rows]

    def get_credential(self, record_id: str) -> Optional[CredentialRecord]:
        row = self.conn.execute(
            "SELECT * FROM credentials WHERE id = ?", (record_id,)
        ).fetchone()
        return self._row_to_credential(row) if row else None

    def _row_to_credential(self, row: sqlite3.Row) -> CredentialRecord:
        return CredentialRecord(
            id=row["id"],
            provider=row["provider"],
            backend=row["backend"],
            label=row["label"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]) if row.get("last_accessed_at") else None,
            last_rotated_at=datetime.fromisoformat(row["last_rotated_at"]) if row.get("last_rotated_at") else None,
            migrated_from=row["migrated_from"],
            migrated_at=datetime.fromisoformat(row["migrated_at"]) if row.get("migrated_at") else None,
            checksum=row["checksum"],
            active=bool(row["active"]),
        )

    def close(self) -> None:
        self.conn.close()


class Migration:
    def __init__(self, version: int, description: str, sql: str):
        self.version = version
        self.description = description
        self.sql = sql


MIGRATIONS = [
    Migration(1, "Initial schema", """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            description TEXT,
            checksum TEXT
        );

        CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            compose_yaml TEXT,
            privacy_tier INTEGER DEFAULT 2,
            runtime_backend TEXT DEFAULT 'docker',
            template_name TEXT,
            llm_provider TEXT,
            llm_conversation TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deployed_at TEXT,
            metadata TEXT
        );

        CREATE TABLE IF NOT EXISTS volumes (
            id TEXT PRIMARY KEY,
            service_id TEXT NOT NULL,
            host_path TEXT NOT NULL,
            container_path TEXT NOT NULL,
            encrypted INTEGER DEFAULT 0,
            size_bytes INTEGER,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ports (
            id TEXT PRIMARY KEY,
            service_id TEXT NOT NULL,
            host_ip TEXT NOT NULL DEFAULT '127.0.0.1',
            host_port INTEGER NOT NULL,
            container_port INTEGER NOT NULL,
            protocol TEXT DEFAULT 'tcp',
            privacy_tier INTEGER DEFAULT 2,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS credentials (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            backend TEXT NOT NULL,
            label TEXT,
            created_at TEXT NOT NULL,
            last_accessed_at TEXT,
            last_rotated_at TEXT,
            migrated_from TEXT,
            migrated_at TEXT,
            checksum TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS credential_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credential_id TEXT NOT NULL,
            from_backend TEXT NOT NULL,
            to_backend TEXT NOT NULL,
            migrated_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (credential_id) REFERENCES credentials(id)
        );

        CREATE INDEX IF NOT EXISTS idx_services_name ON services(name);
        CREATE INDEX IF NOT EXISTS idx_services_status ON services(status);
        CREATE INDEX IF NOT EXISTS idx_credentials_provider ON credentials(provider);
        CREATE INDEX IF NOT EXISTS idx_credentials_active ON credentials(active);
    """),
]
