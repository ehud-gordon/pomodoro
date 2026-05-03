"""Headless tests for the pomodoro engine state machine.

Run: python -m pytest test_engine.py -q
or:  python test_engine.py
"""
from __future__ import annotations

import os
import sys

# Headless Qt (no display needed for engine logic).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QCoreApplication  # noqa: E402

from config import Settings  # noqa: E402
from engine import Phase, PomodoroEngine  # noqa: E402


def make_engine(**overrides) -> PomodoroEngine:
    s = Settings(
        work_minutes=overrides.get("work_minutes", 1),
        short_break_minutes=overrides.get("short_break_minutes", 1),
        long_break_minutes=overrides.get("long_break_minutes", 1),
        sessions_before_long_break=overrides.get("sessions_before_long_break", 4),
        ticking=False,
    )
    return PomodoroEngine(s)


def fast_forward(engine: PomodoroEngine, ticks: int) -> None:
    for _ in range(ticks):
        engine._on_tick()  # type: ignore[attr-defined]


def test_initial_state():
    e = make_engine()
    assert e.phase == Phase.IDLE
    assert not e.running
    assert e.remaining == 0


def test_start_enters_work():
    e = make_engine(work_minutes=2)
    e.start()
    assert e.phase == Phase.WORK
    assert e.running
    assert e.total == 120
    assert e.remaining == 120


def test_work_then_short_break():
    e = make_engine(work_minutes=1, short_break_minutes=1, sessions_before_long_break=4)
    e.start()
    fast_forward(e, 60)  # finish work
    assert e.phase == Phase.SHORT_BREAK
    assert e.remaining == 60
    assert e.completed_work_sessions == 1


def test_long_break_after_n_sessions():
    e = make_engine(work_minutes=1, short_break_minutes=1, long_break_minutes=1,
                    sessions_before_long_break=3)
    e.start()
    # 3 work + 2 short breaks before long break
    fast_forward(e, 60); assert e.phase == Phase.SHORT_BREAK
    fast_forward(e, 60); assert e.phase == Phase.WORK
    fast_forward(e, 60); assert e.phase == Phase.SHORT_BREAK
    fast_forward(e, 60); assert e.phase == Phase.WORK
    fast_forward(e, 60); assert e.phase == Phase.LONG_BREAK
    assert e.completed_work_sessions == 3


def test_pause_then_resume():
    e = make_engine(work_minutes=1)
    e.start()
    fast_forward(e, 5)
    assert e.remaining == 55
    e.pause()
    assert not e.running
    fast_forward(e, 0)
    assert e.remaining == 55  # untouched
    e.start()
    assert e.running


def test_stop_resets():
    e = make_engine()
    e.start()
    fast_forward(e, 10)
    e.stop()
    assert e.phase == Phase.IDLE
    assert not e.running
    assert e.remaining == 0
    assert e.completed_work_sessions == 0


def test_skip_advances_phase():
    e = make_engine(work_minutes=25)
    e.start()
    e.skip()
    assert e.phase == Phase.SHORT_BREAK
    assert e.completed_work_sessions == 1


def test_settings_apply_on_next_phase():
    e = make_engine(work_minutes=1, short_break_minutes=1)
    e.start()
    new = Settings(work_minutes=1, short_break_minutes=2,
                   long_break_minutes=15, sessions_before_long_break=4, ticking=False)
    e.update_settings(new)
    fast_forward(e, 60)  # finish work, enter short break
    assert e.phase == Phase.SHORT_BREAK
    assert e.total == 120  # uses new short break length


def test_cycle_signal_after_each_work():
    e = make_engine(work_minutes=1, short_break_minutes=1, sessions_before_long_break=4)
    received = []
    e.cycle_changed.connect(lambda c, t: received.append((c, t)))
    e.start()
    fast_forward(e, 60)
    fast_forward(e, 60)
    fast_forward(e, 60)
    assert (1, 4) in received and (2, 4) in received


TESTS = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]


def run_all() -> int:
    _app = QCoreApplication([])  # required for QObject signals; keep reference alive
    failures = 0
    for t in TESTS:
        try:
            t()
            print(f"OK   {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failures += 1
            print(f"ERR  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
