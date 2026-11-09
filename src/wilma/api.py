"""High-level Wilma operations used by both the CLI and the TUI."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .client import WilmaClient, WilmaError
from .models import Appointment, Bulletin, Exam, Homework, Lesson, Message
from .parsers import messages as pm
from .parsers import news as pn
from .parsers import overview as po


class WilmaAPI:
    def __init__(self, client: WilmaClient):
        self.c = client
        self._overview: dict | None = None

    def overview(self, refresh: bool = False) -> dict:
        if self._overview is None or refresh:
            self._overview = self.c.get_json("/overview")
        return self._overview

    def schedule(self) -> list[Lesson]:
        return po.parse_schedule(self.overview())

    def exams(self) -> list[Exam]:
        return po.parse_exams(self.overview())

    def homework(self) -> list[Homework]:
        return po.parse_homework(self.overview())

    def appointments(self) -> list[Appointment]:
        return po.parse_appointments(self.overview())

    def messages(self) -> list[Message]:
        return pm.parse_message_list(self.c.get_json("/messages/list"))

    def message(self, id_: str) -> Message:
        return pm.parse_message(self.c.get_json(f"/messages/{id_}"))

    def news(self) -> list[Bulletin]:
        return pn.parse_news_list(self.c.get_html("/news"))

    def news_item(self, id_: str) -> Bulletin:
        return pn.parse_news_item(self.c.get_html(f"/news/{id_}"), id_)

    # -- writes ------------------------------------------------------------
    @staticmethod
    def _form_fields(html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        form = next((f for f in soup.find_all("form") if f.get("action", "").startswith("/messages/compose")), None)
        if form is None:
            raise WilmaError("Compose form not found — Wilma's page layout may have changed.")
        fields: dict[str, str] = {}
        for i in form.find_all(["input", "textarea"]):
            name, typ = i.get("name"), i.get("type")
            if not name or typ in ("submit", "button") or (typ == "checkbox" and not i.has_attr("checked")):
                continue
            fields[name] = i.text if i.name == "textarea" else (i.get("value") or "")
        return fields

    def prepare_reply(self, id_: str, forward: bool = False) -> dict[str, str]:
        """Fetch the prefilled reply form (subject + recipients) without sending anything."""
        html = self.c.get_html("/messages/compose", replyid=id_, **({"forward": ""} if forward else {}))
        return self._form_fields(html)

    def send_reply(self, id_: str, body: str) -> None:
        fields = self.prepare_reply(id_)
        fields["BodyText"] = body
        fields["addsavebtn"] = "Lähetä"
        r = self.c.post_form("/messages/compose", fields)
        if "compose" in str(r.url) and "replyid" in str(r.url):
            raise WilmaError("Wilma did not accept the reply.")

    def send_new(self, subject: str, body: str, teacher_ids: list[str]) -> None:
        """Experimental: recipients are posted as `r_teacher` ids (as the picker does)."""
        fields = self._form_fields(self.c.get_html("/messages/compose"))
        fields.update({"Subject": subject, "BodyText": body, "addsavebtn": "Lähetä"})
        data: list[tuple[str, str]] = list(fields.items()) + [("r_teacher", t) for t in teacher_ids]
        r = self.c._http.post(self.c.slug + "/messages/compose", data=data)
        r.raise_for_status()

    def mark_read(self, id_: str) -> None:
        """Opening a message marks it read in Wilma."""
        self.c.get_html(f"/messages/{id_}")
