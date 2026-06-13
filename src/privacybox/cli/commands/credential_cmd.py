from __future__ import annotations

import typer
from rich.table import Table
from rich.panel import Panel

from privacybox.cli.app import _get_config, app, console

credential_app = typer.Typer(help="管理 API 凭据")
app.add_typer(credential_app, name="credential")


@credential_app.callback(invoke_without_command=True)
def credential_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        list_credentials()


def list_credentials() -> None:
    cfg, db = _get_config()
    records = db.list_credentials(active_only=True)

    if not records:
        console.print("[yellow]没有凭据[/]")
        return

    table = Table(title="凭据列表", border_style="cyan")
    table.add_column("ID (前8位)", style="bold")
    table.add_column("提供商")
    table.add_column("存储后端")
    table.add_column("创建时间")
    table.add_column("来源")

    for r in records:
        origin = r.migrated_from or "原生"
        table.add_row(
            r.id[:8],
            r.provider,
            r.backend,
            r.created_at.strftime("%Y-%m-%d"),
            origin,
        )

    console.print(table)


@credential_app.command()
def list() -> None:
    list_credentials()


@credential_app.command()
def add(
    provider: str = typer.Argument(..., help="提供商: openai|claude|ollama|ssh"),
) -> None:
    import questionary
    cfg, db = _get_config()

    key = questionary.password(f"请输入 {provider} API Key：").ask()
    if not key:
        console.print("[red]Key 不能为空[/]")
        raise typer.Exit(1)

    label = questionary.text("标签（可选）：", default=provider).ask() or provider

    backend_name = cfg.credentials.backend

    from privacybox.utils.types import CredentialRecord
    from datetime import datetime

    record = CredentialRecord(
        provider=provider,
        backend=backend_name,
        label=label,
    )

    from privacybox.credentials.store import CredentialStore
    store = CredentialStore(cfg, db)
    success = store.store(record, key)

    if success:
        console.print(f"[green][OK] 凭据已保存 ({backend_name})[/]")
    else:
        console.print(f"[red][X] 保存失败[/]")
        raise typer.Exit(1)


@credential_app.command()
def remove(
    record_id: str = typer.Argument(..., help="凭据 ID（前 8 位即可）"),
) -> None:
    cfg, db = _get_config()
    records = db.list_credentials(active_only=True)
    matches = [r for r in records if r.id.startswith(record_id)]

    if not matches:
        console.print(f"[red]未找到匹配的凭据[/]")
        raise typer.Exit(1)

    record = matches[0]
    from privacybox.credentials.store import CredentialStore
    store = CredentialStore(cfg, db)

    if store.delete(record.id):
        console.print(f"[green][OK] 凭据 '{record.label}' 已删除[/]")
    else:
        console.print("[red][X] 删除失败[/]")
        raise typer.Exit(1)


@credential_app.command()
def migrate(
    to_backend: str = typer.Argument(..., help="目标后端: file|keychain"),
) -> None:
    cfg, db = _get_config()
    from privacybox.credentials.store import CredentialStore
    store = CredentialStore(cfg, db)

    console.print(f"[cyan]正在迁移凭据到 '{to_backend}'...[/]")
    result = store.migrate_all(to_backend)

    if result:
        console.print(f"[green][OK] 凭据已迁移到 '{to_backend}'[/]")
    else:
        console.print("[red][X] 迁移失败[/]")
        raise typer.Exit(1)


@credential_app.command()
def verify() -> None:
    cfg, db = _get_config()
    from privacybox.credentials.store import CredentialStore
    store = CredentialStore(cfg, db)

    results = store.verify_all()
    all_ok = True

    for rec_id, ok in results.items():
        status = "[green][OK] 正常[/]" if ok else "[red][X] 异常[/]"
        console.print(f"  {rec_id[:8]}: {status}")
        if not ok:
            all_ok = False

    if all_ok:
        console.print("[green]所有凭据正常[/]")
    else:
        console.print("[yellow]部分凭据异常，建议重新添加[/]")
