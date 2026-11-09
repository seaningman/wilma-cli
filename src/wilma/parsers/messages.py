from __future__ import annotations

from ..models import Message
from .common import html_to_text, parse_dt


def parse_message_list(data: dict) -> list[Message]:
    msgs = [
        Message(str(m["Id"]), m.get("Subject", ""), m.get("Sender", ""), parse_dt(m.get("TimeStamp")),
                m.get("Folder", ""))
        for m in data.get("Messages", [])
    ]
    return sorted(msgs, key=lambda m: m.sent or parse_dt("1970-01-01"), reverse=True)


def parse_message(data: dict) -> Message:
    m = (data.get("messages") or [{}])[0]
    return Message(str(m.get("Id", "")), m.get("Subject", ""), m.get("Sender", ""), parse_dt(m.get("TimeStamp")),
                   m.get("Folder", ""), html_to_text(m.get("ContentHtml", "")), bool(m.get("AllowReply")))
