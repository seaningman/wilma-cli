"""Synthetic data only — no real student information."""
from datetime import date, datetime, timedelta

from wilma.models import Appointment, Bulletin, Exam, Homework, Lesson, Message

T = date.today()


class FakeAPI:
    def overview(self, refresh=False):
        return {}

    def schedule(self):
        return [Lesson(T, "08:25", "09:40", "Mathematics", "A101", "Ms Example"),
                Lesson(T, "09:55", "11:10", "History", "B204", "Mr Sample"),
                Lesson(T, "23:00", "23:59", "Late Lab", "C3", "Dr Test")]

    def exams(self):
        return [Exam(T + timedelta(days=2), "Biology", "Chapter 4 test", "10:00", "11:00")]

    def homework(self):
        return [Homework(T + timedelta(days=1), "Mathematics", "Exercises 12–15")]

    def appointments(self):
        return [Appointment("Parent evening", datetime.now(), None)]

    def messages(self):
        return [Message("1", "Field trip on Friday", "Example Teacher", datetime.now(), "inbox"),
                Message("2", "Welcome back", "Principal", datetime.now() - timedelta(days=1), "inbox")]

    def message(self, id_):
        return Message(id_, "Field trip on Friday", "Example Teacher", datetime.now(), "inbox",
                       "Please bring a packed lunch.\nWe leave at 9.", True)

    def news(self):
        return [Bulletin("10", "Updated privacy notice", datetime.now())]

    def news_item(self, id_):
        return Bulletin(id_, "Updated privacy notice", None, "The privacy notice was updated.")

    sent = None

    def send_reply(self, id_, text):
        FakeAPI.sent = (id_, text)
