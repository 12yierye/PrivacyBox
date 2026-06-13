from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DockerConfig(BaseModel):
    socket: str = ""


class PodmanConfig(BaseModel):
    socket: str = ""


class K8sConfig(BaseModel):
    kubeconfig: str = ""
    namespace: str = "default"


class RuntimeConfig(BaseModel):
    backend: str = "docker"
    docker: DockerConfig = Field(default_factory=DockerConfig)
    podman: PodmanConfig = Field(default_factory=PodmanConfig)
    k8s: K8sConfig = Field(default_factory=K8sConfig)


class LLMProviderItem(BaseModel):
    endpoint: str = ""
    api_key_file: str = ""
    model: str = ""


class LLMConfig(BaseModel):
    default_provider: str = "ollama"
    providers: dict[str, LLMProviderItem] = Field(default_factory=dict)


class DeployConfig(BaseModel):
    default_strategy: str = "ask"
    remember_last: bool = True


class TierConfig(BaseModel):
    network: str = "localhost"


class PrivacyConfig(BaseModel):
    default_tier: int = 2
    wizard_on_first_run: bool = True
    tiers: dict[int, TierConfig] = Field(default_factory=lambda: {
        1: TierConfig(network="isolated"),
        2: TierConfig(network="localhost"),
        3: TierConfig(network="vpn"),
        4: TierConfig(network="lan"),
        5: TierConfig(network="public"),
    })


class EncryptionConfig(BaseModel):
    enabled: bool = False
    backend: str = "auto"


class ProxyConfig(BaseModel):
    builtin: str = "traefik"
    plugins: list[str] = Field(default_factory=list)


class UIConfig(BaseModel):
    mode: str = "cli"
    simple_mode: bool = True
    theme: str = "auto"


class CredentialsConfig(BaseModel):
    backend: str = "file"


class RemoteConfig(BaseModel):
    default_host: str = ""
    ssh_key: str = ""


class CicdConfig(BaseModel):
    enabled: bool = False
    config_file: str = "privacybox.yaml"


class PrivacyBoxConfig(BaseModel):
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    deploy: DeployConfig = Field(default_factory=DeployConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    credentials: CredentialsConfig = Field(default_factory=CredentialsConfig)
    remote: RemoteConfig = Field(default_factory=RemoteConfig)
    cicd: CicdConfig = Field(default_factory=CicdConfig)
