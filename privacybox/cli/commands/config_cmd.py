from __future__ import annotations

import os
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from privacybox.cli.app import _get_config, app, console
from privacybox.config.loader import config_path_from_env, save_config

config_app = typer.Typer(help="管理配置")
app.add_typer(config_app, name="config")


@config_app.callback(invoke_without_command=True)
def config_main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        show()


def show() -> None:
    cfg, _ = _get_config()
    raw = yaml.dump(cfg.model_dump(), default_flow_style=False, allow_unicode=True, sort_keys=False)
    syntax = Syntax(raw, "yaml", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="当前配置", border_style="cyan"))


@config_app.command()
def show() -> None:
    cfg, _ = _get_config()
    raw = yaml.dump(cfg.model_dump(), default_flow_style=False, allow_unicode=True, sort_keys=False)
    syntax = Syntax(raw, "yaml", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="当前配置", border_style="cyan"))


@config_app.command()
def set(
    key: str = typer.Argument(..., help="配置键，如 llm.default_provider"),
    value: str = typer.Argument(..., help="配置值"),
) -> None:
    cfg, _ = _get_config()
    keys = key.split(".")
    target = cfg.model_dump()
    current = target
    for k in keys[:-1]:
        if k not in current:
            console.print(f"[red]配置键 '{key}' 不存在[/]")
            raise typer.Exit(1)
        current = current[k]
    last_key = keys[-1]
    if last_key not in current:
        console.print(f"[red]配置键 '{key}' 不存在[/]")
        raise typer.Exit(1)

    typed_val = _coerce_type(current[last_key], value)
    current[last_key] = typed_val

    new_cfg = type(cfg).model_validate(target)
    save_config(new_cfg)
    console.print(f"[green][OK] 已设置 {key} = {value}[/]")


@config_app.command()
def edit() -> None:
    path = config_path_from_env()
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
    if not editor:
        console.print("[yellow]未设置 EDITOR 环境变量，使用默认编辑器[/]")
        editor = "notepad" if os.name == "nt" else "vi"
    os.system(f'"{editor}" "{path}"')


@config_app.command()
def reset() -> None:
    import questionary
    if questionary.confirm("确认重置所有配置为默认值？", default=False).ask():
        from privacybox.config.loader import _build_default_config
        cfg = _build_default_config()
        save_config(cfg)
        console.print("[green][OK] 配置已重置[/]")


@config_app.command()
def wizard() -> None:
    from privacybox.config.wizard import run_wizard
    run_wizard()


def _coerce_type(current_val, str_val):
    if isinstance(current_val, bool):
        return str_val.lower() in ("true", "1", "yes")
    if isinstance(current_val, int):
        return int(str_val)
    if isinstance(current_val, float):
        return float(str_val)
    return str_val
