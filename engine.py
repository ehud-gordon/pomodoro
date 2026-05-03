"""Pomodoro state machine.

Drives a single QTimer at 1Hz. Emits signals consumed by the UI and tray.
"""
from __future__ import annotations

from enum import Enum

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from config import Settings


class Phase(Enum):
    IDLE = "idle"
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


PHASE_LABELS = {
    Phase.IDLE: "Ready",
    Phase.WORK: "Work",
    Phase.SHORT_BREAK: "Short break",
    Phase.LONG_BREAK: "Long break",
}


class PomodoroEngine(QObject):
    tick = pyqtSignal(int)                    # seconds remaining in current phase
    phase_changed = pyqtSignal(object, int)   # (Phase, total_seconds)
    running_changed = pyqtSignal(bool)
    cycle_changed = pyqtSignal(int, int)      # (completed_work_sessions, sessions_per_cycle)
    phase_completed = pyqtSignal(object)      # Phase that just finished

    def __init__(self, settings: Settings, parent=None, *, tick_ms: int = 1000):
        super().__init__(parent)
        self._settings = settings
        self._phase = Phase.IDLE
        self._total = 0
        self._remaining = 0
        self._completed_work = 0
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(tick_ms)
        self._timer.setTimerType(0)  # Qt.PreciseTimer
        self._timer.timeout.connect(self._on_tick)

    # ---- public state --------------------------------------------------
    @property
    def phase(self) -> Phase: return self._phase
    @property
    def remaining(self) -> int: return self._remaining
    @property
    def total(self) -> int: return self._total
    @property
    def running(self) -> bool: return self._running
    @property
    def completed_work_sessions(self) -> int: return self._completed_work
    @property
    def settings(self) -> Settings: return self._settings

    # ---- commands ------------------------------------------------------
    def update_settings(self, settings: Settings) -> None:
        """New settings take effect from the next phase onward."""
        self._settings = settings

    def start(self) -> None:
        if self._phase == Phase.IDLE:
            self._begin_phase(Phase.WORK)
        if not self._running:
            self._running = True
            self._timer.start()
            self.running_changed.emit(True)

    def pause(self) -> None:
        if self._running:
            self._running = False
            self._timer.stop()
            self.running_changed.emit(False)

    def stop(self) -> None:
        was_running = self._running
        self._running = False
        self._timer.stop()
        self._completed_work = 0
        self._begin_phase(Phase.IDLE)
        self.cycle_changed.emit(0, self._settings.sessions_before_long_break)
        if was_running:
            self.running_changed.emit(False)

    def skip(self) -> None:
        """Jump to the next phase immediately. Keeps running state."""
        if self._phase == Phase.IDLE:
            return
        self._advance_phase()

    # ---- internals -----------------------------------------------------
    def _begin_phase(self, phase: Phase) -> None:
        self._phase = phase
        if phase == Phase.IDLE:
            self._total = 0
            self._remaining = 0
        else:
            minutes = {
                Phase.WORK: self._settings.work_minutes,
                Phase.SHORT_BREAK: self._settings.short_break_minutes,
                Phase.LONG_BREAK: self._settings.long_break_minutes,
            }[phase]
            self._total = minutes * 60
            self._remaining = self._total
        self.phase_changed.emit(self._phase, self._total)
        self.tick.emit(self._remaining)

    def _on_tick(self) -> None:
        if self._remaining > 0:
            self._remaining -= 1
            self.tick.emit(self._remaining)
        if self._remaining <= 0:
            self._advance_phase()

    def _advance_phase(self) -> None:
        finished = self._phase
        if self._phase == Phase.WORK:
            self._completed_work += 1
            self.cycle_changed.emit(self._completed_work, self._settings.sessions_before_long_break)
            self.phase_completed.emit(finished)
            if self._completed_work % self._settings.sessions_before_long_break == 0:
                self._begin_phase(Phase.LONG_BREAK)
            else:
                self._begin_phase(Phase.SHORT_BREAK)
        elif self._phase in (Phase.SHORT_BREAK, Phase.LONG_BREAK):
            self.phase_completed.emit(finished)
            self._begin_phase(Phase.WORK)
        else:
            self._begin_phase(Phase.WORK)
        if not self._timer.isActive():
            self._timer.start()
            self._running = True
            self.running_changed.emit(True)
