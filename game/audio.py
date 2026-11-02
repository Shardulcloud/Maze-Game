"""Audio: loads synthesized .wav assets, plays effects + music, fails soft.

If ``pygame.mixer`` can't initialize (no audio device -- e.g. CI, dummy
drivers) or the asset files are missing, every method becomes a no-op and
the game runs silent.  On first launch the manager runs
``tools/generate_sounds.py`` to create the assets automatically.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import pygame

ROOT = Path(__file__).resolve().parents[1]
SOUNDS_DIR = ROOT / "assets" / "sounds"
GEN_SCRIPT = ROOT / "tools" / "generate_sounds.py"

# name -> (default volume, minimum seconds between plays)
_RATES = {"step": 0.14}


class AudioManager:
    def __init__(self) -> None:
        self.enabled = False
        self.music_on = False
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self._volumes = {
            "select": 0.5, "step": 0.30, "pickup": 0.7, "hint": 0.6,
            "count": 0.55, "go": 0.65, "win": 0.8, "lose": 0.8,
        }
        self._last: Dict[str, float] = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        except pygame.error:
            return  # no audio device: stay silent
        self._load_assets()
        self.enabled = True

    # ------------------------------------------------------------- loading
    def _load_assets(self) -> None:
        if not any(SOUNDS_DIR.glob("*.wav")):
            self._synthesize()
        for path in sorted(SOUNDS_DIR.glob("*.wav")):
            try:
                self.sounds[path.stem] = pygame.mixer.Sound(str(path))
            except pygame.error:
                continue
        for name, snd in self.sounds.items():
            snd.set_volume(self._volumes.get(name, 0.6))

    @staticmethod
    def _synthesize() -> bool:
        """Run the stdlib synthesizer once to create missing assets."""
        if not GEN_SCRIPT.exists():
            return False
        try:
            subprocess.run(
                [sys.executable, str(GEN_SCRIPT)],
                check=True, timeout=90,
                capture_output=True,
            )
        except Exception:
            return False
        return any(SOUNDS_DIR.glob("*.wav"))

    # -------------------------------------------------------------- effects
    def play(self, name: str) -> None:
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        now = time.monotonic()
        min_gap = _RATES.get(name)
        if min_gap is not None:
            if now - self._last.get(name, -min_gap) < min_gap:
                return
            self._last[name] = now
        snd.play()

    # --------------------------------------------------------------- music
    def play_music(self, volume: float = 0.30) -> None:
        music = SOUNDS_DIR / "music.wav"
        if not self.enabled or self.music_on or not music.exists():
            return
        try:
            pygame.mixer.music.load(str(music))
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops=-1)
            self.music_on = True
        except pygame.error:
            pass

    def duck_music(self, ducked: bool) -> None:
        if self.enabled and self.music_on:
            try:
                pygame.mixer.music.set_volume(0.10 if ducked else 0.30)
            except pygame.error:
                pass

    def stop_music(self) -> None:
        if self.enabled and self.music_on:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
            self.music_on = False
