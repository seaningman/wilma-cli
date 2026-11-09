import pytest

from tests.fakes import FakeAPI
from wilma.tui.app import ComposeScreen, WilmaApp


@pytest.mark.asyncio
async def test_navigation_and_reply_confirm():
    FakeAPI.sent = None
    app = WilmaApp(FakeAPI(), "tester")
    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause(0.5)
        await pilot.press("4")
        await pilot.pause(0.3)
        ml = app.query_one("#msg-list")
        ml.focus()
        await pilot.press("down")
        await pilot.pause(0.5)
        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, ComposeScreen)
        app.screen.query_one("#m-body").text = "Thanks!"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert FakeAPI.sent is None  # nothing sent before confirming
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert FakeAPI.sent == ("1", "Thanks!")


@pytest.mark.asyncio
async def test_screens_render_and_day_shift():
    app = WilmaApp(FakeAPI(), "tester")
    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause(0.5)
        await pilot.press("2")
        assert app.query_one("#sched-table").row_count == 3
        await pilot.press("right")
        assert app.query_one("#sched-table").row_count == 1  # empty-state row
        await pilot.press("3")
        assert app.query_one("#hw-table").row_count >= 3
