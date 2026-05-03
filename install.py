#!/usr/bin/env python3
"""Install desktop entry, autostart entry, and app icon for pomodorot.

Idempotent — safe to re-run.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication

PROJECT = Path(__file__).resolve().parent
DESKTOP_NAME = "pomodorot.desktop"
ICON_NAME = "pomodorot.png"

APPS_DIR = Path.home() / ".local" / "share" / "applications"
AUTOSTART_DIR = Path.home() / ".config" / "autostart"


def render_app_icon(out_path: Path, size: int = 256) -> None:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(35, 110, 200))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, size, size, size * 0.18, size * 0.18)
    font = QFont("Sans Serif"); font.setBold(True); font.setPixelSize(int(size * 0.50))
    p.setFont(font); p.setPen(QColor(255, 255, 255))
    fm = p.fontMetrics()
    text = "25"
    x = (size - fm.horizontalAdvance(text)) / 2
    y = (size + fm.ascent() - fm.descent()) / 2
    p.drawText(int(x), int(y), text)
    p.end()
    pix.save(str(out_path), "PNG")


def install() -> int:
    # QApplication is required for QPixmap rendering even in offscreen mode.
    _app = QApplication.instance() or QApplication([])

    # 1. Make launcher executable.
    launcher = PROJECT / "pomodorot.sh"
    launcher.chmod(0o755)

    # 2. Render app icon next to project so the .desktop file can reference it.
    icon_path = PROJECT / ICON_NAME
    render_app_icon(icon_path)
    print(f"icon  -> {icon_path}")

    # 3. Install desktop entry to ~/.local/share/applications/
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    src = PROJECT / DESKTOP_NAME
    dst = APPS_DIR / DESKTOP_NAME
    shutil.copy(src, dst)
    dst.chmod(0o644)
    print(f"desktop -> {dst}")

    # 4. Install autostart entry to ~/.config/autostart/
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    auto = AUTOSTART_DIR / DESKTOP_NAME
    shutil.copy(src, auto)
    auto.chmod(0o644)
    print(f"autostart -> {auto}")

    # 5. Refresh the desktop database (best-effort).
    update_db = shutil.which("update-desktop-database")
    if update_db:
        subprocess.run([update_db, str(APPS_DIR)], check=False)
        print("update-desktop-database refreshed")

    print("\nInstalled. The app will start on next login and is searchable as 'Pomodorot'.")
    return 0


if __name__ == "__main__":
    sys.exit(install())
