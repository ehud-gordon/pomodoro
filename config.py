"""Settings persistence for the pomodoro app."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "pomodoro"
CONFIG_FILE = CONFIG_DIR / "config.json"

TICK_SOUND_CHOICES = ("woodblock", "wall_clock", "wristwatch")
DEFAULT_TICK_SOUND = "woodblock"


@dataclass
class Settings:
    work_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    sessions_before_long_break: int = 4
    ticking: bool = False
    tick_sound: str = DEFAULT_TICK_SOUND
    alarm: bool = True

    def normalized(self) -> "Settings":
        return Settings(
            work_minutes=_clamp(self.work_minutes, 1, 180),
            short_break_minutes=_clamp(self.short_break_minutes, 1, 60),
            long_break_minutes=_clamp(self.long_break_minutes, 1, 120),
            sessions_before_long_break=_clamp(self.sessions_before_long_break, 1, 20),
            ticking=bool(self.ticking),
            tick_sound=self.tick_sound if self.tick_sound in TICK_SOUND_CHOICES else DEFAULT_TICK_SOUND,
            alarm=bool(self.alarm),
        )


def _clamp(value: object, lo: int, hi: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


def load_settings() -> Settings:
    if not CONFIG_FILE.exists():
        return Settings()
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return Settings()
    known = {f.name for f in fields(Settings)}
    filtered = {k: v for k, v in data.items() if k in known}
    return Settings(**filtered).normalized()


def save_settings(settings: Settings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(asdict(settings.normalized()), indent=2))
