from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import typer
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

from privacybox.cli.app import _get_config, app, console
from privacybox.config.loader import get_data_dir
from privacybox.utils.types import (
    ComposeResult,
    DeployStrategy,
    PortMapping,
    PrivacyTier,
    ServiceInfo,
    TemplateDef,
    VolumeMount,
)


@app.command()
def deploy(
    description: str = typer.Argument("", help="描述你要部署的服务"),
    mode: str = typer.Option("ask", "--mode", "-m", help="部署策略: template|llm|ask"),
    tier: int = typer.Option(0, "--tier", "-t", help="隐私等级: 1-5"),
    simple: bool = typer.Option(True, "--simple/--advanced", help="简单/高级模式"),
    remote: str = typer.Option("", "--remote", "-r", help="远程部署地址 user@host"),
    encrypt: bool = typer.Option(False, "--encrypt", help="启用数据卷加密"),
) -> None:
    cfg, db = _get_config()

    if not description:
        import questionary
        description = questionary.text("描述你要部署的服务：").ask() or ""

    if not description.strip():
        console.print("[red]请输入服务描述[/]")
        raise typer.Exit(1)

    effective_tier = tier if tier > 0 else cfg.privacy.default_tier
    effective_mode = mode if mode != "ask" else cfg.deploy.default_strategy
    if effective_mode == "ask":
        effective_mode = _ask_strategy()

    privacy_ip = _privacy_ip_for_tier(PrivacyTier(effective_tier))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]正在解析部署需求...", total=None)

        if effective_mode == DeployStrategy.TEMPLATE:
            result = _deploy_via_template(
                description, effective_tier, privacy_ip, simple, progress
            )
        elif effective_mode == DeployStrategy.LLM:
            result = _deploy_via_llm(
                description, effective_tier, privacy_ip, cfg, progress
            )
        else:
            result = _deploy_via_hybrid(
                description, effective_tier, privacy_ip, cfg, simple, progress
            )

        if not result:
            console.print("[red][X] 部署失败，无法生成有效的配置[/]")
            raise typer.Exit(1)

        progress.update(task, description="[cyan]正在部署到容器运行时...")

        from privacybox.runtime.docker_backend import DockerBackend
        backend = DockerBackend(cfg)

        if not backend.is_available():
            console.print("[red][X] Docker 不可用，请先安装 Docker[/]")
            raise typer.Exit(1)

        try:
            project_name = backend.deploy(
                compose_yaml=result.yaml,
                env={},
                project_name=_name_from_metadata(result.metadata),
            )
        except Exception as e:
            console.print(f"[red][X] 部署失败: {e}[/]")
            console.print("[yellow]生成的 docker-compose.yml 如下：[/]")
            console.print(result.yaml)
            raise typer.Exit(1)

        progress.update(task, description="[green][OK] 部署完成")

    service = ServiceInfo(
        name=_name_from_metadata(result.metadata),
        status="running",
        compose_yaml=result.yaml,
        privacy_tier=PrivacyTier(effective_tier),
        template_name=result.metadata.get("template_name"),
        llm_provider=result.metadata.get("provider_used"),
        llm_conversation=result.raw_response,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        deployed_at=datetime.now(),
    )
    db.save_service(service)

    console.print()
    console.print(Panel.fit(
        f"[bold green][OK] 服务已部署[/]\n\n"
        f"  服务: [bold]{service.name}[/]\n"
        f"  隐私等级: {_tier_label(PrivacyTier(effective_tier))}\n"
        f"  部署方式: {result.metadata.get('method', effective_mode)}\n\n"
        f"  查看状态: [bold]privacybox list[/]\n"
        f"  查看日志: [bold]privacybox logs {service.name}[/]\n"
        f"  删除服务: [bold]privacybox destroy {service.name}[/]",
        border_style="green",
    ))


def _ask_strategy() -> str:
    import questionary
    return questionary.select(
        "选择部署方式：",
        choices=[
            ("用 AI 生成配置（灵活）", "llm"),
            ("从模板匹配（可靠）", "template"),
            ("AI + 模板混合", "hybrid"),
        ],
        default="hybrid",
    ).ask() or "hybrid"


def _deploy_via_template(
    description: str,
    tier: int,
    privacy_ip: str,
    simple_mode: bool,
    progress,
) -> Optional[ComposeResult]:
    from privacybox.templates.registry import TemplateRegistry
    from privacybox.templates.renderer import render_template

    registry = TemplateRegistry()
    match = registry.match(description)

    if not match:
        console.print("[yellow]未匹配到模板，切换到 AI 生成...[/]")
        return None

    progress.update(progress.task_ids[0] if hasattr(progress, 'task_ids') else None,
                     description=f"[cyan]已匹配模板: {match.name}[/]")

    import questionary
    params = {}
    for p in match.params:
        if p.advanced and simple_mode:
            continue
        if p.type == "password":
            val = questionary.password(
                f"{p.label}: ",
                default=str(p.default or ""),
            ).ask() or ""
            if not val and p.auto_generate:
                import secrets
                import string
                val = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
                console.print(f"  自动生成: {val}")
        elif p.type == "number":
            val = questionary.text(
                f"{p.label}: ",
                default=str(p.default or ""),
            ).ask() or str(p.default or "")
        else:
            val = questionary.text(
                f"{p.label}: ",
                default=str(p.default or ""),
            ).ask() or str(p.default or "")
        params[p.name] = val

    params["privacy_ip"] = privacy_ip
    params["tier"] = str(tier)

    rendered = render_template(match, params)
    return ComposeResult(
        yaml=rendered,
        metadata={
            "template_name": match.name,
            "method": "template",
            "name": params.get("name", match.name),
        },
    )


def _deploy_via_llm(
    description: str,
    tier: int,
    privacy_ip: str,
    cfg,
    progress,
) -> Optional[ComposeResult]:
    provider_name = cfg.llm.default_provider
    progress.update(progress.task_ids[0] if hasattr(progress, 'task_ids') else None,
                     description=f"[cyan]正在调用 {provider_name} AI 生成配置...")

    provider = _get_llm_provider(provider_name, cfg)
    if not provider or not provider.is_available():
        console.print(f"[yellow]{provider_name} 不可用，尝试其他提供商...[/]")
        fallbacks = [p for p in ["ollama", "openai", "claude"] if p != provider_name]
        for fb in fallbacks:
            provider = _get_llm_provider(fb, cfg)
            if provider and provider.is_available():
                provider_name = fb
                break
        if not provider or not provider.is_available():
            console.print("[red]没有可用的 LLM 提供商[/]")
            console.print("请配置 API Key: [bold]privacybox config set llm.providers.openai.api_key_file <path>[/]")
            return None

    result = provider.generate_compose(
        user_input=description,
        privacy_tier=PrivacyTier(tier),
    )

    if not result or not result.yaml.strip():
        return None

    return ComposeResult(
        yaml=result.yaml.replace("0.0.0.0", privacy_ip) if privacy_ip != "0.0.0.0" else result.yaml,
        metadata={
            "provider_used": provider_name,
            "method": "llm",
            "name": result.metadata.get("name", "app"),
        },
        raw_response=result.raw_response,
    )


def _deploy_via_hybrid(
    description: str,
    tier: int,
    privacy_ip: str,
    cfg,
    simple_mode: bool,
    progress,
) -> Optional[ComposeResult]:
    result = _deploy_via_template(description, tier, privacy_ip, simple_mode, progress)
    if result:
        return result
    return _deploy_via_llm(description, tier, privacy_ip, cfg, progress)


def _get_llm_provider(name: str, cfg):
    from privacybox.llm.ollama_provider import OllamaProvider
    from privacybox.llm.openai_provider import OpenAIProvider
    from privacybox.llm.claude_provider import ClaudeProvider

    providers = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
    }
    cls = providers.get(name)
    if not cls:
        return None
    return cls(cfg)


def _privacy_ip_for_tier(tier: PrivacyTier) -> str:
    return {
        PrivacyTier.ISOLATED: "",
        PrivacyTier.LOCALHOST: "127.0.0.1",
        PrivacyTier.VPN: "127.0.0.1",
        PrivacyTier.LAN: "0.0.0.0",
        PrivacyTier.PUBLIC: "0.0.0.0",
    }.get(tier, "127.0.0.1")


def _tier_label(tier: PrivacyTier) -> str:
    labels = {
        PrivacyTier.ISOLATED: "T1 完全隔离",
        PrivacyTier.LOCALHOST: "T2 仅本机",
        PrivacyTier.VPN: "T3 VPN 网络",
        PrivacyTier.LAN: "T4 局域网",
        PrivacyTier.PUBLIC: "T5 公网+TLS",
    }
    return labels.get(tier, f"T{int(tier)}")


def _name_from_metadata(meta: dict) -> str:
    return meta.get("name", meta.get("template_name", "app"))
