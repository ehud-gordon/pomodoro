"""System tray icon: dynamic countdown with phase-coloured background."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon

from engine import Phase

ICON_HEIGHT = 128
ICON_WIDTH = 128  # GNOME panel slot is square — match it so we fill the whole slot

_COLOURS = {
    Phase.IDLE:        (QColor(110, 110, 110), QColor(235, 235, 235)),
    Phase.WORK:        (QColor( 35, 110, 200), QColor(255, 255, 255)),
    Phase.SHORT_BREAK: (QColor( 45, 165,  85), QColor(255, 255, 255)),
    Phase.LONG_BREAK:  (QColor( 45, 165,  85), QColor(255, 255, 255)),
}


def format_mmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:d}:{seconds % 60:02d}"


def minutes_remaining(seconds: int) -> int:
    """Ceil to whole minutes, so the displayed number ticks down at minute boundaries."""
    return max(0, (max(0, int(seconds)) + 59) // 60)


def render_icon(phase: Phase, seconds_remaining: int, running: bool) -> QIcon:
    pix = QPixmap(ICON_WIDTH, ICON_HEIGHT)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    try:
        if not running or phase == Phase.IDLE:
            bg, fg = _COLOURS[Phase.IDLE]
            text = "—"
        else:
            bg, fg = _COLOURS[phase]
            text = str(minutes_remaining(seconds_remaining))

        radius = ICON_HEIGHT * 0.08
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, ICON_WIDTH, ICON_HEIGHT, radius, radius)

        _draw_centered_text(painter, text, fg)
    finally:
        painter.end()
    return QIcon(pix)


def _draw_centered_text(painter: QPainter, text: str, colour: QColor) -> None:
    """Pick the largest bold font that fits text snugly inside the icon."""
    pad_x = 0
    pad_y = 0
    available_w = ICON_WIDTH - 2 * pad_x
    available_h = ICON_HEIGHT - 2 * pad_y

    font = QFont("Sans Serif")
    font.setBold(True)
    # Binary search for biggest size whose actual glyph bounding box fits.
    lo, hi = 8, ICON_HEIGHT * 4
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        font.setPixelSize(mid)
        rect = QFontMetrics(font).tightBoundingRect(text)
        if rect.width() <= available_w and rect.height() <= available_h:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    font.setPixelSize(best)
    painter.setFont(font)
    painter.setPen(colour)
    rect = QFontMetrics(font).tightBoundingRect(text)
    x = (ICON_WIDTH - rect.width()) / 2 - rect.left()
    y = (ICON_HEIGHT - rect.height()) / 2 - rect.top()
    painter.drawText(int(x), int(y), text)


class PomodoroTray(QSystemTrayIcon):
    show_requested = pyqtSignal()
    start_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    ticking_toggled = pyqtSignal(bool)
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setToolTip("Pomodoro")
        self._build_menu()
        self.activated.connect(self._on_activated)
        self.refresh(Phase.IDLE, 0, False)

    def _build_menu(self) -> None:
        menu = QMenu()
        self._act_show = menu.addAction("Show window")
        menu.addSeparator()
        self._act_start = menu.addAction("Start")
        self._act_pause = menu.addAction("Pause")
        self._act_stop = menu.addAction("Stop")
        menu.addSeparator()
        self._act_ticking = menu.addAction("Ticking sound")
        self._act_ticking.setCheckable(True)
        self._act_settings = menu.addAction("Settings…")
        menu.addSeparator()
        self._act_quit = menu.addAction("Quit")
        self.setContextMenu(menu)

        self._act_show.triggered.connect(self.show_requested)
        self._act_start.triggered.connect(self.start_requested)
        self._act_pause.triggered.connect(self.pause_requested)
        self._act_stop.triggered.connect(self.stop_requested)
        self._act_ticking.toggled.connect(self.ticking_toggled)
        self._act_settings.triggered.connect(self.settings_requested)
        self._act_quit.triggered.connect(self.quit_requested)

    def set_ticking_checked(self, on: bool) -> None:
        self._act_ticking.blockSignals(True)
        self._act_ticking.setChecked(on)
        self._act_ticking.blockSignals(False)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_requested.emit()

    def refresh(self, phase: Phase, seconds_remaining: int, running: bool) -> None:
        icon = render_icon(phase, seconds_remaining, running)
        self.setIcon(icon)
        if not running or phase == Phase.IDLE:
            self.setToolTip("Pomodoro — idle")
        else:
            label = {
                Phase.WORK: "Work",
                Phase.SHORT_BREAK: "Short break",
                Phase.LONG_BREAK: "Long break",
            }[phase]
            self.setToolTip(f"Pomodoro — {label} {format_mmss(seconds_remaining)}")

    def update_actions(self, running: bool, phase: Phase) -> None:
        idle = phase == Phase.IDLE
        self._act_start.setEnabled(not running)
        self._act_pause.setEnabled(running)
        self._act_stop.setEnabled(not idle or running)
