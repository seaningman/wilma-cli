"""Full-screen Textual app: calm home, tabbed screens, confirm-before-send."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Input, OptionList, Static, TabbedContent, TabPane, TextArea
from textual.widgets.option_list import Option

from .. import auth
from ..api import WilmaAPI
from ..client import WilmaClient, WilmaError
from ..render import day_label

MASCOT = " /\\_/\\\n( ^.^ )\n > ^ <"
TABS = ["home", "schedule", "homework", "messages", "news"]
JUMPS = {"home": "home", "h": "home", "sched": "schedule", "schedule": "schedule", "s": "schedule",
         "hw": "homework", "homework": "homework", "exams": "homework", "msg": "messages", "m": "messages",
         "messages": "messages", "news": "news", "n": "news"}


class ComposeScreen(ModalScreen[str | None]):
    """Write a reply, then confirm — nothing is sent until the second step."""

    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "review", "Review")]

    def __init__(self, subject: str):
        super().__init__()
        self.subject, self.stage, self.text = subject, "write", ""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="modal"):
            yield Static(f"[b]Reply[/]  [dim]{escape(self.subject)}[/]", id="m-title")
            yield TextArea(id="m-body")
            yield Static("[dim]ctrl+s review · esc cancel[/]", id="m-hint")

    def on_mount(self) -> None:
        self.query_one("#m-body", TextArea).focus()

    def action_review(self) -> None:
        if self.stage == "write":
            self.text = self.query_one("#m-body", TextArea).text.strip()
            if not self.text:
                return
            self.stage = "confirm"
            self.query_one("#m-body").display = False
            self.query_one("#m-title", Static).update(f"[b]Send this reply?[/]\n\n{escape(self.text)}")
            self.query_one("#m-hint", Static).update("[b #7fd4c1]enter[/] send · esc cancel")
        else:
            self.dismiss(self.text)

    def on_key(self, event) -> None:
        if self.stage == "confirm" and event.key == "enter":
            event.stop()
            self.dismiss(self.text)

    def action_cancel(self) -> None:
        self.dismiss(None)


HELP = """[b #7fd4c1]Keyboard[/]

[b]Tabs[/]        1-5 jump · tab / shift+tab next / prev
[b]Move[/]        j k or ↓ ↑ · g / G top / bottom · ctrl+d / ctrl+u page
[b]Panes[/]       l or → open reader · h or ← back to list · esc back
[b]Schedule[/]    h l or ← → change day · t today
[b]Jump[/]        /  then sched, hw, msg, news + enter
[b]Messages[/]    r reply (ctrl+s review, enter send, esc cancel)
[b]Other[/]       f5 refresh · ? this help · q quit · ctrl+p palette

[dim]esc to close[/]"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,q,question_mark,enter", "close", "Close")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="modal"):
            yield Static(HELP)

    def action_close(self) -> None:
        self.dismiss(None)


class WilmaApp(App):
    TITLE = "wilma"
    CSS_PATH = Path(__file__).with_name("wilma.tcss")
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("1", "tab('home')", "Home"),
        Binding("2", "tab('schedule')", "Schedule"),
        Binding("3", "tab('homework')", "Homework"),
        Binding("4", "tab('messages')", "Messages"),
        Binding("5", "tab('news')", "News"),
        Binding("left,h", "left", "◀", show=False, priority=True),
        Binding("right,l", "right", "▶", show=False, priority=True),
        Binding("j,down", "move(1)", "↓", show=False),
        Binding("k,up", "move(-1)", "↑", show=False),
        Binding("g", "move_edge(0)", "top", show=False),
        Binding("G", "move_edge(1)", "bottom", show=False),
        Binding("ctrl+d,pagedown", "page(1)", "pgdn", show=False),
        Binding("ctrl+u,pageup", "page(-1)", "pgup", show=False),
        Binding("t", "today", "Today", show=False),
        Binding("tab", "next_tab(1)", "Next tab", show=False, priority=True),
        Binding("shift+tab", "next_tab(-1)", "Prev tab", show=False, priority=True),
        Binding("escape", "blur", "Back", show=False),
        Binding("question_mark", "help", "Help"),
        Binding("r", "reply", "Reply"),
        Binding("f5", "refresh_all", "Refresh"),
        Binding("slash", "focus_cmd", "Jump", show=False),
    ]

    def __init__(self, api: WilmaAPI, username: str = ""):
        super().__init__()
        self.api, self.username = api, username
        self.day = date.today()
        self.lessons, self.messages, self.news = [], [], []
        self.current_msg_id: str | None = None
        self.current_subject = ""

    # ------------------------------------------------------------ layout
    def compose(self) -> ComposeResult:
        yield Static(f"{MASCOT}", id="banner")
        with TabbedContent(initial="home"):
            with TabPane("1 Home", id="home"):
                yield Input(placeholder="Jump to…  sched · hw · msg · news   (press / to focus)", id="cmd")
                yield Static("[dim]Loading…[/]", id="glance", classes="card")
            with TabPane("2 Schedule", id="schedule"):
                yield Static("", id="day-label")
                yield DataTable(id="sched-table", cursor_type="row", zebra_stripes=True)
            with TabPane("3 Homework & exams", id="homework"):
                yield DataTable(id="hw-table", cursor_type="row", zebra_stripes=True)
            with TabPane("4 Messages", id="messages"):
                with Horizontal():
                    yield OptionList(id="msg-list")
                    yield VerticalScroll(Static("[dim]Select a message.[/]", id="msg-body"), id="reader")
            with TabPane("5 News", id="news"):
                with Horizontal():
                    yield OptionList(id="news-list")
                    yield VerticalScroll(Static("[dim]Select an item.[/]", id="news-body"), id="reader2")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#banner", Static).update(f"[b #7fd4c1]{MASCOT}[/]  [dim]wilma[/]")
        self.query_one("#sched-table", DataTable).add_columns("Time", "Subject", "Room", "Teacher")
        self.query_one("#hw-table", DataTable).add_columns("When", "Subject", "What")
        self.query_one("#reader2").styles.width = "1fr"
        self.query_one("#reader2").styles.border = ("round", "#2e333d")
        self.query_one("#reader2").styles.padding = (1, 2)
        self.query_one("#news-list").styles.width = "42%"
        self.status("Loading…")
        self.load_all()

    def status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    # ------------------------------------------------------------ loading
    @work(thread=True, exclusive=True, group="load")
    def load_all(self) -> None:
        try:
            self.api.overview(refresh=True)
            lessons = self.api.schedule()
            exams, hw, appts = self.api.exams(), self.api.homework(), self.api.appointments()
            messages, news = self.api.messages(), self.api.news()
        except WilmaError as e:
            self.call_from_thread(self.status, f"[red]{escape(str(e))}[/]")
            return
        except Exception as e:  # network / parse problems show inline, never a traceback
            self.call_from_thread(self.status, f"[red]Could not load: {escape(str(e))}[/]")
            return
        self.call_from_thread(self.populate, lessons, exams, hw, appts, messages, news)

    def populate(self, lessons, exams, hw, appts, messages, news) -> None:
        self.lessons, self.messages, self.news = lessons, messages, news
        self.exams, self.hw, self.appts = exams, hw, appts
        self.render_schedule()
        self.render_homework()
        self.render_glance()
        ml = self.query_one("#msg-list", OptionList)
        ml.clear_options()
        ml.add_options([Option(self._msg_label(m), id=m.id) for m in messages[:100]])
        nl = self.query_one("#news-list", OptionList)
        nl.clear_options()
        nl.add_options([Option(escape(n.title), id=n.id) for n in news])
        self.status(f"[dim]Updated {datetime.now():%H:%M} · {len(messages)} messages[/]")

    @staticmethod
    def _msg_label(m) -> str:
        when = m.sent.strftime("%d.%m. %H:%M") if m.sent else ""
        return f"[b]{escape(m.subject)}[/]\n[dim]{escape(m.sender)} · {when}[/]"

    # ------------------------------------------------------------ renderers
    def render_glance(self) -> None:
        today = [l for l in self.lessons if l.day == date.today()]
        now = datetime.now().strftime("%H:%M")
        nxt = next((l for l in today if l.end > now), None)
        def row(label: str, value: str) -> str:
            return f"[b]{label:<20}[/]{value}"

        lines = [f"[b #7fd4c1]Good {'morning' if datetime.now().hour < 12 else 'day'}[/]  [dim]{escape(self.username)}[/]\n"]
        if nxt:
            lines.append(row("Next", f"{nxt.start}–{nxt.end}  {escape(nxt.subject)}  [dim]{escape(nxt.room)}[/]"))
        else:
            lines.append("[dim]No more lessons today.[/]")
        lines.append(row("Today", f"{len(today)} lessons"))
        soon = [e for e in self.exams if e.day and date.today() <= e.day <= date.today() + timedelta(days=7)]
        for e in soon[:4]:
            lines.append(f"[b #f0b27a]{'Exam':<20}[/]{day_label(e.day)}  {escape(e.subject)}")
        due = [h for h in self.hw if h.due and h.due <= date.today() + timedelta(days=2)]
        lines.append(row("Homework due soon", str(len(due))))
        lines.append(row("Latest message", escape(self.messages[0].subject) if self.messages else "—"))
        self.query_one("#glance", Static).update("\n".join(lines))

    def render_schedule(self) -> None:
        t = self.query_one("#sched-table", DataTable)
        t.clear()
        rows = [l for l in self.lessons if l.day == self.day]
        label = day_label(self.day) if abs((self.day - date.today()).days) <= 1 else self.day.strftime("%A %d.%m.")
        self.query_one("#day-label", Static).update(f"◀  {self.day:%A %d.%m.%Y}  ({label})  ▶")
        if not rows:
            t.add_row("", "[dim]Nothing scheduled — enjoy the quiet. 🐱[/]", "", "")
        for l in rows:
            t.add_row(f"{l.start}–{l.end}", f"[b]{escape(l.subject)}[/]", l.room, l.teacher)

    def render_homework(self) -> None:
        t = self.query_one("#hw-table", DataTable)
        t.clear()
        today = date.today()
        if not self.hw:
            t.add_row("", "[dim]No homework listed.[/]", "")
        for h in self.hw:
            t.add_row(day_label(h.due), f"[b]{escape(h.subject)}[/]", escape(h.text))
        t.add_row("", "", "")
        for e in self.exams:
            if e.day and e.day >= today:
                color = "red" if (e.day - today).days <= 2 else "yellow" if (e.day - today).days <= 7 else "white"
                t.add_row(f"[{color}]{day_label(e.day)}[/]", f"[b]Exam · {escape(e.subject)}[/]", escape(e.name))

    # ------------------------------------------------------------ events
    def on_input_submitted(self, event: Input.Submitted) -> None:
        key = JUMPS.get(event.value.strip().lower())
        event.input.value = ""
        self.set_focus(None)
        if key:
            self.action_tab(key)
        else:
            self.status("[yellow]Try: sched, hw, msg, news[/]")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id is None:
            return
        if event.option_list.id == "msg-list":
            self.open_message(event.option.id)
        elif event.option_list.id == "news-list":
            self.open_news(event.option.id)

    @work(thread=True, exclusive=True, group="msg")
    def open_message(self, id_: str) -> None:
        try:
            m = self.api.message(id_)
        except Exception as e:
            self.call_from_thread(self.query_one("#msg-body", Static).update, f"[red]{escape(str(e))}[/]")
            return
        self.current_msg_id, self.current_subject = id_, m.subject
        sent = f"{m.sent:%d.%m.%Y %H:%M}" if m.sent else ""
        text = f"[b #7fd4c1]{escape(m.subject)}[/]\n[dim]{escape(m.sender)} · {sent}[/]\n\n{escape(m.body)}"
        self.call_from_thread(self.query_one("#msg-body", Static).update, text)

    @work(thread=True, exclusive=True, group="news")
    def open_news(self, id_: str) -> None:
        try:
            n = self.api.news_item(id_)
        except Exception as e:
            self.call_from_thread(self.query_one("#news-body", Static).update, f"[red]{escape(str(e))}[/]")
            return
        self.call_from_thread(self.query_one("#news-body", Static).update, f"[b #7fd4c1]{escape(n.title)}[/]\n\n{escape(n.body)}")

    # ------------------------------------------------------------ actions
    def action_tab(self, name: str) -> None:
        if self._in_input():
            return
        self.query_one(TabbedContent).active = name
        self.focus_main()

    def action_focus_cmd(self) -> None:
        if self._in_input():
            return
        self.query_one(TabbedContent).active = "home"
        self.call_after_refresh(self.query_one("#cmd", Input).focus)

    NAV_ACTIONS = {"left", "right", "next_tab", "move", "move_edge", "page", "today", "tab", "focus_cmd",
                   "reply", "help", "refresh_all"}

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """Navigation keys must not steal keystrokes while typing or inside a dialog."""
        if action in self.NAV_ACTIONS and (self._in_input() or isinstance(self.screen, ModalScreen)):
            return False
        return True

    PANES = {"messages": ("#msg-list", "#reader"), "news": ("#news-list", "#reader2")}

    def _active(self) -> str:
        return self.query_one(TabbedContent).active

    def _in_input(self) -> bool:
        return isinstance(self.focused, (Input, TextArea))

    def action_left(self) -> None:
        if self._in_input():
            return
        tab = self._active()
        if tab == "schedule":
            self.day -= timedelta(days=1)
            self.render_schedule()
        elif tab in self.PANES:
            self.query_one(self.PANES[tab][0]).focus()

    def action_right(self) -> None:
        if self._in_input():
            return
        tab = self._active()
        if tab == "schedule":
            self.day += timedelta(days=1)
            self.render_schedule()
        elif tab in self.PANES:
            self.query_one(self.PANES[tab][1]).focus()

    def action_today(self) -> None:
        if self._active() == "schedule" and not self._in_input():
            self.day = date.today()
            self.render_schedule()

    def action_next_tab(self, step: int) -> None:
        if self._in_input():
            return
        i = (TABS.index(self._active()) + step) % len(TABS)
        self.action_tab(TABS[i])

    def action_move(self, step: int) -> None:
        w = self.focused
        if isinstance(w, (Input, TextArea)):
            return
        if isinstance(w, (OptionList, DataTable)):
            (w.action_cursor_down if step > 0 else w.action_cursor_up)()
        elif isinstance(w, VerticalScroll):
            (w.scroll_down if step > 0 else w.scroll_up)(animate=False)

    def action_move_edge(self, end: int) -> None:
        w = self.focused
        if isinstance(w, OptionList):
            (w.action_last if end else w.action_first)()
        elif isinstance(w, DataTable):
            w.move_cursor(row=w.row_count - 1 if end else 0)
        elif isinstance(w, VerticalScroll):
            (w.scroll_end if end else w.scroll_home)(animate=False)

    def action_page(self, step: int) -> None:
        w = self.focused
        if isinstance(w, (OptionList, DataTable)):
            (w.action_page_down if step > 0 else w.action_page_up)()
        elif isinstance(w, VerticalScroll):
            (w.scroll_page_down if step > 0 else w.scroll_page_up)(animate=False)

    def action_blur(self) -> None:
        if self._in_input():
            self.set_focus(None)
            self.focus_main()
        elif self._active() in self.PANES:
            self.query_one(self.PANES[self._active()][0]).focus()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def focus_main(self) -> None:
        """Put keyboard focus on the main widget of the active tab (never the input)."""
        tab = self._active()
        target = {"schedule": "#sched-table", "homework": "#hw-table"}.get(tab) or (
            self.PANES[tab][0] if tab in self.PANES else None)
        if target:
            self.query_one(target).focus()
        else:
            self.set_focus(None)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self.call_after_refresh(self.focus_main)

    def action_refresh_all(self) -> None:
        self.status("Refreshing…")
        self.load_all()

    def action_reply(self) -> None:
        if self._in_input() or self._active() != "messages" or not self.current_msg_id:
            return
        msg_id = self.current_msg_id

        def done(text: str | None) -> None:
            if text:
                self.send_reply(msg_id, text)

        self.push_screen(ComposeScreen(self.current_subject), done)

    @work(thread=True, group="send")
    def send_reply(self, msg_id: str, text: str) -> None:
        try:
            self.api.send_reply(msg_id, text)
            self.call_from_thread(self.status, "[green]✓ Reply sent.[/]")
        except Exception as e:
            self.call_from_thread(self.status, f"[red]Not sent: {escape(str(e))}[/]")


def run() -> None:
    cfg = auth.load_config()
    if not cfg.ready:
        print("Not set up yet. Run `wilma login` first.")
        raise SystemExit(1)
    client = WilmaClient(cfg.base_url)
    try:
        client.ensure_login(cfg.username, auth.get_password(cfg.username))
    except WilmaError as e:
        print(e)
        raise SystemExit(1)
    WilmaApp(WilmaAPI(client), cfg.username).run(mouse=False)
