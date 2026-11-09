from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Message:
    id: str
    subject: str
    sender: str
    sent: datetime | None = None
    folder: str = ""
    body: str = ""
    can_reply: bool = False


@dataclass
class Lesson:
    day: date
    start: str
    end: str
    subject: str
    room: str = ""
    teacher: str = ""


@dataclass
class Homework:
    due: date | None
    subject: str
    text: str


@dataclass
class Exam:
    day: date | None
    subject: str
    name: str = ""
    start: str = ""
    end: str = ""
    grade: str = ""


@dataclass
class Appointment:
    subject: str
    start: datetime | None
    end: datetime | None
    sender: str = ""
    info: str = ""


@dataclass
class Bulletin:
    id: str
    title: str
    published: datetime | None = None
    body: str = ""
    tags: list[str] = field(default_factory=list)
