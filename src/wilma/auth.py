"""Config, credential and session-cache handling."""
from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import keyring
from keyring.errors import KeyringError

SERVICE = "wilma-cli"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "wilma"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "wilma"
CONFIG_FILE = CONFIG_DIR / "config.toml"
SESSION_FILE = CACHE_DIR / "session.json"


@dataclass
class Config:
    base_url: str = ""
    username: str = ""

    @property
    def ready(self) -> bool:
        return bool(self.base_url and self.username)


def normalize_base_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def load_config() -> Config:
    if not CONFIG_FILE.exists():
        return Config()
    data = tomllib.loads(CONFIG_FILE.read_text())
    return Config(data.get("base_url", ""), data.get("username", ""))


def save_config(cfg: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(f'base_url = "{cfg.base_url}"\nusername = "{cfg.username}"\n')


def get_password(username: str) -> str | None:
    if pw := os.environ.get("WILMA_PASSWORD"):
        return pw
    try:
        return keyring.get_password(SERVICE, username)
    except KeyringError:
        return None


def store_password(username: str, password: str) -> bool:
    try:
        keyring.set_password(SERVICE, username, password)
        return True
    except KeyringError:
        return False


def delete_password(username: str) -> None:
    try:
        keyring.delete_password(SERVICE, username)
    except KeyringError:
        pass


def load_session() -> dict[str, str]:
    try:
        return json.loads(SESSION_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_session(cookies: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.touch(mode=0o600, exist_ok=True)
    SESSION_FILE.chmod(0o600)
    SESSION_FILE.write_text(json.dumps(cookies))


def clear_session() -> None:
    SESSION_FILE.unlink(missing_ok=True)
