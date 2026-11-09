from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup


def parse_date(v: object) -> date | None:
    if not v:
        return None
    s = str(v).strip()
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", s):
        return date(*map(int, m.groups()))
    if m := re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s):
        d, mo, y = map(int, m.groups())
        return date(y, mo, d)
    return None


def parse_dt(v: object) -> datetime | None:
    if not v:
        return None
    s = str(v).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    d = parse_date(s)
    return datetime(d.year, d.month, d.day) if d else None


def html_to_text(html: str) -> str:
    """Flatten Wilma's HTML snippets into readable plain text."""
    soup = BeautifulSoup(html or "", "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all(["p", "div", "li", "h1", "h2", "h3"]):
        p.append("\n")
    text = soup.get_text()
    return re.sub(r"\n{3,}", "\n\n", text).strip()
