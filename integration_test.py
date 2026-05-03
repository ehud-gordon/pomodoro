"""Live integration test.

Boots the real PomodoroApp, but with second-scale phases driven via the
engine's tick interval (we shrink it to 50ms so the test is fast).
Logs every phase change so we can verify cycling.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Use a dedicated config file so we don't clobber the user's real settings.
TEST_CFG = Path("/tmp/pomodoro_integration_cfg")
TEST_CFG.mkdir(exist_ok=True)
os.environ["HOME"] = str(TEST_CFG)  # shifts ~/.config and tick.wav to tmp

from PyQt5.QtCore import QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from config import Settings, save_settings  # noqa: E402
from engine import Phase, PomodoroEngine  # noqa: E402
from sound import TickPlayer, ensure_tick_wav  # noqa: E402
from tray import PomodoroTray, render_icon  # noqa: E402
from ui import MainWindow  # noqa: E402


def main() -> int:
    # Pre-seed settings so the app uses 2s-ish phases.
    save_settings(Settings(
        work_minutes=1, short_break_minutes=1, long_break_minutes=1,
        sessions_before_long_break=2, ticking=True,
    ))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("FAIL: no system tray available")
        return 1
    print("OK: system tray available")

    # Build engine with a very fast tick (50ms) so 60 ticks = 3s per phase.
    settings = Settings(work_minutes=1, short_break_minutes=1, long_break_minutes=1,
                        sessions_before_long_break=2, ticking=True)
    engine = PomodoroEngine(settings, tick_ms=50)
    window = MainWindow()
    tray = PomodoroTray()

    phase_log: list[tuple[Phase, int]] = []
    tick_count = [0]
    icon_refresh_count = [0]

    def on_phase(p, t):
        phase_log.append((p, t))
        print(f"  phase -> {p.value} (total {t}s)")
        window.show_phase(p, t)

    def on_tick(s):
        tick_count[0] += 1
        window.show_remaining(s)
        tray.refresh(engine.phase, s, engine.running)
        icon_refresh_count[0] += 1

    engine.phase_changed.connect(on_phase)
    engine.tick.connect(on_tick)

    # Test ticking sound generation
    try:
        tick_path = ensure_tick_wav()
        assert tick_path.exists() and tick_path.stat().st_size > 0
        print(f"OK: tick.wav generated at {tick_path} ({tick_path.stat().st_size} bytes)")
        player = TickPlayer()
        player.play()
        print("OK: TickPlayer instantiated and play() called")
    except Exception as e:
        print(f"FAIL: tick sound: {e}")
        return 1

    # Verify tray icon renders for all phases
    for ph in (Phase.IDLE, Phase.WORK, Phase.SHORT_BREAK, Phase.LONG_BREAK):
        ic = render_icon(ph, 1234, ph != Phase.IDLE)
        assert not ic.isNull(), f"icon null for {ph}"
    print("OK: tray icon renders for all phases")

    tray.show()
    window.show()
    print("OK: window and tray shown")

    # Start the engine and let it run a few phase transitions.
    # work=60 ticks, short_break=60 ticks, work=60 ticks, long_break=60 ticks
    # at 50ms/tick -> 3s per phase. We'll run for ~10s to see >=3 transitions.
    engine.start()

    def finish():
        print(f"\n--- summary ---")
        print(f"ticks observed: {tick_count[0]}")
        print(f"icon refreshes: {icon_refresh_count[0]}")
        print(f"phase log:      {[(p.value, t) for p, t in phase_log]}")
        # We must have hit at least: WORK, SHORT_BREAK, WORK
        phases_seen = [p for p, _ in phase_log]
        ok = (Phase.WORK in phases_seen
              and Phase.SHORT_BREAK in phases_seen
              and phases_seen.count(Phase.WORK) >= 2)
        print("OK: cycled through phases" if ok else "FAIL: did not cycle as expected")
        # Also check we hit a long break (after 2 work sessions per settings).
        if Phase.LONG_BREAK in phases_seen:
            print("OK: long break reached")
        else:
            print("INFO: long break not reached in test window")
        app.exit(0 if ok else 2)

    QTimer.singleShot(11000, finish)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
