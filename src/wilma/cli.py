from __future__ import annotations

import getpass

import httpx
import typer
from rich.console import Console

from datetime import date, timedelta

from . import __version__, auth
from .api import WilmaAPI
from .render import console as rc, day_label, dump_json, table
from .client import LoginError, WilmaClient, WilmaError

app = typer.Typer(help="A cozy terminal app for Wilma.", no_args_is_help=False, add_completion=False)
console = Console()


def _client() -> WilmaClient:
    cfg = auth.load_config()
    if not cfg.ready:
        console.print("[yellow]Not set up yet.[/] Run [bold]wilma login[/].")
        raise typer.Exit(1)
    client = WilmaClient(cfg.base_url)
    try:
        client.ensure_login(cfg.username, auth.get_password(cfg.username))
    except WilmaError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    return client


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, version: bool = typer.Option(False, "--version")) -> None:
    if version:
        console.print(f"wilma {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        from .tui.app import run

        run()


@app.command()
def login(
    url: str = typer.Option(None, "--url", help="Wilma base URL"),
    username: str = typer.Option(None, "--username", "-u"),
) -> None:
    """Log in and save the session (password goes to the system keyring)."""
    cfg = auth.load_config()
    base = url or typer.prompt("Wilma URL (e.g. https://school.inschool.fi)", default=cfg.base_url or None)
    user = username or typer.prompt("Username", default=cfg.username or None)
    password = auth.os.environ.get("WILMA_PASSWORD") or getpass.getpass("Password: ")
    client = WilmaClient(base)
    try:
        client.login(user, password)
    except WilmaError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    auth.save_config(auth.Config(client.base_url, user))
    stored = auth.store_password(user, password)
    console.print("[green]✓ Logged in.[/]" + ("" if stored else " [yellow](keyring unavailable; password not saved)[/]"))


@app.command()
def logout() -> None:
    """Forget the saved session and password."""
    cfg = auth.load_config()
    auth.clear_session()
    if cfg.username:
        auth.delete_password(cfg.username)
    console.print("Logged out.")


@app.command()
def whoami() -> None:
    """Show the logged-in account."""
    cfg = auth.load_config()
    client = _client()
    console.print(f"[bold]{cfg.username}[/] @ {cfg.base_url}")
    client.close()


@app.command()
def doctor() -> None:
    """Read-only diagnostic of config, connectivity and login."""
    ok = lambda m: console.print(f"[green]✓[/] {m}")  # noqa: E731
    bad = lambda m: console.print(f"[red]✗[/] {m}")  # noqa: E731
    cfg = auth.load_config()
    (ok if cfg.ready else bad)(f"config: {auth.CONFIG_FILE}" + ("" if cfg.ready else " (run `wilma login`)"))
    if not cfg.ready:
        raise typer.Exit(1)
    pw = auth.get_password(cfg.username)
    (ok if pw else bad)("password available (keyring or WILMA_PASSWORD)")
    client = WilmaClient(cfg.base_url)
    try:
        r = httpx.get(f"{client.base_url}/index_json", timeout=15)
        ok(f"reachable: {client.base_url} (HTTP {r.status_code})")
    except httpx.HTTPError as e:
        bad(f"unreachable: {e}")
        raise typer.Exit(1)
    try:
        client.ensure_login(cfg.username, pw)
        ok("logged in")
    except LoginError as e:
        bad(str(e))
        raise typer.Exit(1)
    finally:
        client.close()


# ---------------------------------------------------------------- helpers
JSON = typer.Option(False, "--json", help="Machine-readable output")


def _api() -> WilmaAPI:
    return WilmaAPI(_client())


# --------------------------------------------------------------- schedule
@app.command()
def schedule(
    week: bool = typer.Option(False, "--week", help="Show the whole week"),
    day: str = typer.Option(None, "--day", help="YYYY-MM-DD"),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    """Show today's lessons (or --day / --week)."""
    from .parsers.common import parse_date

    lessons = _api().schedule()
    target = parse_date(day) if day else date.today()
    if week:
        start = target - timedelta(days=target.weekday())
        lessons = [l for l in lessons if start <= l.day < start + timedelta(days=7)]
    else:
        lessons = [l for l in lessons if l.day == target]
    if json_:
        return dump_json(lessons)
    if not lessons:
        rc.print("[dim]No lessons — enjoy the quiet. 🐱[/]")
        return
    t = table("Schedule", ["Day", "Time", "Subject", "Room", "Teacher"])
    for l in lessons:
        t.add_row(day_label(l.day), f"{l.start}–{l.end}", f"[bold]{l.subject}[/]", l.room, l.teacher)
    rc.print(t)


@app.command()
def homework(json_: bool = typer.Option(False, "--json")) -> None:
    """Upcoming homework."""
    items = _api().homework()
    if json_:
        return dump_json(items)
    if not items:
        rc.print("[dim]No homework listed. 🐱[/]")
        return
    t = table("Homework", ["Due", "Subject", "Task"])
    for h in items:
        t.add_row(day_label(h.due), f"[bold]{h.subject}[/]", h.text)
    rc.print(t)


@app.command()
def exams(all_: bool = typer.Option(False, "--all", help="Include past exams"), json_: bool = typer.Option(False, "--json")) -> None:
    """Upcoming exams."""
    items = [e for e in _api().exams() if all_ or (e.day and e.day >= date.today())]
    if json_:
        return dump_json(items)
    if not items:
        rc.print("[dim]No upcoming exams. 🐱[/]")
        return
    t = table("Exams", ["Date", "Time", "Course", "Name", "Grade"])
    for e in items:
        t.add_row(day_label(e.day), e.start, f"[bold]{e.subject}[/]", e.name, e.grade)
    rc.print(t)


# ------------------------------------------------------------------- news
news_app = typer.Typer(help="School announcements.", no_args_is_help=True)
app.add_typer(news_app, name="news")


@news_app.command("list")
def news_list(json_: bool = typer.Option(False, "--json")) -> None:
    items = _api().news()
    if json_:
        return dump_json(items)
    t = table("News", ["ID", "Date", "Title"])
    for n in items:
        t.add_row(n.id, n.published.strftime("%d.%m.") if n.published else "", n.title)
    rc.print(t)


@news_app.command("read")
def news_read(id: str, json_: bool = typer.Option(False, "--json")) -> None:
    n = _api().news_item(id)
    if json_:
        return dump_json(n)
    rc.print(f"[bold]{n.title}[/]\n")
    rc.print(n.body)


# --------------------------------------------------------------- messages
msg_app = typer.Typer(help="Read and send messages.", no_args_is_help=True)
app.add_typer(msg_app, name="messages")


@msg_app.command("list")
def messages_list(limit: int = 20, json_: bool = typer.Option(False, "--json")) -> None:
    items = _api().messages()[:limit]
    if json_:
        return dump_json(items)
    t = table("Messages", ["ID", "Sent", "From", "Subject"])
    for m in items:
        t.add_row(m.id, m.sent.strftime("%d.%m. %H:%M") if m.sent else "", m.sender, f"[bold]{m.subject}[/]")
    rc.print(t)


@msg_app.command("read")
def messages_read(id: str, json_: bool = typer.Option(False, "--json")) -> None:
    """Read a message (this also marks it read in Wilma)."""
    m = _api().message(id)
    if json_:
        return dump_json(m)
    rc.print(f"[bold]{m.subject}[/]\n[dim]{m.sender} · {m.sent:%d.%m.%Y %H:%M}[/]\n" if m.sent else f"[bold]{m.subject}[/]\n")
    rc.print(m.body)


@msg_app.command("mark-read")
def messages_mark_read(id: str) -> None:
    _api().mark_read(id)
    rc.print("[green]✓ Marked read.[/]")


def _confirm_send(preview: str, yes: bool) -> None:
    rc.print(preview)
    if not yes and not typer.confirm("Send this message?", default=False):
        rc.print("[yellow]Cancelled — nothing was sent.[/]")
        raise typer.Exit(1)


@msg_app.command("reply")
def messages_reply(id: str, body: str = typer.Option(..., "--body", "-b"), yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Reply to a message (previews and asks before sending)."""
    api = _api()
    fields = api.prepare_reply(id)
    _confirm_send(f"[bold]Re:[/] {fields.get('Subject', '')}\n\n{body}\n", yes)
    api.send_reply(id, body)
    rc.print("[green]✓ Sent.[/]")


@msg_app.command("send")
def messages_send(
    to_teacher: list[str] = typer.Option(..., "--to-teacher", help="Teacher id (see `wilma teachers`); repeatable"),
    subject: str = typer.Option(..., "--subject", "-s"),
    body: str = typer.Option(..., "--body", "-b"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Send a new message (experimental — prefer `reply` until verified)."""
    _confirm_send(f"[bold]To teacher ids:[/] {', '.join(to_teacher)}\n[bold]{subject}[/]\n\n{body}\n", yes)
    _api().send_new(subject, body, to_teacher)
    rc.print("[green]✓ Sent.[/]")


@app.command()
def teachers(json_: bool = typer.Option(False, "--json")) -> None:
    """List your teachers with their ids (for `messages send`)."""
    seen = {}
    for g in _api().overview().get("Groups", []):
        for t in g.get("Teachers", []):
            seen[t["TeacherId"]] = t["TeacherName"]
    if json_:
        return dump_json([{"id": k, "name": v} for k, v in seen.items()])
    t = table("Teachers", ["ID", "Name"])
    for k, v in seen.items():
        t.add_row(str(k), v)
    rc.print(t)
