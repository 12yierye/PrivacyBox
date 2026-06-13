from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from privacybox.cli.app import _get_config, app, console

manage_app = typer.Typer(help="管理已部署的服务")
app.add_typer(manage_app, name="list", hidden=True)


@manage_app.callback(invoke_without_command=True)
def list_services(
    status: str = typer.Option("", "--status", "-s", help="按状态过滤"),
    format: str = typer.Option("table", "--format", "-f", help="输出格式: table|json|yaml"),
) -> None:
    """列出所有已部署的服务"""
    cfg, db = _get_config()
    services = db.list_services(status=status or None)

    if not services:
        console.print("[yellow]还没有部署任何服务。[/]")
        console.print("使用 [bold]privacybox deploy[/] 开始部署！")
        raise typer.Exit()

    if format == "json":
        data = [
            {
                "name": s.name,
                "status": s.status,
                "privacy_tier": int(s.privacy_tier),
                "ports": [f"{p.host_ip}:{p.host_port}->{p.container_port}" for p in s.ports],
                "created": s.created_at.isoformat(),
            }
            for s in services
        ]
        console.print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if format == "yaml":
        import yaml
        data = [
            {
                "name": s.name,
                "status": s.status,
                "privacy_tier": int(s.privacy_tier),
                "ports": [f"{p.host_ip}:{p.host_port}" for p in s.ports],
                "created": s.created_at.isoformat(),
            }
            for s in services
        ]
        console.print(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        return

    table = Table(title="已部署服务", border_style="cyan")
    table.add_column("名称", style="bold")
    table.add_column("状态")
    table.add_column("端口")
    table.add_column("隐私等级")
    table.add_column("部署时间")

    for s in services:
        ports = ", ".join(
            f"{p.host_ip}:{p.host_port}" for p in s.ports[:3]
        ) or "无"
        tier_label = {1: "T1 隔离", 2: "T2 本地", 3: "T3 VPN", 4: "T4 局域网", 5: "T5 公网"}
        status_style = {
            "running": "green",
            "stopped": "yellow",
            "error": "red",
            "pending": "blue",
        }.get(s.status, "")
        table.add_row(
            s.name,
            f"[{status_style}]{s.status}[/]",
            ports,
            tier_label.get(s.privacy_tier, str(s.privacy_tier)),
            s.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@app.command()
def logs(
    service_name: str = typer.Argument(..., help="服务名称"),
    tail: int = typer.Option(100, "--tail", "-t", help="显示行数"),
    follow: bool = typer.Option(False, "--follow", "-f", help="实时追踪"),
) -> None:
    """查看服务日志"""
    cfg, db = _get_config()
    service = db.get_service(service_name)
    if not service:
        console.print(f"[red]服务 '{service_name}' 不存在[/]")
        raise typer.Exit(1)

    from privacybox.runtime.docker_backend import DockerBackend
    backend = DockerBackend(cfg)

    if not backend.is_available():
        console.print("[red]Docker 不可用[/]")
        raise typer.Exit(1)

    try:
        for line in backend.get_logs(service_name, tail=tail, follow=follow):
            console.print(line, end="")
    except Exception as e:
        console.print(f"[red]获取日志失败: {e}[/]")
        raise typer.Exit(1)


@app.command()
def destroy(
    service_name: str = typer.Argument(..., help="服务名称"),
    keep_data: bool = typer.Option(False, "--keep-data", help="保留数据卷"),
    force: bool = typer.Option(False, "--force", help="跳过确认"),
) -> None:
    """销毁服务"""
    cfg, db = _get_config()
    service = db.get_service(service_name)
    if not service:
        console.print(f"[red]服务 '{service_name}' 不存在[/]")
        raise typer.Exit(1)

    if not force:
        volume_info = ""
        if service.volumes:
            total = sum(v.size_bytes or 0 for v in service.volumes)
            volume_info = f"\n  {len(service.volumes)} 个数据卷 ({_format_bytes(total)})"

        console.print(Panel(
            f"[yellow]即将销毁服务: [bold]{service_name}[/][/]\n"
            f"  隐私等级: T{service.privacy_tier}\n"
            f"  端口: {len(service.ports)} 个{volume_info}",
            title="确认销毁",
            border_style="yellow",
        ))
        import questionary
        if not questionary.confirm("确认删除？", default=False).ask():
            console.print("已取消")
            raise typer.Exit()

    from privacybox.runtime.docker_backend import DockerBackend
    backend = DockerBackend(cfg)

    if not backend.is_available():
        console.print("[red]Docker 不可用[/]")
        raise typer.Exit(1)

    try:
        success = backend.destroy(service_name, keep_volumes=keep_data)
        if success:
            db.delete_service(service_name)
            console.print(f"[green][OK] 服务 '{service_name}' 已销毁[/]")
        else:
            console.print(f"[red][X] 销毁失败[/]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]销毁失败: {e}[/]")
        raise typer.Exit(1)


def _format_bytes(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
