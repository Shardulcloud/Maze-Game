"""Synthesize the game's sound assets as .wav files -- pure stdlib, no numpy.

Why synthesize?  Zero external downloads, tiny files, and the sounds are
tuned to the game (short blips for movement/UI, an arpeggio for victory, an
ambient pad loop for music).  The game auto-runs this script on first launch
if the assets are missing, and runs fine (silently) without any of them.

Usage:  python tools/generate_sounds.py
Output: assets/sounds/*.wav
"""
from __future__ import annotations

import math
import wave
from array import array
from pathlib import Path

SR = 22050  # sample rate; plenty for these sounds, keeps files tiny
OUT = Path(__file__).resolve().parents[1] / "assets" / "sounds"

SINE = (1, 1.0)          # harmonic: (multiple, amplitude)


def _clamp(v: float) -> float:
    return -1.0 if v < -1.0 else (1.0 if v > 1.0 else v)


def tone(
    freq: float,
    dur: float,
    vol: float = 0.8,
    attack: float = 0.005,
    release: float = 0.05,
    harmonics=((1, 1.0),),
    slide: float = 0.0,
) -> array:
    """One note as a sum of harmonics with a trapezoid envelope.

    ``slide`` sweeps the frequency up (e.g. 1.0 = +100% across the note).
    """
    n = int(SR * dur)
    out = array("h", bytes(2 * n))
    for i in range(n):
        t = i / SR
        env = 1.0
        if attack > 0 and t < attack:
            env *= t / attack
        rem = dur - t
        if release > 0 and rem < release:
            env *= rem / release
        f = freq * (1.0 + slide * t / dur)
        phase = 2.0 * math.pi * f * t
        s = 0.0
        for mult, amp in harmonics:
            s += amp * math.sin(phase * mult)
        out[i] = int(_clamp(s * 0.9) * env * vol * 32767)
    return out


def silence(dur: float) -> array:
    return array("h", bytes(2 * int(SR * dur)))


def concat(*parts: array) -> array:
    out = array("h")
    for p in parts:
        out.extend(p)
    return out


def chord(freqs, dur: float, vol: float) -> array:
    """A soft pad: stacked sines with a slow attack/release + gentle tremolo.

    The envelope reaches silence at both ends, so the exported loop (two
    chords) butts together without a click.
    """
    n = int(SR * dur)
    out = array("h", bytes(2 * n))
    attack = release = 1.2
    for i in range(n):
        t = i / SR
        env = 1.0
        if t < attack:
            env *= t / attack
        rem = dur - t
        if rem < release:
            env *= rem / release
        trem = 0.8 + 0.2 * math.sin(2 * math.pi * 0.3 * t)
        s = 0.0
        for f in freqs:
            s += math.sin(2 * math.pi * f * t) + 0.35 * math.sin(4 * math.pi * f * t)
        out[i] = int(_clamp(s * env * trem * vol / len(freqs)) * 32767)
    return out


def write(name: str, samples: array) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(samples.tobytes())
    print(f"  wrote {path.relative_to(OUT.parent.parent)} ({path.stat().st_size} bytes)")


def main() -> None:
    print("Synthesizing sound assets ...")
    write("select.wav", tone(700, 0.06, 0.5))
    write("step.wav", tone(170, 0.05, 0.30, harmonics=((1, 1.0), (2, 0.3))))
    write("pickup.wav", concat(tone(660, 0.07, 0.7), tone(990, 0.10, 0.7)))
    write(
        "hint.wav",
        tone(
            320, 0.35, 0.6, attack=0.03, release=0.12, slide=1.8,
            harmonics=((1, 1.0), (1.007, 0.6)),
        ),
    )
    write("count.wav", tone(440, 0.09, 0.55))
    write("go.wav", tone(880, 0.22, 0.65))
    write(
        "win.wav",
        concat(
            tone(523.25, 0.12, 0.7),
            tone(659.25, 0.12, 0.7),
            tone(783.99, 0.12, 0.7),
            tone(1046.50, 0.40, 0.55, release=0.30),
        ),
    )
    write(
        "lose.wav",
        concat(
            tone(392.00, 0.16, 0.6, release=0.10),
            tone(311.13, 0.16, 0.6, release=0.10),
            tone(246.94, 0.30, 0.55, release=0.20),
        ),
    )
    # 8-second ambient loop: Am(add9)-ish -> Fmaj7-ish, very quiet.
    music = concat(
        chord((110.00, 164.81, 220.00, 246.94), 4.0, 0.16),
        chord((87.31, 130.81, 174.61, 220.00), 4.0, 0.16),
    )
    write("music.wav", music)
    print("Done.")


if __name__ == "__main__":
    main()
