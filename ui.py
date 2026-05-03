"""Main window and settings dialog."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QFont, QPalette
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QMainWindow, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from config import DEFAULT_TICK_SOUND, Settings, TICK_SOUND_CHOICES
from engine import PHASE_LABELS, Phase
from tray import format_mmss


# ---- main window -------------------------------------------------------
class MainWindow(QMainWindow):
    start_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    skip_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    ticking_toggled = pyqtSignal(bool)
    quit_requested = pyqtSignal()

    PHASE_BG = {
        Phase.IDLE:        "#3a3a3a",
        Phase.WORK:        "#236ec8",
        Phase.SHORT_BREAK: "#2da555",
        Phase.LONG_BREAK:  "#2da555",
    }

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pomodoro")
        self.resize(380, 320)
        self._build()
        self._hide_to_tray_on_close = True

    def _build(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(14)

        self.phase_label = QLabel("Ready")
        self.phase_label.setAlignment(Qt.AlignCenter)
        f = self.phase_label.font(); f.setPointSize(16); f.setBold(True)
        self.phase_label.setFont(f)

        self.timer_label = QLabel("00:00")
        self.timer_label.setAlignment(Qt.AlignCenter)
        f = QFont("Monospace"); f.setStyleHint(QFont.Monospace); f.setPointSize(56); f.setBold(True)
        self.timer_label.setFont(f)
        self.timer_label.setMinimumHeight(110)
        self.timer_label.setAutoFillBackground(True)
        self._set_phase_colour(Phase.IDLE)

        self.cycle_label = QLabel("Sessions completed: 0")
        self.cycle_label.setAlignment(Qt.AlignCenter)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop  = QPushButton("Stop")
        self.btn_skip  = QPushButton("Skip")
        for b in (self.btn_start, self.btn_pause, self.btn_stop, self.btn_skip):
            b.setMinimumHeight(34)
            btn_row.addWidget(b)

        # Settings + quit row
        bottom = QHBoxLayout()
        self.chk_ticking = QCheckBox("Ticking")
        self.btn_settings = QPushButton("Settings…")
        self.btn_quit = QPushButton("Quit")
        self.btn_settings.setMinimumHeight(30)
        self.btn_quit.setMinimumHeight(30)
        bottom.addWidget(self.chk_ticking)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_settings)
        bottom.addWidget(self.btn_quit)

        v.addWidget(self.phase_label)
        v.addWidget(self.timer_label, 1)
        v.addWidget(self.cycle_label)
        v.addLayout(btn_row)
        v.addLayout(bottom)

        self.btn_start.clicked.connect(self.start_requested)
        self.btn_pause.clicked.connect(self.pause_requested)
        self.btn_stop.clicked.connect(self.stop_requested)
        self.btn_skip.clicked.connect(self.skip_requested)
        self.btn_settings.clicked.connect(self.settings_requested)
        self.btn_quit.clicked.connect(self.quit_requested)
        self.chk_ticking.toggled.connect(self.ticking_toggled)

        self.update_buttons(running=False, phase=Phase.IDLE)

    def _set_phase_colour(self, phase: Phase) -> None:
        bg = self.PHASE_BG[phase]
        self.timer_label.setStyleSheet(
            f"background-color: {bg}; color: white; border-radius: 10px; padding: 12px;"
        )

    # ---- slots from main app ------------------------------------------
    def show_remaining(self, seconds: int) -> None:
        self.timer_label.setText(format_mmss(seconds))

    def show_phase(self, phase: Phase, total: int) -> None:
        self.phase_label.setText(PHASE_LABELS[phase])
        self._set_phase_colour(phase)
        if phase == Phase.IDLE:
            self.timer_label.setText("00:00")

    def show_cycle(self, completed: int, per_cycle: int) -> None:
        next_long = per_cycle - (completed % per_cycle) if completed else per_cycle
        self.cycle_label.setText(
            f"Sessions completed: {completed}   ·   {next_long} until long break"
        )

    def update_buttons(self, running: bool, phase: Phase) -> None:
        idle = phase == Phase.IDLE
        self.btn_start.setEnabled(not running)
        self.btn_start.setText("Resume" if (not running and not idle) else "Start")
        self.btn_pause.setEnabled(running)
        self.btn_stop.setEnabled(not idle or running)
        self.btn_skip.setEnabled(not idle)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt signature)
        if self._hide_to_tray_on_close:
            event.ignore()
            self.hide()
        else:
            event.accept()

    def allow_real_close(self) -> None:
        self._hide_to_tray_on_close = False

    def set_ticking_checked(self, on: bool) -> None:
        self.chk_ticking.blockSignals(True)
        self.chk_ticking.setChecked(on)
        self.chk_ticking.blockSignals(False)


# ---- settings dialog ---------------------------------------------------
TICK_SOUND_LABELS = {
    "woodblock": "Woodblock",
    "wall_clock": "Clock — wall",
    "wristwatch": "Clock — wristwatch",
}


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)

        self.spin_work = self._spin(1, 180, settings.work_minutes)
        self.spin_short = self._spin(1, 60, settings.short_break_minutes)
        self.spin_long = self._spin(1, 120, settings.long_break_minutes)
        self.spin_count = self._spin(1, 20, settings.sessions_before_long_break)
        self.chk_tick = QCheckBox("Play ticking sound during work sessions")
        self.chk_tick.setChecked(settings.ticking)

        self.combo_sound = QComboBox()
        for key in TICK_SOUND_CHOICES:
            self.combo_sound.addItem(TICK_SOUND_LABELS.get(key, key), key)
        current = settings.tick_sound if settings.tick_sound in TICK_SOUND_CHOICES else DEFAULT_TICK_SOUND
        self.combo_sound.setCurrentIndex(self.combo_sound.findData(current))
        self.combo_sound.setEnabled(self.chk_tick.isChecked())
        self.chk_tick.toggled.connect(self.combo_sound.setEnabled)

        self.chk_alarm = QCheckBox("Play alarm sound when a phase changes")
        self.chk_alarm.setChecked(settings.alarm)

        form = QFormLayout()
        form.addRow("Work session length (minutes):", self.spin_work)
        form.addRow("Short break length (minutes):", self.spin_short)
        form.addRow("Long break length (minutes):", self.spin_long)
        form.addRow("Sessions before long break:", self.spin_count)
        form.addRow(self.chk_tick)
        form.addRow("Ticking sound:", self.combo_sound)
        form.addRow(self.chk_alarm)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _spin(lo: int, hi: int, value: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(int(value))
        s.setMinimumWidth(80)
        return s

    def values(self) -> Settings:
        return Settings(
            work_minutes=self.spin_work.value(),
            short_break_minutes=self.spin_short.value(),
            long_break_minutes=self.spin_long.value(),
            sessions_before_long_break=self.spin_count.value(),
            ticking=self.chk_tick.isChecked(),
            tick_sound=self.combo_sound.currentData() or DEFAULT_TICK_SOUND,
            alarm=self.chk_alarm.isChecked(),
        ).normalized()
