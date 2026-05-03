# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Python interpreter

Use `/home/ehud/miniforge3/bin/python3` for everything (running the app, tests, install script). The launcher `pomodorot.sh` hardcodes this path. PyQt5 is the only third-party dependency.

## Common commands

```bash
# Run the app (GUI; requires a system tray)
/home/ehud/miniforge3/bin/python3 main.py

# Headless engine unit tests (no display required — uses QT_QPA_PLATFORM=offscreen)
/home/ehud/miniforge3/bin/python3 test_engine.py
# or via pytest, single test:
/home/ehud/miniforge3/bin/python3 -m pytest test_engine.py::test_long_break_after_n_sessions -q

# Live integration test — boots real PomodoroApp with tick_ms=50 and runs ~11s.
# Needs a real system tray; writes to /tmp/pomodoro_integration_cfg (NOT your real config).
/home/ehud/miniforge3/bin/python3 integration_test.py

# Render sample tray icons to /tmp/pomo_icon_*.png for visual inspection
/home/ehud/miniforge3/bin/python3 preview_icons.py

# Install desktop entry + autostart + app icon (idempotent)
/home/ehud/miniforge3/bin/python3 install.py
```

## Architecture

The app is a single-process PyQt5 desktop pomodoro timer. The architecture is a strict pub/sub fan-out from one engine to two views (window + tray), wired together by a thin coordinator.

**Module layering** (no cycles):
- `config.py` — `Settings` dataclass + JSON persistence at `~/.config/pomodoro/config.json`. `Settings.normalized()` clamps fields to valid ranges; loaders/savers always normalize. Adding a setting = add field, range, and (if a string enum) a CHOICES tuple.
- `engine.py` — `PomodoroEngine(QObject)`: pure state machine. Holds the only `QTimer`. Emits `tick`, `phase_changed`, `running_changed`, `cycle_changed`, `phase_completed`. Has no UI imports. `update_settings()` does NOT take effect until the next phase begins (intentional — see `test_settings_apply_on_next_phase`).
- `sound.py` — Synthesizes tick WAVs on demand into `~/.config/pomodoro/`. The "woodblock" sound uses the legacy filename `tick.wav` for backward compat; others are `tick_<name>.wav`. `ensure_tick_wav` regenerates any cached file <50ms because PulseAudio's `QSoundEffect` silently drops short clips. Adding a new tick sound = add a generator function + register it in `SOUND_GENERATORS` + extend `TICK_SOUND_CHOICES` in `config.py` + add a label in `ui.TICK_SOUND_LABELS`.
- `tray.py` — `PomodoroTray(QSystemTrayIcon)` + `render_icon()`. Icon is repainted on every tick: minutes-remaining (ceil) on a phase-coloured rounded rect. Font size is binary-searched to fit. Emits its own request signals (start/pause/stop/settings/ticking/quit) — never calls into the engine directly.
- `ui.py` — `MainWindow` and `SettingsDialog`. Window emits request signals only — same pattern as tray. Closing the window hides to tray (see `closeEvent` + `allow_real_close`).
- `main.py` — `PomodoroApp` is the wiring layer. It owns the engine, window, tray, and `TickPlayer`. It connects window/tray request signals to engine commands, and engine signals to window/tray view updates. **All cross-component coordination lives here**; engine/tray/ui must not know about each other.

**Signal flow for a tick:**
```
QTimer (1Hz)
  -> engine._on_tick()
  -> engine.tick.emit(seconds)
  -> PomodoroApp._on_tick
       -> window.show_remaining(seconds)        (timer label)
       -> tray.refresh(phase, seconds, running) (re-render icon)
       -> tick_player.play() if WORK and ticking enabled
```

**Phase transitions** are driven entirely inside `engine._advance_phase()`: WORK -> SHORT_BREAK or LONG_BREAK (every `sessions_before_long_break` work sessions) -> WORK. `skip()` calls `_advance_phase()` directly. `stop()` resets to IDLE and clears the work-session counter.

## Testing approach

- `test_engine.py` runs without a display by directly calling `engine._on_tick()` instead of waiting for the QTimer — that's why `fast_forward` exists. Add new engine tests in this style; do not introduce real-time waits.
- `integration_test.py` is a smoke test for the whole stack including real audio/tray. It overrides `HOME` to `/tmp/pomodoro_integration_cfg` so it can't touch the user's real `~/.config/pomodoro/config.json`. Preserve that override if you extend it.

## Conventions specific to this repo

- Engine signals use `pyqtSignal(object, ...)` for `Phase` enums (PyQt doesn't auto-marshal Python enums).
- Views (window, tray) expose `*_requested` signals; commands flow only through `PomodoroApp`. Don't shortcut by calling `engine.start()` from a view.
- When a UI control reflects engine state (e.g., the "Ticking" checkbox), `blockSignals(True)` around `setChecked` to avoid feedback loops — see `MainWindow.set_ticking_checked` and `PomodoroTray.set_ticking_checked`.
- The tray icon is square 128x128 because the GNOME panel slot is square; changing aspect ratio will leave gaps.
