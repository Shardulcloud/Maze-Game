"""Game modes: Solo Run, Race, and Co-op Split-Screen.

A mode owns the *rules*: players, collectibles, fog configuration, win
conditions, hints, HUD lines, and results.  It is rendering-agnostic (it
talks in grid cells and world pixels only), so ``main`` stays a thin shell:
state machine + input + drawing.

The fog configurations per mode:

* Solo   -- fog of war with memory: you see a lantern radius now, and dimly
            remember everywhere you have been.
* Race   -- no fog: both players see the full maze, it's a fair sprint.
* Co-op  -- the showcase mode, split screen with asymmetric information:
            the Navigator (P1, left viewport) explores with a big lantern and
            memory; the Runner (P2, right viewport) sees only a tiny circle
            around themselves, no memory.  Talking is required.

Hints (press H): A* from the active player to the exit, limited uses, shown
for a few seconds.  Race has none (it would be unfair); instead it shows live
"steps to exit" for both players, recomputed by A* a few times per second.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from game import config as C
from game.effects import Effects
from game.player import K_ARROWS, K_WASD, Player
from game.visibility import explore, visible_cells
from maze import Grid, astar
from maze.grid import DELTA


def fmt_time(t: float) -> str:
    if t < 60.0:
        return f"{t:.1f}s"
    return f"{int(t // 60)}:{t % 60:04.1f}"


class GameMode:
    # Class-level configuration each mode overrides.
    id = "base"
    uses_fog = False
    split_screen = False
    hints_default = 0

    def __init__(self, grid: Grid, seed: int, tile: int) -> None:
        self.grid = grid
        self.tile = tile
        self.seed = seed
        self.rng = random.Random(seed ^ 0xC0FFEE)
        self.exit: Tuple[int, int] = (grid.width - 1, grid.height - 1)
        self.players: List[Player] = []
        self.collectibles: Set[Tuple[int, int]] = set()
        self.timer = 0.0
        self.finished = False
        self.finish_time: Optional[float] = None
        self.winner_text = ""
        self.hint: Optional[Tuple[List[Tuple[int, int]], float]] = None
        self.hints_left = self.hints_default
        self.draw_offsets: Dict[int, Tuple[float, float]] = {}

    # ---------------------------------------------------------------- setup
    def _add_player(self, x: int, y: int, color, keys, name) -> Player:
        p = Player(x, y, color, keys, name, speed=C.PLAYER_SPEED)
        self.players.append(p)
        return p

    def _place_collectibles(self, count: int, avoid: Sequence[Tuple[int, int]],
                            min_dist: int = 6) -> None:
        """Random open cells, far from the starts, never on the exit."""
        starts = list(avoid)
        cands = []
        for cell in self.grid.cells_iter():
            if cell == self.exit:
                continue
            if any(abs(cell[0] - s[0]) + abs(cell[1] - s[1]) < min_dist for s in starts):
                continue
            cands.append(cell)
        self.rng.shuffle(cands)
        self.collectibles = set(cands[:count])

    @property
    def coin_total(self) -> int:
        return len(self.collectibles) + sum(p.score for p in self.players) // 100

    # --------------------------------------------------------------- update
    def update(self, dt: float, keystate, audio, fx: Effects) -> None:
        if self.finished:
            return
        self.timer += dt
        for p in self.players:
            p.update(dt, self.grid, keystate)
            if p.take_arrived():
                self._on_arrive(p, audio, fx)
        if self.hint is not None and self.timer > self.hint[1]:
            self.hint = None
        self._tick(dt)

    def _tick(self, dt: float) -> None:
        pass

    # -------------------------------------------------------- event helpers
    def _pickup(self, p: Player, audio, fx) -> bool:
        cell = p.tile
        if cell in self.collectibles:
            self.collectibles.discard(cell)
            p.score += 100
            wx = (cell[0] + 0.5) * self.tile
            wy = (cell[1] + 0.5) * self.tile
            fx.burst(wx, wy, C.COIN, n=16, speed=110)
            fx.shake_add(1.5)
            audio.play("pickup")
            return True
        return False

    def _finish(self, winner: str, audio, fx) -> None:
        self.finished = True
        self.finish_time = self.timer
        self.winner_text = winner
        wx = (self.exit[0] + 0.5) * self.tile
        wy = (self.exit[1] + 0.5) * self.tile
        fx.confetti(wx, wy, [C.PLAYER1, C.PLAYER2, C.COIN, C.EXIT, C.HINT], n=70)
        fx.shake_add(6)
        audio.play("win")

    # ---------------------------------------------------------------- hints
    @property
    def hint_player(self) -> Optional[Player]:
        return self.players[0] if self.players else None

    def request_hint(self, audio) -> bool:
        p = self.hint_player
        if self.finished or self.hints_left <= 0 or p is None:
            return False
        res = astar(self.grid, p.tile, self.exit)
        if not res.found:
            return False
        self.hints_left -= 1
        self.hint = (res.path, self.timer + C.HINT_DURATION)
        audio.play("hint")
        return True

    @property
    def hint_frac_left(self) -> float:
        if self.hint is None:
            return 0.0
        _, until = self.hint
        return max(0.0, (until - self.timer) / C.HINT_DURATION)

    # ------------------------------------------------------------------ fog
    def fog_states(self) -> List[Tuple[Optional[Set[Tuple]], Optional[Set[Tuple]]]]:
        """Per viewport: (explored memory set or None, visible set or None)."""
        return [(None, None)]

    # ------------------------------------------------------------------ hud
    def hud(self) -> List[Tuple[str, tuple]]:
        raise NotImplementedError

    def results(self) -> Tuple[str, tuple, List[Tuple[str, str]]]:
        raise NotImplementedError

    def controls_help(self) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------- solo
class SoloMode(GameMode):
    id = "solo"
    uses_fog = True
    hints_default = 3

    def __init__(self, grid: Grid, seed: int, tile: int) -> None:
        super().__init__(grid, seed, tile)
        self._add_player(0, 0, C.PLAYER1, K_WASD, "Runner")
        n = max(3, grid.cell_count // 55)
        self._place_collectibles(n, avoid=[(0, 0)])
        self.explored: Set[Tuple[int, int]] = set()
        self._reveal(self.players[0])
        res = astar(grid, (0, 0), self.exit)
        self.optimal = res.length if res.found else 0

    def _reveal(self, p: Player) -> None:
        explore(self.grid, self.explored, p.gx, p.gy, C.FOG_RADIUS["solo"])

    def _on_arrive(self, p: Player, audio, fx: Effects) -> None:
        self._pickup(p, audio, fx)
        self._reveal(p)
        if p.tile == self.exit:
            self._finish("ESCAPED!", audio, fx)

    def fog_states(self):
        vis = visible_cells(self.grid, self.players[0].gx, self.players[0].gy,
                            C.FOG_RADIUS["solo"])
        return [(self.explored, vis)]

    def hud(self):
        p = self.players[0]
        segs = [
            (f"TIME {fmt_time(self.timer)}", C.TEXT),
            (f"COINS {p.score // 100}/{self.coin_total}", C.COIN),
        ]
        if self.hints_default:
            segs.append((f"HINTS {self.hints_left} [H]", C.HINT))
        return segs

    def results(self):
        p = self.players[0]
        steps = max(1, p.steps)
        eff = 100.0 * self.optimal / steps if self.optimal else 0.0
        lines = [
            ("Time", fmt_time(self.finish_time or 0.0)),
            ("Coins", f"{p.score // 100}/{self.coin_total}"),
            ("Your steps", str(p.steps)),
            ("Optimal path (A*)", str(self.optimal)),
            ("Route efficiency", f"{eff:.0f}%"),
        ]
        return "YOU ESCAPED!", C.GOOD, lines

    def controls_help(self):
        return "WASD move - H hint - ESC pause"


# --------------------------------------------------------------------- race
class RaceMode(GameMode):
    id = "race"
    hints_default = 0

    def __init__(self, grid: Grid, seed: int, tile: int) -> None:
        super().__init__(grid, seed, tile)
        self._add_player(0, 0, C.PLAYER1, K_WASD, "Player 1")
        self._add_player(0, 0, C.PLAYER2, K_ARROWS, "Player 2")
        self.draw_offsets = {1: (0.22, 0.12)}
        n = max(3, grid.cell_count // 70)
        self._place_collectibles(n, avoid=[(0, 0)])
        self._dist = [-1, -1]
        self._dist_t = 0.0

    def _on_arrive(self, p: Player, audio, fx: Effects) -> None:
        self._pickup(p, audio, fx)
        if p.tile == self.exit:
            idx = self.players.index(p)
            self._finish(f"PLAYER {idx + 1} WINS!", audio, fx)

    def _tick(self, dt: float) -> None:
        self._dist_t -= dt
        if self._dist_t <= 0.0:
            self._dist_t = C.RACE_DIST_INTERVAL
            for i, p in enumerate(self.players):
                res = astar(self.grid, p.tile, self.exit)
                self._dist[i] = res.length if res.found else -1

    def hud(self):
        segs = [(f"TIME {fmt_time(self.timer)}", C.TEXT)]
        for i, p in enumerate(self.players):
            d = self._dist[i]
            label = f"P{i+1} {d} steps" if d >= 0 else f"P{i+1} --"
            segs.append((label, p.color))
        segs.append((f"COINS {self.players[0].score // 100}/{self.players[1].score // 100}", C.COIN))
        return segs

    def results(self):
        p1, p2 = self.players
        t = self.finish_time or 0.0
        win_idx = 0 if p1.score >= 0 and self.winner_text == "PLAYER 1 WINS!" else 1
        banner = self.winner_text
        color = self.players[win_idx].color
        lines = [
            ("Time", fmt_time(t)),
            ("P1 coins / steps", f"{p1.score // 100} / {p1.steps}"),
            ("P2 coins / steps", f"{p2.score // 100} / {p2.steps}"),
            ("Maze", f"{self.grid.width}x{self.grid.height} seed {self.seed}"),
        ]
        return banner, color, lines

    def controls_help(self):
        return "P1: WASD   P2: arrows - ESC pause"


# --------------------------------------------------------------------- coop
class CoopMode(GameMode):
    id = "coop"
    uses_fog = True
    split_screen = True
    hints_default = 2

    def __init__(self, grid: Grid, seed: int, tile: int) -> None:
        super().__init__(grid, seed, tile)
        # Both start in the same corner; roles diverge via their viewports.
        self._add_player(0, 0, C.PLAYER1, K_WASD, "Navigator")
        self._add_player(0, 0, C.PLAYER2, K_ARROWS, "Runner")
        self.draw_offsets = {1: (0.22, 0.12)}
        n = max(3, grid.cell_count // 60)
        self._place_collectibles(n, avoid=[(0, 0)])
        self.nav_explored: Set[Tuple[int, int]] = set()
        self._reveal_nav()
        res = astar(grid, (0, 0), self.exit)
        self.optimal = res.length if res.found else 0

    @property
    def nav(self) -> Player:
        return self.players[0]

    @property
    def runner(self) -> Player:
        return self.players[1]

    @property
    def hint_player(self) -> Player:
        return self.runner

    def _reveal_nav(self) -> None:
        explore(self.grid, self.nav_explored, self.nav.gx, self.nav.gy,
                C.FOG_RADIUS["coop_nav"])

    def _on_arrive(self, p: Player, audio, fx: Effects) -> None:
        if p is self.nav:
            self._reveal_nav()
        else:
            # Only the runner picks up coins (tension: the navigator can't).
            self._pickup(p, audio, fx)
            if p.tile == self.exit:
                self._finish("TEAM ESCAPED!", audio, fx)

    def fog_states(self):
        nav_vis = visible_cells(self.grid, self.nav.gx, self.nav.gy,
                                C.FOG_RADIUS["coop_nav"])
        run_vis = visible_cells(self.grid, self.runner.gx, self.runner.gy,
                                C.FOG_RADIUS["coop_runner"])
        return [(self.nav_explored, nav_vis), (None, run_vis)]

    def hud(self):
        segs = [
            (f"TIME {fmt_time(self.timer)}", C.TEXT),
            (f"COINS {self.runner.score // 100}/{self.coin_total}", C.COIN),
            (f"HINTS {self.hints_left} [H]", C.HINT),
        ]
        return segs

    def results(self):
        r = self.runner
        steps = max(1, r.steps)
        eff = 100.0 * self.optimal / steps if self.optimal else 0.0
        lines = [
            ("Time", fmt_time(self.finish_time or 0.0)),
            ("Coins (runner)", f"{r.score // 100}/{self.coin_total}"),
            ("Runner steps / optimal", f"{r.steps} / {self.optimal}"),
            ("Route efficiency", f"{eff:.0f}%"),
            ("Navigator revealed", f"{len(self.nav_explored)} cells"),
        ]
        return "TEAM ESCAPED!", C.GOOD, lines

    def controls_help(self):
        return "NAV (left, WASD) explores - RUNNER (right, arrows) escapes - H hint"


MODE_CLASSES = {cls.id: cls for cls in (SoloMode, RaceMode, CoopMode)}
