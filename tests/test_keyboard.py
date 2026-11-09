"""Everything must be reachable without a mouse."""
import pytest

from tests.fakes import FakeAPI
from wilma.tui.app import ComposeScreen, HelpScreen, WilmaApp


@pytest.mark.asyncio
async def test_keyboard_only_flow():
    FakeAPI.sent = None
    app = WilmaApp(FakeAPI(), "tester")
    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause(0.5)
        # tab cycling and focus lands on the main widget
        await pilot.press("tab")
        assert app._active() == "schedule" and app.focused.id == "sched-table"
        await pilot.press("l")                     # next day
        assert app.query_one("#sched-table").row_count == 1
        await pilot.press("t")                     # back to today
        assert app.query_one("#sched-table").row_count == 3
        await pilot.press("shift+tab", "shift+tab")  # wraps to news
        assert app._active() == "news"
        await pilot.press("4")
        assert app.focused.id == "msg-list"
        await pilot.press("j")
        await pilot.pause(0.4)
        await pilot.press("l")                     # into reader
        assert app.focused.id == "reader"
        await pilot.press("j", "G", "g")           # scroll keys don't crash
        await pilot.press("h")                     # back to list
        assert app.focused.id == "msg-list"
        await pilot.press("r")
        assert isinstance(app.screen, ComposeScreen)
        await pilot.press("h", "i", "tab")         # typing, incl. nav keys, goes to the text box
        assert app.screen.query_one("#m-body").text.startswith("hi")
        await pilot.press("ctrl+s", "enter")
        await pilot.pause(0.4)
        assert FakeAPI.sent[1].startswith("hi")


@pytest.mark.asyncio
async def test_jump_box_and_help():
    app = WilmaApp(FakeAPI(), "tester")
    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause(0.5)
        await pilot.press("slash")
        await pilot.pause(0.1)
        await pilot.press("h", "w", "enter")       # 'h' and 'w' typed, not treated as nav
        await pilot.pause(0.2)
        assert app._active() == "homework"
        await pilot.press("question_mark")
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        assert not isinstance(app.screen, HelpScreen)
