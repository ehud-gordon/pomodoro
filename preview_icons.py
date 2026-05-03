"""Render sample tray icons to PNG for visual inspection."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication
from engine import Phase
from tray import render_icon

app = QApplication(sys.argv)
samples = [
    ("idle.png",       Phase.IDLE,        0,    False),
    ("work_25.png",    Phase.WORK,        25*60, True),
    ("work_5_03.png",  Phase.WORK,        5*60+3, True),
    ("short_break.png",Phase.SHORT_BREAK, 4*60+12, True),
    ("long_break.png", Phase.LONG_BREAK,  14*60+59, True),
    ("last_seconds.png", Phase.WORK,      9, True),
]
for name, phase, secs, running in samples:
    icon = render_icon(phase, secs, running)
    pix = icon.pixmap(128, 128)
    out = f"/tmp/pomo_icon_{name}"
    pix.save(out, "PNG")
    print(f"wrote {out}")
