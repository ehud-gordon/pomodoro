#!/usr/bin/env python3
"""Pomodoro timer with system tray icon."""
from __future__ import annotations

import sys
from dataclasses import replace
from typing import Optional

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from config import Settings, load_settings, save_settings
from engine import PHASE_LABELS, Phase, PomodoroEngine
from sound import AlarmPlayer, TickPlayer
from tray import PomodoroTray
from ui import MainWindow, SettingsDialog


class PomodoroApp(QObject):
    def __init__(self, qapp: QApplication) -> None:
        super().__init__()
        self.qapp = qapp
        self.settings = load_settings()
        self.engine = PomodoroEngine(self.settings)
        self.window = MainWindow()
        self.tray = PomodoroTray()
        self.tick_player: Optional[TickPlayer] = None
        self.alarm_player: Optional[AlarmPlayer] = None

        self._wire_window()
        self._wire_tray()
        self._wire_engine()

        self.window.show_cycle(0, self.settings.sessions_before_long_break)
        self.window.show_phase(Phase.IDLE, 0)
        self.window.update_buttons(running=False, phase=Phase.IDLE)
        self.window.set_ticking_checked(self.settings.ticking)
        self.tray.update_actions(running=False, phase=Phase.IDLE)
        self.tray.set_ticking_checked(self.settings.ticking)
        self.tray.show()

    # ---- wiring --------------------------------------------------------
    def _wire_window(self) -> None:
        w = self.window
        w.start_requested.connect(self.engine.start)
        w.pause_requested.connect(self.engine.pause)
        w.stop_requested.connect(self.engine.stop)
        w.skip_requested.connect(self.engine.skip)
        w.settings_requested.connect(self.open_settings)
        w.ticking_toggled.connect(self.set_ticking)
        w.quit_requested.connect(self.quit)

    def _wire_tray(self) -> None:
        t = self.tray
        t.show_requested.connect(self.show_window)
        t.start_requested.connect(self.engine.start)
        t.pause_requested.connect(self.engine.pause)
        t.stop_requested.connect(self.engine.stop)
        t.settings_requested.connect(self.open_settings)
        t.ticking_toggled.connect(self.set_ticking)
        t.quit_requested.connect(self.quit)

    def _wire_engine(self) -> None:
        e = self.engine
        e.tick.connect(self._on_tick)
        e.phase_changed.connect(self._on_phase_changed)
        e.running_changed.connect(self._on_running_changed)
        e.cycle_changed.connect(self.window.show_cycle)
        e.phase_completed.connect(self._on_phase_completed)

    # ---- engine signal handlers ---------------------------------------
    def _on_tick(self, seconds_remaining: int) -> None:
        self.window.show_remaining(seconds_remaining)
        self.tray.refresh(self.engine.phase, seconds_remaining, self.engine.running)
        if (self.engine.running
                and self.engine.phase == Phase.WORK
                and self.settings.ticking
                and self.tick_player is not None):
            self.tick_player.play()

    def _on_phase_changed(self, phase: Phase, total: int) -> None:
        self.window.show_phase(phase, total)
        self.window.update_buttons(running=self.engine.running, phase=phase)
        self.tray.refresh(phase, self.engine.remaining, self.engine.running)
        self.tray.update_actions(running=self.engine.running, phase=phase)

    def _on_running_changed(self, running: bool) -> None:
        self.window.update_buttons(running=running, phase=self.engine.phase)
        self.tray.refresh(self.engine.phase, self.engine.remaining, running)
        self.tray.update_actions(running=running, phase=self.engine.phase)

    def _on_phase_completed(self, phase: Phase) -> None:
        msg = {
            Phase.WORK: "Work session complete — time for a break!",
            Phase.SHORT_BREAK: "Short break over — back to work.",
            Phase.LONG_BREAK: "Long break over — back to work.",
        }.get(phase)
        if msg and self.tray.supportsMessages():
            self.tray.showMessage("Pomodoro", msg, QSystemTrayIcon.Information, 4000)
        if self.settings.alarm and self.alarm_player is not None:
            self.alarm_player.play()

    # ---- top-level commands -------------------------------------------
    def show_window(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, parent=self.window)
        if dlg.exec_() == dlg.Accepted:
            new = dlg.values()
            self.settings = new
            self.engine.update_settings(new)
            save_settings(new)
            self._sync_tick_player()
            self._sync_alarm_player()
            self.window.set_ticking_checked(new.ticking)
            self.tray.set_ticking_checked(new.ticking)
            # If user is currently idle, refresh "until long break" hint
            if self.engine.phase == Phase.IDLE:
                self.window.show_cycle(0, new.sessions_before_long_break)

    def set_ticking(self, on: bool) -> None:
        """Toggle ticking sound, applied immediately (even mid-session)."""
        if self.settings.ticking == on:
            return
        self.settings = replace(self.settings, ticking=on)
        self.engine.update_settings(self.settings)
        save_settings(self.settings)
        self._sync_tick_player()
        self.window.set_ticking_checked(on)
        self.tray.set_ticking_checked(on)

    def _sync_tick_player(self) -> None:
        if not self.settings.ticking:
            self.tick_player = None
            return
        if self.tick_player is not None and self.tick_player.sound == self.settings.tick_sound:
            return
        try:
            self.tick_player = TickPlayer(self.settings.tick_sound)
        except Exception as exc:  # audio not available — degrade gracefully
            self.tick_player = None
            QMessageBox.warning(
                self.window, "Pomodoro",
                f"Could not enable ticking sound:\n{exc}"
            )

    def _sync_alarm_player(self) -> None:
        if not self.settings.alarm:
            self.alarm_player = None
            return
        if self.alarm_player is not None:
            return
        try:
            self.alarm_player = AlarmPlayer()
        except Exception as exc:
            self.alarm_player = None
            QMessageBox.warning(
                self.window, "Pomodoro",
                f"Could not enable alarm sound:\n{exc}"
            )

    def quit(self) -> None:
        self.window.allow_real_close()
        self.tray.hide()
        self.qapp.quit()


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Pomodoro")
    app.setQuitOnLastWindowClosed(False)  # tray keeps app alive

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Pomodoro",
                             "No system tray detected. The app needs a system tray.")
        return 1

    pomodoro = PomodoroApp(app)
    pomodoro._sync_tick_player()  # initialise if enabled
    pomodoro._sync_alarm_player()  # initialise if enabled
    pomodoro.show_window()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
