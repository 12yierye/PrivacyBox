from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Optional
from uuid import uuid4


class PrivacyTier(IntEnum):
    ISOLATED = 1
    LOCALHOST = 2
    VPN = 3
    LAN = 4
    PUBLIC = 5


class ServiceStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class DeployStrategy(str):
    TEMPLATE = "template"
    LLM = "llm"
    HYBRID = "hybrid"
    ASK = "ask"


class RuntimeBackendType(str):
    DOCKER = "docker"
    PODMAN = "podman"
    K8S = "k8s"


class LLMProviderType(str):
    OLLAMA = "ollama"
    OPENAI = "openai"
    CLAUDE = "claude"
    CUSTOM = "custom"


@dataclass
class PortMapping:
    host_ip: str = "127.0.0.1"
    host_port: int = 0
    container_port: int = 0
    protocol: str = "tcp"
    privacy_tier: PrivacyTier = PrivacyTier.LOCALHOST


@dataclass
class VolumeMount:
    host_path: str = ""
    container_path: str = ""
    encrypted: bool = False
    size_bytes: Optional[int] = None


@dataclass
class ServiceInfo:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    status: str = ServiceStatus.PENDING
    runtime_backend: str = RuntimeBackendType.DOCKER
    compose_yaml: str = ""
    privacy_tier: PrivacyTier = PrivacyTier.LOCALHOST
    template_name: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_conversation: Optional[str] = None
    ports: list[PortMapping] = field(default_factory=list)
    volumes: list[VolumeMount] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    deployed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ComposeResult:
    yaml: str
    metadata: dict = field(default_factory=dict)
    provider_used: str = ""
    raw_response: str = ""
    retries: int = 0


@dataclass
class HealthStatus:
    healthy: bool = False
    message: str = ""
    response_time_ms: Optional[float] = None


@dataclass
class TemplateParam:
    name: str = ""
    type: str = "string"
    label: str = ""
    hint: str = ""
    default: object = None
    required: bool = False
    advanced: bool = False
    auto_generate: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass
class TemplateDef:
    name: str = ""
    version: str = "1.0"
    description: str = ""
    categories: list[str] = field(default_factory=list)
    author: str = ""
    params: list[TemplateParam] = field(default_factory=list)
    compose_template: str = ""


@dataclass
class CredentialRecord:
    id: str = field(default_factory=lambda: str(uuid4()))
    provider: str = ""
    backend: str = "file"
    label: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: Optional[datetime] = None
    last_rotated_at: Optional[datetime] = None
    migrated_from: Optional[str] = None
    migrated_at: Optional[datetime] = None
    checksum: str = ""
    active: bool = True


@dataclass
class PipelineService:
    name: str = ""
    template: str = ""
    params: dict = field(default_factory=dict)
    privacy_tier: PrivacyTier = PrivacyTier.LOCALHOST


@dataclass
class PipelineHook:
    command: Optional[str] = None
    webhook: Optional[str] = None
    timeout: int = 30


@dataclass
class PipelineEnvironment:
    remote: Optional[str] = None
    privacy_tier: PrivacyTier = PrivacyTier.LOCALHOST
    proxy: bool = False


@dataclass
class PipelineDef:
    version: str = "1.0"
    services: list[PipelineService] = field(default_factory=list)
    hooks: dict[str, list[PipelineHook]] = field(default_factory=dict)
    environments: dict[str, PipelineEnvironment] = field(default_factory=dict)
