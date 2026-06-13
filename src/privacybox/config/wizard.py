from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from privacybox.config.loader import PrivacyBoxConfig, save_config

console = Console()


def run_wizard() -> PrivacyBoxConfig:
    """Interactive first-run wizard to set up PrivacyBox."""

    console.print(Panel.fit(
        "[bold cyan]PrivacyBox 首次配置向导[/]\n\n"
        "这个向导会帮你完成基本配置，只需 1 分钟。\n"
        "所有设置都可以之后通过 [bold]privacybox config set[/] 修改。",
        border_style="cyan",
    ))

    import questionary

    config = PrivacyBoxConfig()

    config.deploy.default_strategy = questionary.select(
        "部署策略：你希望默认怎么部署服务？",
        choices=[
            ("每次询问我（推荐）", "ask"),
            ("优先用模板匹配", "template"),
            ("优先用 AI 生成", "llm"),
        ],
        default="ask",
    ).ask() or "ask"

    config.privacy.default_tier = int(questionary.select(
        "隐私等级：新服务的网络暴露默认设为什么？",
        choices=[
            ("T2 - 仅本机访问（127.0.0.1，推荐）", "2"),
            ("T1 - 完全隔离，不暴露任何端口", "1"),
            ("T4 - 局域网可访问", "4"),
            ("T5 - 公网可访问（需谨慎）", "5"),
        ],
        default="2",
    ).ask() or "2")

    config.llm.default_provider = questionary.select(
        "LLM 提供商：你主要想用哪个 AI 模型生成配置？",
        choices=[
            ("Ollama 本地（免费·隐私）", "ollama"),
            ("OpenAI GPT-4o（需 API Key）", "openai"),
            ("Anthropic Claude（需 API Key）", "claude"),
        ],
        default="ollama",
    ).ask() or "ollama"

    if config.llm.default_provider in ("openai", "claude"):
        key = questionary.password(
            f"请输入 {config.llm.default_provider} API Key："
        ).ask()
        if key:
            _write_api_key(config.llm.default_provider, key)

    config.ui.simple_mode = questionary.confirm(
        "简单模式：是否隐藏高级参数？\n（可随时用 --advanced 切换）",
        default=True,
    ).ask()

    save_config(config)

    console.print("[bold green][OK] 配置完成！开始使用吧：[/]")
    console.print("  privacybox deploy \"帮我部署一个 Nextcloud\"")

    return config


def _write_api_key(provider: str, key: str) -> None:
    from privacybox.config.loader import get_credentials_dir
    cred_dir = get_credentials_dir()
    cred_dir.mkdir(parents=True, exist_ok=True)
    key_file = cred_dir / f"{provider}.key"
    key_file.write_text(key, encoding="utf-8")
    key_file.chmod(0o600)
