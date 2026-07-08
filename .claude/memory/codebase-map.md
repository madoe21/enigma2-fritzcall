# Codebase map (onboarding 2026-07-08)

**enigma2-fritzcall** — Enigma2 (OpenATV 7.6) plugin: shows FRITZ!Box call
monitor / call list on the TV. Python.

## Layout
- `src/fritz_call/plugin.py` — entry (registers plugin, menu/EPG hooks).
- `src/fritz_call/api.py` (~300 LOC) — FRITZ!Box access (TR-064 / call-list
  fetch). **Data layer.**
- `src/fritz_call/services.py` (~250) — orchestration/polling.
- `src/fritz_call/screens.py` (~720) — enigma2 GUI (Screen/ConfigList) — the
  bulk of the enigma2 coupling.
- `res/` assets, `control/` ipk metadata, `build/` staged ipk (gitignored).

## Conventions
- Enigma2 Py3 runtime; keep imports defensive.
- Network calls must carry timeouts (GUI runs on the main reactor thread).

## Kodi portability: **monolithic (data layer already separate)**
`api.py`/`services.py` hold the FRITZ!Box logic; `screens.py`+`plugin.py`
hold enigma2 (`Screens.*`, `Components.*`) — 4 files import enigma2. Port =
move `api.py`/`services.py` into a `core/` package, confirm it is enigma2-free
(abstract config access), then add a `platform/kodi/` GUI. Data layer is the
portable asset; GUI is a rewrite per platform. See [[codebase-map]] pattern in
lotto/stocks/weather (already core/-split) as the target shape.
