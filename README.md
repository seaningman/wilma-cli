# wilma 🐱

A cozy terminal app for [Wilma](https://www.visma.fi/wilma/): schedule, homework & exams, messages
(read + reply) and school news — as a full-screen TUI or scriptable commands.

> Wilma has no official public API. This tool uses the same web endpoints as the browser
> (`/overview`, `/messages/list`, …) and was built against Espoo's instance; other
> municipalities may differ. Run `wilma doctor` if something looks off.

## Install

```sh
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/wilma login --url https://<school>.inschool.fi -u <username>
```
The password goes to your system keyring (or set `WILMA_PASSWORD`).

## Use

```sh
wilma                      # full-screen app, fully keyboard-driven (press ? for help)
wilma schedule [--week | --day 2026-11-09]
wilma homework | exams
wilma news list | read ID
wilma messages list | read ID | mark-read ID
wilma messages reply ID -b "Thanks!"       # previews and asks before sending
wilma messages send --to-teacher ID -s "Subject" -b "Text"   # experimental; ids via `wilma teachers`
wilma doctor
```
Every data command takes `--json`.

## Keys (no mouse needed)

| Keys | Action |
|---|---|
| `1`–`5`, `tab` / `shift+tab` | switch tabs |
| `j` `k` / `↓` `↑`, `g` `G`, `ctrl+d` `ctrl+u` | move, top/bottom, page |
| `l` / `→`, `h` / `←`, `esc` | open reader / back to list |
| `h` `l`, `t` (schedule) | previous/next day, today |
| `/` | jump box (`sched`, `hw`, `msg`, `news`) |
| `r` | reply (`ctrl+s` review, `enter` send, `esc` cancel) |
| `f5`, `?`, `q` | refresh, help, quit |

## Development

```sh
.venv/bin/pip install -e '.[dev]' && .venv/bin/pytest
```
Tests use synthetic data only; never commit real student data.
