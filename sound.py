"""Synthesized tick sounds + playback wrapper."""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path
from typing import Callable, Iterable

from PyQt5.QtCore import QUrl
from PyQt5.QtMultimedia import QSoundEffect

SOUND_DIR = Path.home() / ".config" / "pomodoro"
TICK_PATH = SOUND_DIR / "tick.wav"  # legacy path — kept for backward compat
ALARM_PATH = SOUND_DIR / "alarm.wav"
RATE = 22050

SampleGen = Callable[[int], Iterable[float]]


def _woodblock(rate: int) -> Iterable[float]:
    """Bright two-tone click (the original tick)."""
    duration = 0.05
    n = int(rate * duration)
    for i in range(n):
        t = i / rate
        envelope = math.exp(-t * 80)
        yield (math.sin(2 * math.pi * 1800 * t) * 0.6
               + math.sin(2 * math.pi * 900 * t) * 0.4) * envelope * 0.4


def _wall_clock(rate: int) -> Iterable[float]:
    """Pendulum/wall-clock 'tock': a sharp escapement click + low hollow body."""
    duration = 0.09
    n = int(rate * duration)
    for i in range(n):
        t = i / rate
        click_env = math.exp(-t * 450)
        click = (math.sin(2 * math.pi * 2400 * t)
                 + math.sin(2 * math.pi * 1100 * t) * 0.6) * click_env * 0.30
        body_env = math.exp(-t * 45)
        body = (math.sin(2 * math.pi * 360 * t)
                + math.sin(2 * math.pi * 180 * t) * 0.7) * body_env * 0.30
        yield click + body


def _wristwatch(rate: int) -> Iterable[float]:
    """Quartz wristwatch 'tick': very brief, high, with a noisy attack.

    The audible tick is ~25ms but the clip is padded to ~80ms with silence
    because QSoundEffect on some backends (PulseAudio) silently drops clips
    shorter than its internal buffer period.
    """
    rng = random.Random(42)
    tick_duration = 0.025
    total_duration = 0.08
    tick_n = int(rate * tick_duration)
    total_n = int(rate * total_duration)
    for i in range(total_n):
        if i >= tick_n:
            yield 0.0
            continue
        t = i / rate
        envelope = math.exp(-t * 280)
        noise = (rng.random() * 2 - 1) * 0.45
        tone = (math.sin(2 * math.pi * 3200 * t) * 0.6
                + math.sin(2 * math.pi * 5200 * t) * 0.3)
        yield (noise + tone) * envelope * 0.7


# Registry of available tick sounds. Keys must match config.TICK_SOUND_CHOICES.
SOUND_GENERATORS: dict[str, SampleGen] = {
    "woodblock": _woodblock,
    "wall_clock": _wall_clock,
    "wristwatch": _wristwatch,
}


def _alarm(rate: int) -> Iterable[float]:
    """Two-note descending chime (~0.95s) for phase transitions."""
    note_duration = 0.45
    gap_duration = 0.05
    notes = (880.0, 660.0)  # A5 -> E5
    n_per_note = int(rate * note_duration)
    n_gap = int(rate * gap_duration)
    for note_idx, freq in enumerate(notes):
        for i in range(n_per_note):
            t = i / rate
            envelope = math.exp(-t * 4.0)
            yield (math.sin(2 * math.pi * freq * t) * 0.55
                   + math.sin(2 * math.pi * freq * 2 * t) * 0.18
                   + math.sin(2 * math.pi * freq * 3 * t) * 0.06) * envelope * 0.65
        if note_idx < len(notes) - 1:
            for _ in range(n_gap):
                yield 0.0


def _wav_path(name: str) -> Path:
    if name == "woodblock":
        # Preserve historical filename so existing installs don't regenerate.
        return TICK_PATH
    return SOUND_DIR / f"tick_{name}.wav"


def _write_wav(path: Path, samples: Iterable[float], rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for s in samples:
        s = max(-1.0, min(1.0, s))
        frames.extend(struct.pack("<h", int(s * 32767)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def ensure_tick_wav(name: str = "woodblock") -> Path:
    """Generate the wav for the named sound on first use; return its path.

    Regenerates any cached file shorter than 50ms — QSoundEffect on PulseAudio
    can silently drop clips shorter than its internal buffer period.
    """
    if name not in SOUND_GENERATORS:
        name = "woodblock"
    path = _wav_path(name)
    if path.exists() and _wav_duration_ms(path) >= 50:
        return path
    _write_wav(path, SOUND_GENERATORS[name](RATE), RATE)
    return path


def ensure_alarm_wav() -> Path:
    """Generate the alarm wav on first use; return its path."""
    if ALARM_PATH.exists() and _wav_duration_ms(ALARM_PATH) >= 50:
        return ALARM_PATH
    _write_wav(ALARM_PATH, _alarm(RATE), RATE)
    return ALARM_PATH


def _wav_duration_ms(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / w.getframerate() * 1000.0
    except (OSError, wave.Error):
        return 0.0


class TickPlayer:
    """Plays a tick sound on demand. Safe to call rapidly."""

    def __init__(self, sound: str = "woodblock") -> None:
        self._sound = sound if sound in SOUND_GENERATORS else "woodblock"
        path = ensure_tick_wav(self._sound)
        self._effect = QSoundEffect()
        self._effect.setSource(QUrl.fromLocalFile(str(path)))
        self._effect.setVolume(0.4)
        self._effect.setLoopCount(1)

    @property
    def sound(self) -> str:
        return self._sound

    def play(self) -> None:
        # Restart even if a previous instance is still playing.
        self._effect.stop()
        self._effect.play()

    def set_volume(self, v: float) -> None:
        self._effect.setVolume(max(0.0, min(1.0, v)))


class AlarmPlayer:
    """Plays the phase-transition alarm sound on demand."""

    def __init__(self) -> None:
        path = ensure_alarm_wav()
        self._effect = QSoundEffect()
        self._effect.setSource(QUrl.fromLocalFile(str(path)))
        self._effect.setVolume(0.7)
        self._effect.setLoopCount(1)

    def play(self) -> None:
        self._effect.stop()
        self._effect.play()

    def set_volume(self, v: float) -> None:
        self._effect.setVolume(max(0.0, min(1.0, v)))
