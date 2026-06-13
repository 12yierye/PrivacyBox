from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from privacybox import __version__

app = typer.Typer(
    name="privacybox",
    help="自然语言驱动的自部署引擎 — 一句话部署任意服务，隐私默认可调",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="显示版本号"),
) -> None:
    if version:
        console.print(f"PrivacyBox v{__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]PrivacyBox[/] — 自然语言驱动的自部署引擎")
        console.print(f"版本 {__version__}")
        console.print()
        console.print("快速开始：")
        console.print("  [bold]privacybox deploy \"帮我部署一个 Nextcloud\"[/]")
        console.print("  [bold]privacybox --help[/]  查看全部命令")
        console.print()
        console.print("首次使用？先运行向导：")
        console.print("  [bold]privacybox config wizard[/]")


def _get_config() -> tuple:
    """Load config and initialize database."""
    from privacybox.config.loader import load_config, get_default_config_path
    from privacybox.config.wizard import run_wizard
    from privacybox.state.database import Database

    cfg = load_config()
    db = Database()
    return cfg, db


# Import command modules to register them with Typer
import privacybox.cli.commands.deploy  # noqa: F401, E402
import privacybox.cli.commands.manage  # noqa: F401, E402
import privacybox.cli.commands.config_cmd  # noqa: F401, E402
import privacybox.cli.commands.template_cmd  # noqa: F401, E402
import privacybox.cli.commands.credential_cmd  # noqa: F401, E402
import privacybox.cli.commands.doctor_cmd  # noqa: F401, E402
