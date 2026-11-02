"""Game configuration: window, palette, tuning knobs, menu options.

Importing this module does NOT import pygame (only maze direction constants
for the key maps), so unit tests can import it freely.
"""
from __future__ import annotations

# ------------------------------------------------------------------ window
FPS = 60
WINDOW_W, WINDOW_H = 1280, 800
HUD_H = 44           # top bar height (HUD lives here)
TILE_MIN = 10        # never render tiles smaller than this

# ------------------------------------------------------------------ tuning
PLAYER_SPEED = 8.0          # tiles per second
COUNTDOWN = 3.0             # seconds of 3-2-1-GO
GEN_ANIM_DURATION = 3.0     # "watch the algorithm build it" replay length
HINT_DURATION = 2.5         # seconds an A* hint path stays on screen
COLLECTIBLE_DENSITY = 1 / 55  # coins per cell
RACE_DIST_INTERVAL = 0.4      # seconds between live "steps to exit" A* runs
FOG_RADIUS = {
    "solo": 4.5,           # solo: explore with a decent lantern
    "coop_nav": 5.5,        # co-op navigator: big lantern + memory
    "coop_runner": 2.5,     # co-op runner: tiny lantern, NO memory
}

# ------------------------------------------------------------------- menu
MODES = (
    ("solo", "Solo Run"),
    ("race", "Race (2P)"),
    ("coop", "Co-op Split-Screen (2P)"),
)
MODE_LABELS = dict(MODES)

SIZES = (
    ("small", "Small 21x15"),
    ("medium", "Medium 31x21"),
    ("large", "Large 45x31"),
    ("huge", "Huge 61x41"),
)
SIZE_CELLS = {
    "small": (21, 15),
    "medium": (31, 21),
    "large": (45, 31),
    "huge": (61, 41),
}

# ------------------------------------------------------------------ colors
BG = (10, 11, 16)
FLOOR = (26, 28, 38)
GRID_DOT = (36, 39, 52)
WALL = (147, 153, 178)
PLAYER1 = (86, 214, 255)     # cyan
PLAYER2 = (255, 168, 64)    # orange
EXIT = (110, 255, 170)      # green portal
COIN = (255, 212, 92)
HINT = (186, 160, 255)
TEXT = (232, 234, 242)
DIM = (148, 152, 168)
GOOD = (110, 255, 170)
BAD = (255, 110, 110)
MENU_ACCENT = (255, 122, 180)

FOG_RGB = (6, 7, 11)
FOG_OPAQUE_A = 243   # unexplored: nearly black, faint ghost of the walls
FOG_MEMORY_A = 168   # explored but not currently visible: dim memory

HUD_BG = (14, 15, 22, 216)
OVERLAY_BG = (8, 9, 14, 216)
