import httpx
import pytest
import respx

from wilma import auth
from wilma.client import LoginError, WilmaClient

BASE = "https://school.example.fi"


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(auth, "SESSION_FILE", tmp_path / "session.json")


@respx.mock
def test_login_ok():
    respx.get(f"{BASE}/index_json").mock(return_value=httpx.Response(200, json={"SessionID": "abc"}))
    respx.post(f"{BASE}/login").mock(
        return_value=httpx.Response(200, headers={"set-cookie": "Wilma2SID=xyz; Path=/"}, text="ok")
    )
    c = WilmaClient(BASE)
    c.login("u", "p")
    assert c.cookies()["Wilma2SID"] == "xyz"
    assert auth.load_session()["Wilma2SID"] == "xyz"


@respx.mock
def test_login_failed():
    respx.get(f"{BASE}/index_json").mock(return_value=httpx.Response(200, json={"SessionID": "abc"}))
    respx.post(f"{BASE}/login").mock(return_value=httpx.Response(200, text="nope"))
    with pytest.raises(LoginError):
        WilmaClient(BASE).login("u", "bad")
