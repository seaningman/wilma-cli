"""Shared formatting helpers (rich tables + JSON output)."""
from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime

from rich.console import Console
from rich.table import Table

console = Console()


def _default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    raise TypeError(type(o))


def dump_json(items) -> None:
    print(json.dumps(items, default=_default, ensure_ascii=False, indent=2))


def day_label(d: date | None) -> str:
    if d is None:
        return "—"
    delta = (d - date.today()).days
    names = {0: "Today", 1: "Tomorrow", -1: "Yesterday"}
    return names.get(delta, d.strftime("%a %d.%m."))


def table(title: str, cols: list[str]) -> Table:
    t = Table(title=title, title_justify="left", border_style="grey50", header_style="bold cyan", box=None, pad_edge=False)
    for c in cols:
        t.add_column(c, overflow="fold")
    return t
