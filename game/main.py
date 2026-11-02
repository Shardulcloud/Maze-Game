"""Maze Runner -- entry point and game shell.

Run::

    python -m game.main                 # menu
    python -m game.main --mode coop     # jump straight into co-op
    python -m game.main --smoke        # headless self-test (CI / no display)

States: MENU -> GENERATING -> COUNTDOWN -> PLAYING -> (PAUSED) -> FINISHED.
The shell is deliberately thin: rules live in game_modes, drawing in
renderer, algorithms in the ``maze`` package.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

if __package__ in (None, ""):  # allow `python game/main.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame

from game import config as C
from game.audio import AudioManager
from game.effects import Effects, GenerationAnimation
from game.game_modes import MODE_CLASSES, fmt_time
from game.player import K_ARROWS, K_WASD
from game.renderer import (
    Camera,
    FogLayer,
    build_surface,
    draw_coin,
    draw_exit,
    draw_hint_path,
    draw_player,
    make_glow,
    paint_event,
)
from maze import GENERATOR_LABELS, bfs, generate, initial_state
from maze.rng import random_seed

# States
MENU, GENERATING, COUNTDOWN, PLAYING, PAUSED, FINISHED = range(6)

SHOT_DIR = Path(__file__).resolve().parents[1] / "assets" / "screenshots"


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Maze Runner -- procedural mazes & pathfinding")
        self.screen = pygame.display.set_mode((C.WINDOW_W, C.WINDOW_H))
        self.clock = pygame.time.Clock()
        self.font_banner = pygame.font.Font(None, 72)
        self.font_l = pygame.font.Font(None, 46)
        self.font_m = pygame.font.Font(None, 30)
        self.font_s = pygame.font.Font(None, 22)
        self.audio = AudioManager()

        self.running = True
        self.state = MENU
        self.t_global = 0.0

        # Menu state.
        self.gens = list(GENERATOR_LABELS.items())
        self.menu_idx = 0
        self.menu_values = {"mode": 0, "size": 1, "gen": 0}
        self.seed = random_seed()
        self._build_menu_bg()

        # Current-game context.
        self.mode = None
        self.grid = None
        self.tile = 0
        self.maze_surf = None
        self.anim = None
        self.viewports: List[Camera] = []
        self.fogs: List[Optional[FogLayer]] = []
        self.fx = Effects()
        self.gen_label = ""
        self.exit_glow = None
        self.player_glows = []
        self.countdown_t = 0.0
        self._count_last = -1

        # Cached HUD strip.
        self._hud_bg = pygame.Surface((C.WINDOW_W, C.HUD_H), pygame.SRCALPHA)
        self._hud_bg.fill(C.HUD_BG)
        self._dim = pygame.Surface((C.WINDOW_W, C.WINDOW_H), pygame.SRCALPHA)
        self._dim.fill((*C.BG, 200))

    # ----------------------------------------------------------------- menu
    def _build_menu_bg(self) -> None:
        """Attract mode: a dim maze with a glowing dot walking a BFS path."""
        grid = generate(41, 23, method="dfs", seed=7)
        tile = max(10, min((C.WINDOW_W - 40) // 41, (C.WINDOW_H - 60) // 23) // 2)
        self._menu_surf = build_surface(grid, tile)
        self._menu_tile = tile
        res = bfs(grid, (0, 0), (40, 22))
        self._menu_path = res.path if res.found else [(0, 0)]
        self._menu_glow = make_glow(tile * 0.4, C.PLAYER1)
        self._menu_exit = (40, 22)

    def _menu_rows(self):
        return [
            ("Mode", [label for _, label in C.MODES], self.menu_values["mode"]),
            ("Maze size", [label for _, label in C.SIZES], self.menu_values["size"]),
            ("Generator", [label for _, label in self.gens], self.menu_values["gen"]),
            ("Seed", [str(self.seed)], 0),
        ]

    def _menu_advance(self, delta: int) -> None:
        self.menu_idx = (self.menu_idx + delta) % len(self._menu_rows())
        self.audio.play("select")

    def _menu_change(self, delta: int) -> None:
        row = self._menu_rows()[self.menu_idx]
        name = row[0]
        if name == "Seed":
            self.seed = random_seed()
        else:
            key = {"Mode": "mode", "Maze size": "size", "Generator": "gen"}[name]
            n = len(row[1])
            self.menu_values[key] = (self.menu_values[key] + delta) % n
        self.audio.play("select")

    # ---------------------------------------------------------- game set-up
    def _start_game(self, mode_key: Optional[str] = None, animate: bool = True) -> None:
        mk = mode_key or C.MODES[self.menu_values["mode"]][0]
        size_key = C.SIZES[self.menu_values["size"]][0]
        w, h = C.SIZE_CELLS[size_key]
        gen_key, gen_label = self.gens[self.menu_values["gen"]]
        mode_cls = MODE_CLASSES[mk]

        events: List[Tuple] = []
        grid = generate(
            w, h, gen_key, self.seed,
            on_carve=lambda x, y, d: events.append(("carve", x, y, d)),
            on_wall=lambda x, y, d: events.append(("wall", x, y, d)),
        )
        if mode_cls.split_screen:
            tile = max(
                C.TILE_MIN,
                min((C.WINDOW_W // 2 - 12) // w, (C.WINDOW_H - C.HUD_H - 8) // h),
            )
        else:
            tile = max(
                C.TILE_MIN,
                min((C.WINDOW_W - 16) // w, (C.WINDOW_H - C.HUD_H - 8) // h),
            )

        self.grid, self.tile, self.gen_label = grid, tile, gen_label
        self.maze_surf = build_surface(grid, tile, initial=initial_state(gen_key))
        self.mode = mode_cls(grid, self.seed, tile)
        self.fx = Effects()
        self.exit_glow = make_glow(tile * 0.55, C.EXIT, 60)
        self.player_glows = [make_glow(tile * 0.34, p.color) for p in self.mode.players]

        world_w, world_h = w * tile, h * tile
        if self.mode.split_screen:
            vw = (C.WINDOW_W - 6) // 2
            vh = C.WINDOW_H - C.HUD_H
            self.viewports = [
                Camera(0, C.HUD_H, vw, vh, world_w, world_h),
                Camera(vw + 6, C.HUD_H, C.WINDOW_W - vw - 6, vh, world_w, world_h),
            ]
        else:
            self.viewports = [
                Camera(0, C.HUD_H, C.WINDOW_W, C.WINDOW_H - C.HUD_H, world_w, world_h)
            ]
        for cam in self.viewports:
            cam.center_world()
        self.fogs = [
            FogLayer(grid, tile) if self.mode.uses_fog else None
            for _ in self.viewports
        ]

        if events and animate:
            self.anim = GenerationAnimation(events, C.GEN_ANIM_DURATION)
            self.state = GENERATING
        else:
            if events:  # animate=False: paint everything, skip the show
                gen_anim = GenerationAnimation(events, 0.0)
                gen_anim.skip(self._paint_event)
            self.anim = None
            self._begin_countdown()

    def _paint_event(self, kind: str, x: int, y: int, d: int) -> None:
        paint_event(self.maze_surf, self.tile, kind, x, y, d)

    def _begin_countdown(self) -> None:
        self.state = COUNTDOWN
        self.countdown_t = C.COUNTDOWN
        self._count_last = int(math.ceil(C.COUNTDOWN)) + 1
        self.audio.play_music()

    def _restart(self, new_seed: bool, animate: bool = False) -> None:
        if new_seed:
            self.seed = random_seed()
        self._start_game(animate=animate)

    # -------------------------------------------------------------- helpers
    def _blit_center(self, surf: pygame.Surface, y: int, color_key=None) -> None:
        x = (C.WINDOW_W - surf.get_width()) // 2
        self.screen.blit(surf, (x, y))

    def _text(self, text: str, font: pygame.font.Font, color) -> pygame.Surface:
        return font.render(text, True, color)

    def _screenshot(self, name: str) -> None:
        try:
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.screen, str(SHOT_DIR / name))
            print(f"[smoke] saved {SHOT_DIR / name}")
        except pygame.error as exc:
            print(f"[smoke] screenshot failed: {exc}")

    # --------------------------------------------------------------- update
    def _update_state(self, dt: float) -> None:
        if self.state == GENERATING and self.anim is not None:
            self.anim.update(dt, self._paint_event)
            if self.anim.done:
                self.anim = None
                self._begin_countdown()
        elif self.state == COUNTDOWN:
            self.countdown_t -= dt
            n = int(math.ceil(max(0.0, self.countdown_t)))
            if n != self._count_last and n >= 1:
                self._count_last = n
                self.audio.play("count")
            if self.countdown_t <= 0:
                self.state = PLAYING
                self.audio.play("go")
        elif self.state == PLAYING:
            self.mode.update(dt, pygame.key.get_pressed(), self.audio, self.fx)
            self.fx.update(dt)
            if self.mode.finished:
                self.state = FINISHED

    def _update_cameras(self) -> None:
        players = self.mode.players
        tile = self.tile
        if self.mode.split_screen:
            self.viewports[0].center((players[0].rx + 0.5) * tile, (players[0].ry + 0.5) * tile)
            self.viewports[1].center((players[1].rx + 0.5) * tile, (players[1].ry + 0.5) * tile)
        elif len(players) == 2:
            mx = (players[0].rx + players[1].rx) / 2 + 0.5
            my = (players[0].ry + players[1].ry) / 2 + 0.5
            self.viewports[0].center(mx * tile, my * tile)
        else:
            self.viewports[0].center((players[0].rx + 0.5) * tile, (players[0].ry + 0.5) * tile)
        shake = self.fx.shake.offset()
        for cam in self.viewports:
            cam.sx, cam.sy = shake

    def _update_fogs(self) -> None:
        # Fog is only *drawn* in COUNTDOWN/PLAYING/PAUSED, so only rebuild it
        # there.  GENERATING never shows fog; FINISHED lifts it (full reveal
        # behind the results panel).
        if not self.mode.uses_fog or self.state not in (COUNTDOWN, PLAYING, PAUSED):
            return
        states = self.mode.fog_states()
        for i, (fog, fstate) in enumerate(zip(self.fogs, states)):
            p = self.mode.players[i]
            explored, visible = fstate
            key = (p.gx, p.gy, len(explored) if explored else 0)
            fog.maybe_rebuild(key, explored, visible)

    # ----------------------------------------------------------------- draw
    def _draw_world(self, show_entities: bool, show_fog: bool) -> None:
        self._update_cameras()
        self._update_fogs()
        mode, tile = self.mode, self.tile
        for i, cam in enumerate(self.viewports):
            cam.blit(self.screen, self.maze_surf)
            if show_entities:
                for cell in mode.collectibles:
                    phase = (cell[0] * 7 + cell[1] * 13) * 0.7
                    draw_coin(self.screen, cam, cell, tile, self.t_global, phase)
                draw_exit(self.screen, cam, mode.exit, tile, self.t_global, self.exit_glow)
            for j, p in enumerate(mode.players):
                draw_player(
                    self.screen, cam, p, tile, self.player_glows[j],
                    mode.draw_offsets.get(j, (0.0, 0.0)),
                )
            self.fx.parts.draw(self.screen, cam)
            if show_fog and self.fogs[i] is not None and self.state != FINISHED:
                self.fogs[i].draw(self.screen, cam)
        if mode.hint is not None:
            for cam in self.viewports:
                draw_hint_path(
                    self.screen, cam, mode.hint[0], tile,
                    self.t_global, mode.hint_frac_left,
                )
        if mode.split_screen:
            x = self.viewports[0].view_w + 3
            pygame.draw.line(
                self.screen, C.WALL, (x, C.HUD_H), (x, C.WINDOW_H), 3
            )

    def _draw_hud(self) -> None:
        self.screen.blit(self._hud_bg, (0, 0))
        x = 14
        for text, color in self.mode.hud():
            surf = self.font_s.render(text, True, color)
            self.screen.blit(surf, (x, (C.HUD_H - surf.get_height()) // 2))
            x += surf.get_width() + 26
        right = f"{self.gen_label} - seed {self.seed} - {self.mode.id}"
        surf = self.font_s.render(right, True, C.DIM)
        self.screen.blit(surf, (C.WINDOW_W - surf.get_width() - 12, (C.HUD_H - surf.get_height()) // 2))

    def _draw_menu(self) -> None:
        scr = self.screen
        scr.fill(C.BG)
        surf = self._menu_surf
        scr.blit(
            surf,
            ((C.WINDOW_W - surf.get_width()) // 2,
             (C.WINDOW_H - surf.get_height()) // 2 + 30),
        )
        # Glowing dot walking the BFS solution.
        tile = self._menu_tile
        idx = int(self.t_global * 7.0) % len(self._menu_path)
        cx, cy = self._menu_path[idx]
        wx = (C.WINDOW_W - surf.get_width()) // 2 + (cx + 0.5) * tile
        wy = (C.WINDOW_H - surf.get_height()) // 2 + 30 + (cy + 0.5) * tile
        scr.blit(self._menu_glow, (wx - self._menu_glow.get_width() // 2,
                                   wy - self._menu_glow.get_height() // 2))
        pygame.draw.circle(scr, C.PLAYER1, (int(wx), int(wy)), max(4, tile // 3))
        ex, ey = self._menu_exit
        wx = (C.WINDOW_W - surf.get_width()) // 2 + (ex + 0.5) * tile
        wy = (C.WINDOW_H - surf.get_height()) // 2 + 30 + (ey + 0.5) * tile
        pygame.draw.circle(scr, C.EXIT, (int(wx), int(wy)), max(4, tile // 3))
        scr.blit(self._dim, (0, 0))

        self._blit_center(self._text("MAZE RUNNER", self.font_banner, C.TEXT), 56)
        self._blit_center(
            self._text("procedural generation x pathfinding playground", self.font_m, C.DIM), 112
        )
        y = 190
        rows = self._menu_rows()
        for i, (name, options, value) in enumerate(rows):
            selected = i == self.menu_idx
            prefix = "> " if selected else "  "
            color = C.MENU_ACCENT if selected else C.DIM
            label = self.font_l.render(prefix + name, True, color)
            scr.blit(label, (300, y))
            if selected and name != "Seed":
                vtxt = f"<  {options[value]}  >"
            elif name == "Seed":
                vtxt = f"{self.seed}   (R reroll)"
            else:
                vtxt = options[value]
            vcolor = C.TEXT if selected else C.DIM
            vsurf = self.font_l.render(vtxt, True, vcolor)
            scr.blit(vsurf, (700, y))
            y += 58
        self._blit_center(
            self._text(
                "ENTER start - UP/DOWN pick - LEFT/RIGHT change - R reroll seed - ESC quit",
                self.font_s, C.DIM,
            ),
            C.WINDOW_H - 40,
        )

    def _draw_generating(self) -> None:
        self.screen.fill(C.BG)
        show_entities = not self.mode.uses_fog
        self._draw_world(show_entities=False, show_fog=False)
        self._draw_hud()
        frac = self.anim.progress if self.anim else 1.0
        bar_w = 360
        x = (C.WINDOW_W - bar_w) // 2
        y = C.WINDOW_H - 46
        pygame.draw.rect(self.screen, C.DIM, (x, y, bar_w, 8), 1)
        pygame.draw.rect(self.screen, C.MENU_ACCENT, (x, y, int(bar_w * frac), 8))
        text = self._text(
            f"{self.gen_label}: building the maze - {int(frac * 100)}%   (SPACE skip)",
            self.font_m, C.TEXT,
        )
        self._blit_center(text, y - 40)

    def _draw_countdown(self) -> None:
        self.screen.fill(C.BG)
        show_entities = not self.mode.uses_fog
        self._draw_world(show_entities=show_entities, show_fog=self.mode.uses_fog)
        self._draw_hud()
        n = int(math.ceil(max(0.0, self.countdown_t)))
        big = self.font_banner.render(str(n) if n > 0 else "GO!", True, C.EXIT)
        self._blit_center(big, (C.WINDOW_H - C.HUD_H) // 2 - 120 + C.HUD_H)
        self._blit_center(
            self._text(self.mode.controls_help(), self.font_m, C.DIM),
            C.WINDOW_H - 60,
        )

    def _draw_playing(self) -> None:
        self.screen.fill(C.BG)
        self._draw_world(show_entities=True, show_fog=True)
        self._draw_hud()

    def _draw_paused(self) -> None:
        self._draw_playing()
        self.screen.blit(self._dim, (0, 0))
        self._blit_center(self._text("PAUSED", self.font_banner, C.TEXT), 260)
        self._blit_center(
            self._text("SPACE resume - R restart - M menu - Q quit", self.font_m, C.DIM), 340
        )

    def _draw_finished(self) -> None:
        self.screen.fill(C.BG)
        # Fog lifts: reveal the whole maze behind the results panel.
        self._draw_world(show_entities=True, show_fog=True)
        self._draw_hud()
        banner, color, lines = self.mode.results()
        panel_w, panel_h = 560, 90 + 44 * len(lines)
        px = (C.WINDOW_W - panel_w) // 2
        py = max(C.HUD_H + 20, (C.WINDOW_H - panel_h) // 2)
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill(C.OVERLAY_BG)
        pygame.draw.rect(panel, (*color, 255), (0, 0, panel_w, panel_h), 2)
        self.screen.blit(panel, (px, py))
        bs = self.font_l.render(banner, True, color)
        self.screen.blit(bs, (px + (panel_w - bs.get_width()) // 2, py + 24))
        yy = py + 84
        for label, value in lines:
            ls = self.font_m.render(label, True, C.DIM)
            vs = self.font_m.render(str(value), True, C.TEXT)
            self.screen.blit(ls, (px + 40, yy))
            self.screen.blit(vs, (px + panel_w - 40 - vs.get_width(), yy))
            yy += 44
        self._blit_center(
            self._text("SPACE replay - N new maze - M menu", self.font_m, C.DIM),
            py + panel_h + 24,
        )

    def _draw(self) -> None:
        if self.state == MENU:
            self._draw_menu()
        elif self.state == GENERATING:
            self._draw_generating()
        elif self.state == COUNTDOWN:
            self._draw_countdown()
        elif self.state == PLAYING:
            self._draw_playing()
        elif self.state == PAUSED:
            self._draw_paused()
        elif self.state == FINISHED:
            self._draw_finished()

    # ---------------------------------------------------------------- input
    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type != pygame.KEYDOWN:
                continue
            key = event.key
            st = self.state
            if st == MENU:
                if key in (pygame.K_UP, pygame.K_w):
                    self._menu_advance(-1)
                elif key in (pygame.K_DOWN, pygame.K_s):
                    self._menu_advance(1)
                elif key in (pygame.K_LEFT, pygame.K_a):
                    self._menu_change(-1)
                elif key in (pygame.K_RIGHT, pygame.K_d):
                    self._menu_change(1)
                elif key == pygame.K_r:
                    self.seed = random_seed()
                    self.audio.play("select")
                elif key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._start_game(animate=True)
                elif key == pygame.K_ESCAPE:
                    self.running = False
            elif st == GENERATING:
                if key in (pygame.K_SPACE, pygame.K_RETURN) and self.anim:
                    self.anim.skip(self._paint_event)
                    self.anim = None
                    self._begin_countdown()
            elif st == COUNTDOWN:
                pass  # hands off the keys until GO
            elif st == PLAYING:
                if key == pygame.K_ESCAPE:
                    self.state = PAUSED
                    self.audio.duck_music(True)
                elif key == pygame.K_h:
                    self.mode.request_hint(self.audio)
                elif key == pygame.K_r:
                    self._restart(new_seed=False)
                elif key == pygame.K_n:
                    self._restart(new_seed=True)
            elif st == PAUSED:
                if key in (pygame.K_SPACE, pygame.K_ESCAPE):
                    self.state = PLAYING
                    self.audio.duck_music(False)
                elif key == pygame.K_r:
                    self.audio.duck_music(False)
                    self._restart(new_seed=False)
                elif key == pygame.K_m:
                    self.audio.stop_music()
                    self.state = MENU
                elif key == pygame.K_q:
                    self.running = False
            elif st == FINISHED:
                if key in (pygame.K_SPACE, pygame.K_r):
                    self._restart(new_seed=False)
                elif key == pygame.K_n:
                    self._restart(new_seed=True)
                elif key in (pygame.K_m, pygame.K_ESCAPE):
                    self.audio.stop_music()
                    self.state = MENU

    # ------------------------------------------------------------------ run
    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(C.FPS) / 1000.0, 1 / 20.0)
            self.t_global += dt
            self._handle_events()
            if not self.running:
                break
            self._update_state(dt)
            self._draw()
            pygame.display.flip()
        self.audio.stop_music()
        pygame.quit()

    # ---------------------------------------------------------------- smoke
    def run_smoke(self) -> bool:
        """Headless end-to-end self-test.

        Exercises every generator, every mode, the generation animation, the
        countdown, gameplay movement, hints, fog, pause, and results --
        rendering a REAL frame at every step, so that a crash in ANY draw
        path (e.g. a NameError inside the fog renderer) fails here instead
        of on the player's screen.  Saves screenshots.  Run with SDL dummy
        drivers.
        """
        try:
            print("[smoke] generators x modes sanity ...")
            for gen_key, label in self.gens:
                grid = generate(15, 11, gen_key, seed=5)
                assert grid.passage_count() == 15 * 11 - 1, label

            empty = dict.fromkeys(
                list(K_WASD.values()) + list(K_ARROWS.values()), False
            )

            def ks(*held_keys):
                state = dict(empty)
                for k in held_keys:
                    state[k] = True
                return state

            def flip():
                pygame.display.flip()

            def play_and_draw(frames: int, keystate, dt: float = 1 / 60.0):
                for _ in range(frames):
                    self.mode.update(dt, keystate, self.audio, self.fx)
                    self.fx.update(dt)
                    self.t_global += dt
                    self._draw_playing()
                    flip()

            def finish(player, shot: str):
                player.set_tile(*self.mode.exit)
                player.force_arrive()
                self.mode.update(1 / 60.0, ks(), self.audio, self.fx)
                assert self.mode.finished, f"{self.mode.id} did not finish"
                self.state = FINISHED
                self._draw_finished()
                flip()
                self._screenshot(shot)

            # ---- solo: animation -> countdown -> play -> pause -> win
            print("[smoke] solo mode ...")
            self._start_game("solo", animate=True)
            assert self.anim is not None and self.state == GENERATING
            for _ in range(12):  # render the generation animation (real path)
                self.t_global += 1 / 60.0
                self._update_state(1 / 60.0)
                self._draw_generating()
                flip()
            if self.state == GENERATING:  # fast-forward remaining events
                while not self.anim.done:
                    self.anim.update(0.05, self._paint_event)
                self._update_state(1 / 60.0)  # anim done -> COUNTDOWN (real path)
            assert self.state == COUNTDOWN
            self._update_state(1 / 60.0)  # exercises the count-tick branch
            self._draw_countdown()        # fog mode: fog + players, no entities
            flip()
            self.state = PLAYING

            play_and_draw(40, ks(K_WASD[8]))   # hold West
            play_and_draw(40, ks(K_WASD[2]))   # hold East
            play_and_draw(40, ks(K_WASD[4]))   # hold South
            play_and_draw(40, ks(K_WASD[1]))   # hold North
            assert self.mode.request_hint(self.audio) and self.mode.hint
            play_and_draw(30, ks())            # hint beads above the fog
            self.state = PAUSED
            self._draw_paused()
            flip()
            self.state = PLAYING
            finish(self.mode.players[0], "solo.png")

            # ---- race: two players, live distance HUD, first to exit
            print("[smoke] race mode ...")
            self._start_game("race", animate=False)
            assert self.state == COUNTDOWN
            self._draw_countdown()  # no-fog mode: entities already visible
            flip()
            self.state = PLAYING
            play_and_draw(120, ks(K_WASD[2], K_ARROWS[2]))  # both hold East
            self.mode.request_hint(self.audio)  # race has no hints -> must fail
            assert self.mode.hint is None
            assert self.mode._dist[0] >= 0
            finish(self.mode.players[0], "race.png")

            # ---- coop: split screen, asymmetric fog, runner wins
            print("[smoke] coop mode ...")
            self._start_game("coop", animate=False)
            assert self.state == COUNTDOWN
            self._draw_countdown()  # split screen + both fog layers
            flip()
            self.state = PLAYING
            play_and_draw(60, ks(K_WASD[2]))     # navigator explores East
            play_and_draw(60, ks(K_ARROWS[2]))   # runner moves East
            assert self.mode.request_hint(self.audio)
            self.state = PAUSED
            self._draw_paused()
            flip()
            self.state = PLAYING
            finish(self.mode.runner, "coop.png")

            # HUD/results/fog-state formatting must not crash for any mode.
            print("[smoke] all modes: hud/results/fog formatting ...")
            for mk in ("solo", "race", "coop"):
                self._start_game(mk, animate=False)
                self.mode.hud()
                self.mode.results()
                self.mode.fog_states()
            print("SMOKE OK")
            return True
        except Exception as exc:  # noqa: BLE001 - smoke reports, never raises
            import traceback
            traceback.print_exc()
            print(f"SMOKE FAILED: {exc}")
            return False
        finally:
            self.audio.stop_music()
            pygame.quit()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maze-runner", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--smoke", action="store_true",
                        help="headless self-test (no window; used by CI)")
    parser.add_argument("--mode", choices=[k for k, _ in C.MODES],
                        help="start directly in this mode")
    parser.add_argument("--size", choices=list(C.SIZE_CELLS),
                        help="maze size (default: menu selection)")
    parser.add_argument("--gen", choices=list(GENERATOR_LABELS),
                        help="maze generation algorithm")
    parser.add_argument("--seed", type=int, help="fixed seed (reproducible maze)")
    args = parser.parse_args(argv)

    if args.smoke:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    game = Game()
    if args.smoke:
        return 0 if game.run_smoke() else 1

    if args.seed is not None:
        game.seed = args.seed
    if args.mode:
        game.menu_values["mode"] = [k for k, _ in C.MODES].index(args.mode)
    if args.size:
        game.menu_values["size"] = [k for k, _ in C.SIZES].index(args.size)
    if args.gen:
        game.menu_values["gen"] = [k for k, _ in GENERATOR_LABELS].index(args.gen)
    if any((args.mode, args.size, args.gen, args.seed is not None)):
        game._start_game(animate=False)

    game.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
