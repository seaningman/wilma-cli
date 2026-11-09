"""HTTP client for Wilma's cookie-session web interface.

Wilma has no official public API. The flow below follows the web UI's JSON
views and must be validated against a real instance (see `wilma doctor`).
"""
from __future__ import annotations

from typing import Any

import httpx

from . import auth


class WilmaError(Exception):
    pass


class LoginError(WilmaError):
    pass


class WilmaClient:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None):
        self.base_url = auth.normalize_base_url(base_url)
        self._http = httpx.Client(
            base_url=self.base_url,
            follow_redirects=True,
            timeout=15,
            headers={"User-Agent": "wilma-cli"},
            transport=transport,
        )
        self.formkey: str | None = None
        self.slug: str = ""  # "/!123456" prefix for guardian accounts

    # -- session -----------------------------------------------------------
    def restore(self, cookies: dict[str, str]) -> None:
        for k, v in cookies.items():
            self._http.cookies.set(k, v)

    def cookies(self) -> dict[str, str]:
        return dict(self._http.cookies.items())

    def login(self, username: str, password: str) -> None:
        try:
            pre = self._http.get("/index_json")
            pre.raise_for_status()
            session_id = pre.json().get("SessionID", "")
            resp = self._http.post(
                "/login",
                data={
                    "Login": username,
                    "Password": password,
                    "SESSIONID": session_id,
                    "CompleteJson": "",
                    "Submit": "Submit",
                },
            )
        except (httpx.HTTPError, ValueError) as e:
            raise WilmaError(f"Could not reach Wilma at {self.base_url}: {e}") from e
        if "Wilma2SID" not in self._http.cookies or "loginfailed" in str(resp.url).lower():
            raise LoginError("Login failed — check username and password.")
        auth.save_session(self.cookies())

    def ensure_login(self, username: str, password: str | None) -> None:
        """Reuse the cached session if still valid, otherwise log in again."""
        self.restore(auth.load_session())
        if self._http.cookies and self.is_authenticated():
            return
        if not password:
            raise LoginError("Session expired and no saved password. Run `wilma login`.")
        self.login(username, password)

    def is_authenticated(self) -> bool:
        try:
            r = self._http.get("/")
        except httpx.HTTPError:
            return False
        return r.status_code == 200 and 'id="logout-form"' in r.text or "/logout" in r.text

    # -- requests ----------------------------------------------------------
    def get_json(self, path: str, **params: Any) -> Any:
        r = self._http.get(self.slug + path, params={"format": "json", **params})
        if r.status_code in (401, 403):
            raise LoginError("Not authenticated.")
        r.raise_for_status()
        return r.json()

    def get_html(self, path: str, **params: Any) -> str:
        r = self._http.get(self.slug + path, params=params or None)
        if r.status_code in (401, 403):
            raise LoginError("Not authenticated.")
        r.raise_for_status()
        return r.text

    def post_form(self, path: str, data: dict[str, str]) -> httpx.Response:
        """POST a form (callers pass the page's own `formkey`)."""
        r = self._http.post(self.slug + path, data=data)
        r.raise_for_status()
        return r

    def close(self) -> None:
        self._http.close()
