from __future__ import annotations

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from privacybox.cli.app import _get_config, app, console

template_app = typer.Typer(help="管理部署模板")
app.add_typer(template_app, name="template")


@template_app.callback(invoke_without_command=True)
def template_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        list_templates()


def list_templates() -> None:
    from privacybox.templates.registry import TemplateRegistry
    registry = TemplateRegistry()
    templates = registry.list_all()

    if not templates:
        console.print("[yellow]暂无可用模板[/]")
        return

    table = Table(title="可用模板", border_style="cyan")
    table.add_column("名称", style="bold")
    table.add_column("版本")
    table.add_column("描述")
    table.add_column("分类")

    for t in templates:
        cats = ", ".join(t.categories) if t.categories else "-"
        table.add_row(t.name, t.version, t.description[:60], cats)

    console.print(table)


@template_app.command()
def list() -> None:
    list_templates()


@template_app.command()
def show(
    name: str = typer.Argument(..., help="模板名称"),
) -> None:
    from privacybox.templates.registry import TemplateRegistry
    registry = TemplateRegistry()
    template = registry.get(name)

    if not template:
        console.print(f"[red]模板 '{name}' 不存在[/]")
        raise typer.Exit(1)

    console.print(f"[bold]模板:[/] {template.name} v{template.version}")
    console.print(f"[bold]描述:[/] {template.description}")
    console.print(f"[bold]分类:[/] {', '.join(template.categories)}")
    console.print()

    if template.params:
        table = Table(title="参数列表", border_style="cyan")
        table.add_column("参数名", style="bold")
        table.add_column("类型")
        table.add_column("标签")
        table.add_column("默认值")
        table.add_column("必填")
        table.add_column("高级")

        for p in template.params:
            table.add_row(
                p.name,
                p.type,
                p.label,
                str(p.default or ""),
                "[OK]" if p.required else "",
                "[OK]" if p.advanced else "",
            )
        console.print(table)


@template_app.command()
def validate(
    path: str = typer.Argument(..., help="模板文件路径"),
) -> None:
    p = Path(path)
    if not p.exists():
        console.print(f"[red]文件不存在: {path}[/]")
        raise typer.Exit(1)

    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    errors = []
    if "name" not in data:
        errors.append("缺少 name")
    if "compose" not in data:
        errors.append("缺少 compose")

    if errors:
        console.print(f"[red]校验失败:[/]")
        for e in errors:
            console.print(f"  - {e}")
        raise typer.Exit(1)

    console.print("[green][OK] 模板格式正确[/]")


@template_app.command()
def publish(
    path: str = typer.Argument(..., help="模板文件路径"),
) -> None:
    console.print("[yellow]社区模板发布功能即将上线[/]")
    console.print("敬请期待: https://github.com/privacybox/templates")
