# CLAUDE.md

Windows-only tkinter GUI for controlling LIFX smart bulbs over the LAN.
Entry point: `lifx_control_panel/__main__.pyw` (`python lifx_control_panel/__main__.pyw`).

## Commands

```powershell
# Tests — MUST run from inside the package dir with PYTHONPATH=. (CI does the same)
cd lifx_control_panel
$env:PYTHONPATH = "."; python -m unittest discover test -p "*test*.py"

# Build exe (PyInstaller)
.\build_all.bat
```

## Architecture

- `__main__.pyw` — `LifxFrame` root window; owns device discovery (`scan_for_lights`), tray icon, keybinds, logging.
- `frames.py` — `LightFrame` (one per device; already handles multizone via `supports_multizone()`), `GroupFrame`.
- `utilities/async_bulb_interface.py` — background thread polling bulb state into per-label `Queue`s; frames drain them on a `FRAME_PERIOD_MS` tick.
- `utilities/color_thread.py` — screen-avg / dominant-color / cycle effects, each a restartable `ColorThreadRunner`.
- `ui/settings.py` — module-level `config` (ConfigParser) shared globally; layered `default.ini` → `config.ini` (written next to cwd at runtime).
- `test/dummy_devices.py` — fake lifxlan devices so tests run without hardware.

## Gotchas

- Uses a forked lifxlan (`samclane/lifxlan`) pinned in requirements.txt; `bitstring<4` is required — 4.x breaks lifxlan's pack formats.
- `pyaudio` is optional (commented out in requirements.txt); without it the music-color button is disabled. Guarded import in `utilities/audio.py`.
- Colors are HSBK 4-tuples with 0–65535 ranges (not 0–255 / 0–360). `utils.Color` is a NamedTuple — immutable, use `_replace`.
- Keep `requirements.txt` and `setup.py` `install_requires` in sync when touching deps.
- `_constants.py` VERSION/BUILD_DATE are updated in `lifx_control_panel\build_all.spec` at release time.
