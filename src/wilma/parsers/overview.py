"""Parse `/overview?format=json` into schedule, exams, homework, appointments."""
from __future__ import annotations

from datetime import date

from ..models import Appointment, Exam, Homework, Lesson
from .common import parse_date, parse_dt


def parse_schedule(data: dict) -> list[Lesson]:
    names = {g.get("Id"): g for g in data.get("Groups", [])}
    lessons: list[Lesson] = []
    for item in data.get("Schedule", []):
        groups = item.get("Groups") or []
        full = [names.get(g.get("Id"), {}) for g in groups]
        g = groups[0] if groups else {}
        subject = (full[0].get("CourseName") if full else None) or g.get("Caption") or g.get("FullCaption") or "Lesson"
        teachers = {t.get("TeacherName", "") for gr in [*groups, *full] for t in gr.get("Teachers", [])}
        for d in item.get("DateArray", []):
            day = parse_date(d)
            if day:
                lessons.append(
                    Lesson(day, item.get("Start", ""), item.get("End", ""), subject,
                           item.get("Class", "") or g.get("Class", ""), ", ".join(sorted(t for t in teachers if t)))
                )
    return sorted(lessons, key=lambda x: (x.day, x.start))


def parse_exams(data: dict) -> list[Exam]:
    exams = []
    for e in data.get("Exams", []):
        exams.append(Exam(parse_date(e.get("Date")), e.get("CourseTitle") or e.get("Course", ""),
                          e.get("Name", ""), e.get("TimeStart", ""), e.get("TimeEnd", ""), e.get("Grade", "")))
    return sorted(exams, key=lambda x: x.day or date.max)


def parse_homework(data: dict) -> list[Homework]:
    """Homework lives under Groups[].Homework; field names are matched defensively."""
    out = []
    for g in data.get("Groups", []):
        subject = g.get("CourseName") or g.get("Caption") or g.get("Name", "")
        for h in g.get("Homework", []) or []:
            text = h.get("Homework") or h.get("Text") or h.get("Info") or h.get("Description") or ""
            out.append(Homework(parse_date(h.get("Date") or h.get("DueDate") or h.get("Day")), subject, str(text)))
    return sorted(out, key=lambda x: x.due or date.max)


def parse_appointments(data: dict) -> list[Appointment]:
    return [
        Appointment(a.get("Subject", ""), parse_dt(a.get("Start")), parse_dt(a.get("End")),
                    a.get("Sender", ""), a.get("Info", ""))
        for a in data.get("Appointments", [])
    ]
