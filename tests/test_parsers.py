"""Parsers against synthetic payloads shaped like real Wilma responses."""
from datetime import date

from wilma.parsers import messages as pm
from wilma.parsers import news as pn
from wilma.parsers import overview as po

OVERVIEW = {
    "Schedule": [{"Day": 1, "Start": "08:25", "End": "09:40", "Class": "A1", "DateArray": ["2026-11-09", "2026-11-16"],
                  "Groups": [{"Id": 7, "Caption": "MA01.1", "Teachers": []}]}],
    "Groups": [{"Id": 7, "CourseName": "Mathematics", "Teachers": [{"TeacherId": 1, "TeacherName": "Ms Example"}],
                "Homework": [{"Date": "2026-11-10", "Homework": "Read ch. 3"}]}],
    "Exams": [{"Date": "2026-11-20", "CourseTitle": "Biology", "Name": "Test", "TimeStart": "10:00", "TimeEnd": "11:00"},
              {"Date": "2026-08-01", "CourseTitle": "Old", "Name": ""}],
    "Appointments": [{"Subject": "Evening", "Start": "2026-11-06 09:15", "End": "2026-11-06 10:00", "Sender": "School", "Info": ""}],
}


def test_schedule_expands_dates_and_uses_course_name():
    lessons = po.parse_schedule(OVERVIEW)
    assert [l.day for l in lessons] == [date(2026, 11, 9), date(2026, 11, 16)]
    assert lessons[0].subject == "Mathematics" and lessons[0].teacher == "Ms Example" and lessons[0].room == "A1"


def test_exams_sorted_and_homework_parsed():
    assert [e.subject for e in po.parse_exams(OVERVIEW)] == ["Old", "Biology"]
    hw = po.parse_homework(OVERVIEW)
    assert hw[0].subject == "Mathematics" and hw[0].due == date(2026, 11, 10) and hw[0].text == "Read ch. 3"
    assert po.parse_appointments(OVERVIEW)[0].start.hour == 9


def test_messages():
    lst = pm.parse_message_list({"Messages": [
        {"Id": 1, "Subject": "Old", "TimeStamp": "2026-11-01 10:00:00", "Sender": "A"},
        {"Id": 2, "Subject": "New", "TimeStamp": "2026-11-05 10:00:00", "Sender": "B"}]})
    assert [m.id for m in lst] == ["2", "1"]
    m = pm.parse_message({"messages": [{"Id": 2, "Subject": "New", "Sender": "B", "TimeStamp": "2026-11-05 10:00",
                                        "ContentHtml": "<p>Hello</p><p>World<br>again</p>", "AllowReply": True}]})
    assert m.body == "Hello\nWorld\nagain" and m.can_reply


NEWS_LIST = """<div class="panel-body"><h2>09.11.2026</h2>
<div class="margin-bottom well"><h3>Title A</h3><span><a href="/news/11">Read</a></span></div>
<h2>Eilen</h2><div class="margin-bottom well"><h3>Title B</h3><span><a href="/news/12">Read</a></span></div></div>"""
NEWS_ITEM = """<main id="main-content"><div class="panel"><div class="panel-body"><h2>Title A</h2>
<div id="news-content"><p>First</p><p>Second <a href="https://x.example">link</a></p></div></div></div></main>"""


def test_news():
    items = pn.parse_news_list(NEWS_LIST)
    assert [(n.id, n.title) for n in items] == [("11", "Title A"), ("12", "Title B")]
    assert items[0].published.day == 9 and items[1].published is None
    n = pn.parse_news_item(NEWS_ITEM, "11")
    assert n.title == "Title A" and "First" in n.body and "Second" in n.body
