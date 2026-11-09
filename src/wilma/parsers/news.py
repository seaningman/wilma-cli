from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..models import Bulletin
from .common import html_to_text, parse_date


def parse_news_list(html: str) -> list[Bulletin]:
    """List page: `h2` date headings, each followed by `div.well` blocks (h3 title + link)."""
    soup = BeautifulSoup(html, "lxml")
    out: list[Bulletin] = []
    heading = ""
    for el in soup.select(".panel-body > h2, .panel-body > div.well"):
        if el.name == "h2":
            heading = el.get_text(strip=True)
            continue
        a = el.find("a", href=re.compile(r"^/news/\d+"))
        h3 = el.find("h3")
        if not a or not h3:
            continue
        d = parse_date(heading)
        out.append(Bulletin(re.search(r"\d+", a["href"]).group(), h3.get_text(" ", strip=True),
                            datetime(d.year, d.month, d.day) if d else None))
    return out


def parse_news_item(html: str, id_: str = "") -> Bulletin:
    soup = BeautifulSoup(html, "lxml")
    title = soup.select_one("main#main-content .panel-body h2")
    body = soup.select_one("#news-content")
    return Bulletin(id_, title.get_text(" ", strip=True) if title else "", None,
                    html_to_text(str(body)) if body else "")
