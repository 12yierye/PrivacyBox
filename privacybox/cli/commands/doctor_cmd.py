from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from privacybox.cli.app import app, console

STATUS_STYLES = {
    "ok": "green",
    "warn": "yellow",
    "error": "red",
    "info": "blue",
}


@app.command()
def doctor() -> None:
    """诊断环境兼容性"""
    from privacybox.config.loader import load_config
    from privacybox.doctor import Doctor

    cfg = load_config()
    doctor = Doctor(cfg)
    results = doctor.check_all()

    table = Table(title="环境诊断", border_style="cyan")
    table.add_column("检查项", style="bold")
    table.add_column("状态")
    table.add_column("详情")

    has_error = False
    for r in results:
        style = STATUS_STYLES.get(r["status"], "white")
        status_text = {
            "ok": "[OK]",
            "warn": "[!]",
            "error": "[X]",
            "info": "[i]",
        }.get(r["status"], "?")
        table.add_row(
            r["name"],
            f"[{style}]{status_text} {r['status']}[/]",
            r.get("detail", ""),
        )
        if r["status"] == "error":
            has_error = True

    console.print(table)

    if has_error:
        console.print()
        console.print(Panel(
            "[yellow]部分检查未通过，但 PrivacyBox 仍可运行。[/]\n"
            "安装 Docker 以获得完整功能。",
            border_style="yellow",
        ))
    else:
        console.print()
        console.print("[green][OK] 环境就绪，开始使用！[/]")
