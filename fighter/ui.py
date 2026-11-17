"""Pygame user interface. Everything drawn with primitives; no asset pack required."""
from __future__ import annotations

import queue
import math
import random
import pygame

from .ai import AIController
from .combat import Combat, DEFAULT_HP, MAX_ENERGY, ROUND_COUNTDOWN
from .skeleton import draw as draw_stickman
from .audio import Audio, play_map_music

from .config import load_settings
from .gamepad import Gamepad, merge_state, CURSOR_SPEED
from .network import RoomClient, RoomServer
from .characters import CHARACTERS
from . import assets
from .theme import (W, H, BG, PANEL, PANEL_HI, WHITE, MUTED, BLUE, CYAN, RED,
                    GREEN, GOLD, shade, mix, font)
from . import widgets

from .pages import (MenuPage, SelectPage, ShowcasePage, SettingsPage, LanPage,
                    RoomPage)
from .arena import ArenaPage, WORLD_X_OFF


# 战斗按键 → 九键输入名。逐帧采样会漏掉短于一帧的快速点按，
# 因此战斗中额外用 KEYDOWN 事件把这些按键锁存一帧。
COMBAT_KEYS = {
    pygame.K_a: "left", pygame.K_d: "right", pygame.K_s: "down",
    pygame.K_w: "jump", pygame.K_SPACE: "jump",
    pygame.K_j: "punch", pygame.K_k: "kick", pygame.K_u: "projectile",
    pygame.K_i: "grab", pygame.K_l: "guard",
}


class GameApp(MenuPage, SelectPage, ShowcasePage, SettingsPage, LanPage, RoomPage,
              ArenaPage):
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("LAN FIGHTER | 局域网格斗")
        self.settings = load_settings()
        self.screen = None
        self.set_display()
        self.clock = pygame.time.Clock()
        self.fonts = {n: font(n) for n in (14, 15, 16, 18, 19, 20, 21, 22, 24, 25, 26,
                                           30, 38, 40, 56)}
        self.audio = Audio()
        self.combat = Combat(self.settings["map"])
        self.now = 0.
        self.effects = []
        self.last_event = -1
        self.shake = 0.
        self.practice_mode = "normal"
        # 技能训练帧数据面板记住“上一招”，收招后仍能看到完整帧数据。
        self.frame_data_move = ''
        self.running = True
        self.page = "menu"
        self.map_picker_open = False
        self.map_scroll = 0.
        # 难度浮层由设置页打开；开赛参数，改档只在下一局生效。
        self.ai_picker_open = False
        self.select_mode = "menu"   # "menu" | "lan_pick"
        self.char_p1 = "red_scarf"
        self.char_p2 = "blue_headband"
        self.select_slot = 0
        self.select_scroll = 0.0
        self.mode = "join"
        self.fields = {"nickname": self.settings["nickname"], "server_ip": self.settings["server_ip"],
                       "port": str(self.settings["port"])}
        self.focus = None
        # Last drawn rect of each text field, used to position the IME window.
        self.field_rects = {}
        # Keep SDL text input off while playing: with a Chinese IME active,
        # composition mode swallows letter keys (A/D/S/W never reach pygame).
        # It is re-enabled only while a text field is focused.
        self.text_input_on = True
        self.sync_text_input()
        self.controls = []
        self.notice = ""
        self.notice_until = 0
        self.server: RoomServer | None = None
        self.client: RoomClient | None = None
        self.players = []
        self.ready = False
        self.fighters = self.combat.fighters
        self.game_state = self.combat.snapshot()
        self.winner = None
        self.last_input = 0
        self.dt = 1 / 60
        self.canvas = pygame.Surface((W, H))
        # set_display() builds fade_surface / scaled at the physical resolution.
        self.mouse = (0, 0)
        # 手柄：战斗中与键盘合并为同一份九键输入，菜单页驱动虚拟光标。
        self.gamepad = Gamepad()
        self.gp_cursor = [W / 2, H / 2]
        self.mouse_virtual = False
        self.last_mouse_pos = (-1, -1)
        self.page_fade = 0.
        self.last_page = "menu"
        self.button_glow = {}
        self.card_glow = {}
        self.hp_shown = [float(DEFAULT_HP), float(DEFAULT_HP)]
        self.hp_trail = [float(DEFAULT_HP), float(DEFAULT_HP)]
        self.energy_shown = [0., 0.]
        self.particles = []
        self.announcement = None
        self.combo_shown = [0, 0]
        self.combo_pop = [0., 0.]
        self.phase_seen = "game"
        self.round_seen = 1
        self.countdown_seen = False
        self.showcase_cid = "red_scarf"
        self.last_click_ms = -9999
        self.last_click_pos = (-9999, -9999)
        # 砸瓦鲁多的喊招音效所占用的人声道，前摇被打断时用来掐断声音。
        self.time_stop_channels = {}
        self.flash = 0.
        self.paused = False
        # 本帧通过 KEYDOWN 捕获到的战斗按键；合并进逐帧采样后解决快速点按丢失。
        self.press_latch = set()
        # 从暂停菜单进入设置时记录来源页面，返回时回到对局并保持暂停。
        self.settings_return = ""
        # 从暂停面板进入角色招式表时记录来源，返回时同样回到暂停中的对局。
        self.moves_return = ""
        # One AIController per fighter slot; all AI state lives on these.
        self.ai = [AIController(0, self.combat, self.settings),
                   AIController(1, self.combat, self.settings)]
        self.backdrops = {}
        self.dust = None
        self.rounded_masks = {}
        self.art_badge = {}

    def set_display(self):
        # Windowed mode keeps the plain 1100x680 surface. Fullscreen grabs the
        # real desktop resolution: pygame.SCALED is deliberately avoided
        # because repeated set_mode switches with it never take effect on some
        # Windows drivers. The upscale is done manually every frame instead,
        # either stretched edge-to-edge or aspect-fit with letterbox borders.
        if self.settings["fullscreen"]:
            info = pygame.display.Info()
            self.display_surface = pygame.display.set_mode(
                (info.current_w, info.current_h), pygame.FULLSCREEN)
        else:
            self.display_surface = pygame.display.set_mode((W, H))
        self.screen = self.display_surface
        dw, dh = self.display_surface.get_size()
        self.letterbox = self.letterbox_pos = None
        if (dw, dh) == (W, H):
            self.scale = (1., 1.)
        elif self.settings["fullscreen"]:
            # Fullscreen is always aspect-fit: one uniform scale, the spare
            # space shows as background-coloured borders (no stretching).
            s = min(dw / W, dh / H)
            self.scale = (s, s)
            tw, th = int(W * s), int(H * s)
            self.letterbox = pygame.Surface((tw, th))
            self.letterbox_pos = ((dw - tw) // 2, (dh - th) // 2)
        else:
            self.scale = (dw / W, dh / H)
        if self.scale == (1., 1.):
            self.scaled = None
        else:
            self.scaled = pygame.Surface((dw, dh))
        # Fade overlay must cover the physical resolution in fullscreen.
        self.fade_surface = pygame.Surface((dw, dh))
        self.fade_surface.fill((6, 10, 20))

    def to_logical(self, pos):
        """Map a physical-screen position onto the 1100x680 logical canvas."""
        if self.letterbox_pos is not None:
            pos = (pos[0] - self.letterbox_pos[0], pos[1] - self.letterbox_pos[1])
        sx, sy = self.scale
        return (int(pos[0] / sx), int(pos[1] / sy))

    def to_physical(self, pos):
        """逻辑画布坐标 → 物理屏幕坐标（全屏缩放 / 黑边换算的反函数）。"""
        sx, sy = self.scale
        x, y = pos[0] * sx, pos[1] * sy
        if self.letterbox_pos is not None:
            x += self.letterbox_pos[0]
            y += self.letterbox_pos[1]
        return int(x), int(y)

    def post_key(self, key):
        """向事件队列投递一次 KEYDOWN，复用已有的按键处理链路。"""
        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))

    def menu_nav_active(self):
        """菜单允许手柄光标；进行中的战斗把同一手柄交给角色控制。"""
        if self.page in ("game", "result"):
            return False
        return not (self.page == "practice" and not self.paused)

    def update_pointer(self, dt):
        """真实鼠标与手柄虚拟光标二选一：谁动了就跟随谁。

        菜单页用手柄推动虚拟光标，确认键合成一次鼠标左键事件，从而复用现有的
        点击 / 双击分发；Start / Back 合成为 ESC 键事件，复用现有返回与暂停逻辑。
        """
        physical = pygame.mouse.get_pos()
        if physical != self.last_mouse_pos:
            self.last_mouse_pos = physical
            self.mouse_virtual = False
            self.mouse = self.to_logical(physical)
            self.gp_cursor = [float(self.mouse[0]), float(self.mouse[1])]
        if not self.settings.get("gamepad", True):
            self.mouse = self.to_logical(physical)
            return
        self.gamepad.update()
        if self.gamepad.escape_edge():
            self.post_key(pygame.K_ESCAPE)
        if not self.menu_nav_active():
            self.mouse = self.to_logical(physical)
            return
        dx, dy, confirm, back = self.gamepad.menu_state()
        if dx or dy:
            self.gp_cursor[0] = min(W - 1, max(0., self.gp_cursor[0] + dx * CURSOR_SPEED * dt))
            self.gp_cursor[1] = min(H - 1, max(0., self.gp_cursor[1] + dy * CURSOR_SPEED * dt))
            self.mouse_virtual = True
            self.mouse = (int(self.gp_cursor[0]), int(self.gp_cursor[1]))
        if back:
            self.post_key(pygame.K_ESCAPE)
        if confirm:
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=self.to_physical(self.gp_cursor)))

    def latch_combat_key(self, key):
        """战斗中按事件补记按下，避免快于一帧的点按被逐帧采样漏掉。"""
        if self.page not in ("game", "practice") or self.paused:
            return
        name = COMBAT_KEYS.get(key)
        if name:
            self.press_latch.add(name)

    def own_input(self):
        """键盘与手柄合并后的本地玩家输入（九键字典）。"""
        keys = pygame.key.get_pressed()
        state = {"left": bool(keys[pygame.K_a]), "right": bool(keys[pygame.K_d]),
                 "jump": bool(keys[pygame.K_w] or keys[pygame.K_SPACE]),
                 "punch": bool(keys[pygame.K_j]), "kick": bool(keys[pygame.K_k]),
                 "projectile": bool(keys[pygame.K_u]), "grab": bool(keys[pygame.K_i]),
                 "down": bool(keys[pygame.K_s]), "guard": bool(keys[pygame.K_l])}
        if self.settings.get("gamepad", True):
            state = merge_state(state, self.gamepad.poll())
        if self.press_latch:
            # 本帧捕获过 KEYDOWN 的按钮强制视为按下，哪怕采样时已经松开。
            for name in self.press_latch:
                if name in state:
                    state[name] = True
        return state

    def set_focus(self, key):
        """Move the text-input focus; committing the settings fields on blur."""
        if self.focus is not None and self.focus != key and self.page == "settings":
            self.commit_fields()
        self.focus = key

    def sync_text_input(self):
        """Enable text input (and the IME) only while a text field has focus."""
        want = self.focus is not None
        if want == self.text_input_on:
            return
        try:
            if want:
                pygame.key.start_text_input()
                rect = self.field_rects.get(self.focus)
                if rect is not None:
                    # Place the IME candidate window beside the focused field.
                    pygame.key.set_text_input_rect(rect)
            else:
                pygame.key.stop_text_input()
            self.text_input_on = want
        except (AttributeError, pygame.error):
            pass

    def text(self, value, x, y, size=22, color=WHITE, center=False, shadow=False):
        return widgets.text(self.screen, self.fonts, value, x, y, size, color, center, shadow)

    def rect(self, x, y, w, h, color=PANEL, radius=16, border=None):
        return widgets.rect(self.screen, x, y, w, h, color, radius, border)

    def key_pills(self, keys, x, y, color=CYAN, size=18, sep="→"):
        return widgets.key_pills(self.screen, self.fonts, keys, x, y, color, size, sep)

    def panel(self, x, y, w, h, color=PANEL, radius=18, border=(45, 62, 92), accent=None,
              shadow=True):
        return widgets.panel(self.screen, x, y, w, h, color, radius, border, accent, shadow)

    def button(self, label, rect, action, color=BLUE, enabled=True):
        r = pygame.Rect(rect)
        hovered = enabled and r.collidepoint(self.mouse)
        key = (label, r.x, r.y, r.width, r.height)
        glow = self.button_glow.get(key, 0.)
        glow += ((1. if hovered else 0.) - glow) * min(1., self.dt * 12)
        self.button_glow[key] = glow
        base = color if enabled else (58, 66, 84)
        bg = mix(base, (235, 245, 255), glow * .16)
        draw = r.inflate(int(8 * glow), int(6 * glow))
        pygame.draw.rect(self.screen, (5, 9, 17), draw.move(0, 4), border_radius=13)
        pygame.draw.rect(self.screen, shade(bg, .74), draw, border_radius=13)
        face = pygame.Rect(draw.x + 1, draw.y + 1, draw.width - 2, draw.height - 2)
        pygame.draw.rect(self.screen, bg, face, border_radius=12)
        sheen = pygame.Rect(face.x + 2, face.y + 2, face.width - 4, max(6, face.height // 2))
        pygame.draw.rect(self.screen, mix(bg, WHITE, .20 + .10 * glow), sheen,
                         border_radius=11)
        rim = mix(bg, WHITE, .30) if enabled else (86, 96, 118)
        pygame.draw.rect(self.screen, rim, draw, 1, border_radius=13)
        if enabled and glow > .08:
            pygame.draw.rect(self.screen, mix(base, WHITE, .55),
                             draw.inflate(2, 2), 2, border_radius=14)
            # chevron hints that the row is clickable
            chev_x = draw.right - 24
            pygame.draw.line(self.screen, mix(WHITE, base, .35),
                             (chev_x, draw.centery - 7), (chev_x + 7, draw.centery), 2)
            pygame.draw.line(self.screen, mix(WHITE, base, .35),
                             (chev_x + 7, draw.centery), (chev_x, draw.centery + 7), 2)
        self.text(label, draw.centerx, draw.centery, 22,
                  WHITE if enabled else MUTED, True, shadow=True)
        self.controls.append((r, action if enabled else None))

    def input(self, key, label, rect, maxlen=24):
        r = pygame.Rect(rect)
        self.field_rects[key] = r
        focused = self.focus == key
        pygame.draw.circle(self.screen, CYAN if focused else (96, 118, 154),
                           (r.left + 2, r.top - 16), 4)
        self.text(label, r.left + 12, r.top - 27, 19, MUTED)
        pygame.draw.rect(self.screen, (10, 16, 28), r.inflate(4, 4), border_radius=12)
        self.rect(*r, shade(PANEL_HI, .86), 10)
        inner = pygame.Rect(r.x + 3, r.y + 3, r.width - 6, r.height - 6)
        pygame.draw.rect(self.screen, mix(PANEL_HI, (10, 16, 28), .28), inner,
                         border_radius=8)
        pygame.draw.rect(self.screen, BLUE if focused else (57, 75, 105), r, 2,
                         border_radius=10)
        if focused:
            pygame.draw.rect(self.screen, CYAN, r.inflate(4, 4), 1, border_radius=12)
        txt = self.fields[key]
        self.text(txt + ("|" if focused and pygame.time.get_ticks() // 500 % 2 else ""),
                  r.x + 14, r.y + 12, 22)
        self.controls.append((r, ("focus", key, maxlen)))

    def rounded_art(self, image, radius=14):
        """Mask an already-sized surface into a rounded card."""
        size = image.get_width()
        key = (image.get_height(), size, radius)
        mask = self.rounded_masks.get(key)
        if mask is None:
            mask = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, size, size),
                             border_radius=radius)
            self.rounded_masks[key] = mask
        out = image.copy()
        out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return out

    def portrait_image(self, char_id, size):
        art = assets.cover("portraits", char_id, (size, size))
        return self.rounded_art(art, size // 10) if art is not None else None

    def draw_avatar(self, char_id, cx, cy, size, accent):
        """Round portrait if available; accent ring fallback otherwise."""
        art = self.portrait_image(char_id, size)
        if art is not None:
            rect = art.get_rect(center=(cx, cy))
            pygame.draw.circle(self.screen, shade(accent, .55), (cx, cy),
                               size // 2 + 5, 2)
            self.screen.blit(art, rect)
        else:
            radius = size // 2
            pygame.draw.circle(self.screen, shade(PANEL_HI, 1.05), (cx, cy), radius)
            pygame.draw.circle(self.screen, shade(accent, .55), (cx, cy), radius, 2)
            head = max(8, size // 5)
            hy = cy - size // 12
            pygame.draw.circle(self.screen, (17, 25, 40), (cx, hy), head)
            pygame.draw.circle(self.screen, (231, 238, 249), (cx, hy), head, 3)
            pygame.draw.circle(self.screen, accent, (cx + head // 2, hy - 1),
                               max(2, head // 4))
            neck = hy + head
            pygame.draw.line(self.screen, (231, 238, 249),
                             (cx, neck), (cx, cy + size // 4), 4)
            pygame.draw.line(self.screen, (231, 238, 249),
                             (cx - size // 5, cy + size // 4),
                             (cx + size // 5, cy + size // 4), 5)

    def build_backdrop(self, kind):
        """Pre-render the page backdrop once: gradient, art, grid, vignette."""
        surf = pygame.Surface((W, H)).convert()
        top = (18, 29, 50) if kind != "arena" else (13, 22, 40)
        bottom = (7, 11, 20)
        band = 4
        for y in range(0, H, band):
            color = mix(top, bottom, y / float(H))
            pygame.draw.rect(surf, color, (0, y, W, band))
        art = assets.cover("backgrounds", "arena" if kind == "arena" else "menu", (W, H))
        if art is not None:
            surf.blit(art, (0, 0))
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((6, 10, 20, 126))
            surf.blit(veil, (0, 0))
        else:
            glow = pygame.Surface((W, H), pygame.SRCALPHA)
            for cx, cy, radius, color in ((955, 110, 310, (38, 96, 176)),
                                          (195, 640, 310, (24, 72, 124)),
                                          (W // 2, 330, 440, (20, 46, 84))):
                for step in range(18):
                    r = radius - step * (radius // 20)
                    glow_color = (*color, int(6 + step * 1.4))
                    pygame.draw.circle(glow, glow_color, (cx, cy), max(4, r))
            surf.blit(glow, (0, 0))
            grid = pygame.Surface((W, H), pygame.SRCALPHA)
            for y in range(70, H, 60):
                pygame.draw.line(grid, (66, 100, 152, 24), (0, y), (W, y))
            for x in range(0, W, 60):
                pygame.draw.line(grid, (66, 100, 152, 20), (x, 0), (x, H))
            surf.blit(grid, (0, 0))
            beams = pygame.Surface((W, H), pygame.SRCALPHA)
            for i in range(-2, 8):
                bx = i * 150
                pygame.draw.line(beams, (90, 150, 226, 14), (bx, H), (bx + 520, 0), 2)
            surf.blit(beams, (0, 0))
        vignette = pygame.Surface((W, H), pygame.SRCALPHA)
        depth = 88
        for i in range(depth):
            alpha = int(36 * ((depth - i) / depth) ** 2)
            if alpha <= 0:
                continue
            pygame.draw.rect(vignette, (4, 7, 14, alpha),
                             (i * 2, i, W - i * 4, H - i * 2), 1)
        surf.blit(vignette, (0, 0))
        self.backdrops[kind] = surf
        return surf

    def build_dust(self):
        dust = pygame.Surface((W, H + 120), pygame.SRCALPHA)
        random.seed(7)
        for _ in range(54):
            x = random.randint(0, W)
            y = random.randint(0, H + 120)
            radius = random.choice((1, 1, 1, 2, 2, 3))
            pygame.draw.circle(dust, (155, 205, 255, random.randint(16, 56)),
                               (x, y), radius)
        random.seed()
        return dust

    def background(self, kind="menu"):
        if kind not in self.backdrops:
            self.build_backdrop(kind)
        self.screen.blit(self.backdrops[kind], (0, 0))
        if self.dust is None:
            self.dust = self.build_dust()
        offset = int((self.now * 13) % 120)
        self.screen.blit(self.dust, (0, -120 + offset))

    def header(self, title, subtitle=""):
        self.text(title, 67, 45, 40, (7, 12, 22))
        self.text(title, 65, 43, 40, WHITE)
        pygame.draw.rect(self.screen, (10, 16, 28), (65, 90, 74, 4), border_radius=2)
        pygame.draw.rect(self.screen, CYAN, (65, 89, 66, 3), border_radius=2)
        if subtitle:
            self.text(subtitle, 67, 102, 19, MUTED)

    # ---------- juice: particles, banners, announcements ----------
    def spawn_particles(self, x, y, color, count=8, speed=190, gravity=320,
                        life=.45, size=4, rise=False):
        for _ in range(count):
            if rise:
                angle = random.uniform(math.pi * 1.1, math.pi * 1.9)
            else:
                angle = random.uniform(0, math.pi * 2)
            velocity = random.uniform(speed * .35, speed)
            self.particles.append({
                "x": float(x), "y": float(y),
                "vx": math.cos(angle) * velocity, "vy": math.sin(angle) * velocity,
                "gravity": gravity, "life": life, "max": life,
                "color": color, "size": random.randint(2, size),
            })

    def announce(self, text, sub="", color=GOLD, duration=1.5):
        self.announcement = {"text": text, "sub": sub, "color": color,
                             "t": duration, "max": duration}

    def draw_banner(self):
        a = self.announcement
        if not a: return
        progress = 1 - a["t"] / a["max"]
        surf = self.fonts[56].render(a["text"], True, a["color"])
        alpha = 255 if progress < .72 else int(255 * max(0., 1 - (progress - .72) / .28))
        if progress < .22:
            scale = 1.55 - .55 * (progress / .22)
            surf = pygame.transform.smoothscale(
                surf, (max(1, int(surf.get_width() * scale)),
                       max(1, int(surf.get_height() * scale))))
        surf.set_alpha(alpha)
        rect = surf.get_rect(center=(W // 2, 322))
        pygame.draw.line(self.screen, (*a["color"],), (W // 2 - 150, 322 + 46),
                         (W // 2 + 150, 322 + 46), 2)
        self.screen.blit(surf, rect)
        if a["sub"]:
            sub = self.fonts[26].render(a["sub"], True, WHITE)
            sub.set_alpha(alpha)
            self.screen.blit(sub, sub.get_rect(center=(W // 2, 372)))

    def sync_match_state(self, phase):
        gs = self.game_state
        round_now = gs.get("round", 1)
        if self.page in ("practice", "game") and round_now != self.round_seen:
            self.round_seen = round_now
            self.combo_shown = [0, 0]
        if phase != self.phase_seen:
            if phase == "match_end":
                self.announce("K.O.", "MATCH", RED, 1.9)
                self.flash = max(self.flash, .22)
            elif phase == "round_end" and self.phase_seen == "game":
                winner = gs.get("round_winner")
                side = "CPU" if self.page == "practice" and self.practice_mode == "cpu_vs_cpu" else "PLAYER"
                self.announce("K.O.", "" if winner is None else f"{side} {winner + 1} WINS", GOLD, 1.7)
                self.flash = max(self.flash, .16)
            self.phase_seen = phase

    def draw_countdown(self):
        """Three-second pre-round countdown, then a FIGHT banner."""
        countdown = float(self.game_state.get("countdown", 0.) or 0.)
        if countdown <= 0:
            if self.countdown_seen:
                self.countdown_seen = False
                self.announce("FIGHT!", "", GOLD, .95)
                self.flash = max(self.flash, .10)
            return
        self.countdown_seen = True
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((5, 9, 18, 70))
        self.screen.blit(veil, (0, 0))
        self.text(f"ROUND {self.game_state.get('round', 1)}", W // 2, 262, 22, GOLD, True)
        number = int(math.ceil(countdown))
        step = countdown - math.floor(countdown)   # 1.0 -> 0.0 within the second
        scale = 1.05 + .55 * step
        alpha = 255 if step > .22 else int(255 * step / .22)
        surface = self.fonts[56].render(str(number), True, GOLD)
        size = (max(1, int(surface.get_width() * scale)), max(1, int(surface.get_height() * scale)))
        surface = pygame.transform.smoothscale(surface, size)
        surface.set_alpha(alpha)
        shadow = pygame.transform.smoothscale(self.fonts[56].render(str(number), True, (8, 12, 22)), size)
        shadow.set_alpha(int(alpha * .45))
        self.screen.blit(shadow, shadow.get_rect(center=(W // 2 + 4, 346)))
        self.screen.blit(surface, surface.get_rect(center=(W // 2, 340)))

    def toggle_pause(self):
        self.paused = not self.paused
        # 暂停期间不消费输入，恢复时不能带出暂停前的残留点按。
        self.press_latch.clear()

    def restart_mode(self):
        self.paused = False
        if self.practice_mode == "training":
            self.training()
        elif self.practice_mode == "cpu_vs_cpu":
            self.cpu_vs_cpu()
        else:
            self.practice()

    def _pause_hint(self):
        """暂停面板顶部的模式说明（原对战页底部提示挪入面板）。"""
        if self.practice_mode == "training":
            return "技能训练：AI 自动回满血 · 不会移动和攻击", CYAN
        if self.practice_mode == "cpu_vs_cpu":
            return "电脑双人对战：双方均由 AI 操作", GOLD
        return "练习模式：AI 自动移动与出招", MUTED

    def pause_overlay(self):
        hint, tint = self._pause_hint()
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((6, 10, 20, 215))
        self.screen.blit(veil, (0, 0))
        self.panel(W // 2 - 250, 190, 500, 400, PANEL, 20, (58, 76, 108), GOLD)
        self.text("暂 停", W // 2, 234, 40, WHITE, True, shadow=True)
        pygame.draw.line(self.screen, (48, 64, 92), (W // 2 - 160, 268),
                         (W // 2 + 160, 268), 1)
        self.text(hint, W // 2, 284, 16, tint, True)
        self.button("继续游戏", (W // 2 - 150, 310, 300, 50), self.toggle_pause, GREEN)
        self.button("招式表", (W // 2 - 150, 372, 144, 50), self.open_char_moves, PANEL_HI)
        self.button("设置", (W // 2 + 6, 372, 144, 50), self.open_settings, PANEL_HI)
        self.button("重新开始", (W // 2 - 150, 434, 300, 50), self.restart_mode, PANEL_HI)
        self.button("返回主菜单", (W // 2 - 150, 496, 300, 50), self.back, PANEL_HI)
        self.text("按 ESC 继续", W // 2, 556, 16, MUTED, True)

    def fighter_art(self, char_id, size, walk=0., face=1, action="idle"):
        """Procedural fighter scaled to ``size`` for cards and showcase walls."""
        style = CHARACTERS.get(char_id, CHARACTERS["red_scarf"])
        canvas = pygame.Surface((180, 212), pygame.SRCALPHA)
        sample = {'x': 90, 'y': 0, 'face': face, 'action': action,
                  'action_frame': 0, 'walk': walk, 'flash': 0, 'attack_kind': '',
                  'char_id': char_id,
                  'projectile_config': style.get('projectile', {})}
        draw_stickman(pygame, canvas, sample, 0, 202, offset=0)
        return pygame.transform.smoothscale(canvas, size)

    def set_page(self, p):
        self.page = p

    def _setup_combat(self):
        """Apply the selected characters' loadouts to the combat instance."""
        self.combat.set_loadout(0, CHARACTERS[self.char_p1])
        self.combat.set_loadout(1, CHARACTERS[self.char_p2])
        # Every combat rebuild (practice / training / cpu_vs_cpu) goes through
        # here, so rebind both controllers to the fresh instance in one place.
        self.ai[0].bind(self.combat)
        self.ai[1].bind(self.combat)

    def lock_match_ai(self, levels):
        """开局锁定两个 AI 槽位的难度与角色风格。

        levels 为 (p0, p1) 档位，None 表示该槽位不跑 AI。锁定后对局中途
        改设置（含暂停→设置）不会改变 AI 行为，HUD 名字也读锁定值。
        """
        style = self.settings.get("char_ai", True)
        for idx, level in enumerate(levels):
            self.ai[idx].set_level(level)
            self.ai[idx].set_style(style)

    def practice(self):
        self.combat = Combat(self.settings["map"])
        self._setup_combat()
        self.combat.countdown = ROUND_COUNTDOWN
        self.fighters = self.combat.fighters
        self.game_state = self.combat.snapshot()
        self.page = "practice"
        self.practice_mode = "normal"
        self.frame_data_move = ''
        self.winner = None
        self.effects = []
        # 难度与风格在本局开场锁定：之后改设置既不动 AI 行为，也不动 HUD 名字。
        self.lock_match_ai((None, self.settings["ai_level"]))
        self.ai[0].reset()
        self.ai[1].reset()
        self.reset_match_fx()

    def training(self):
        self.combat = Combat(self.settings["map"])
        self.combat.training_mode = True
        self._setup_combat()
        # Combo training starts immediately: no pre-round countdown.
        self.fighters = self.combat.fighters
        self.game_state = self.combat.snapshot()
        self.page = "practice"
        self.practice_mode = "training"
        self.frame_data_move = ''
        self.winner = None
        self.effects = []
        self.lock_match_ai((None, None))
        self.ai[0].reset()
        self.ai[1].reset()
        self.reset_match_fx()
        self.announce("TRAINING", "技能训练 · 自由练习连招", CYAN, 1.5)

    def cpu_vs_cpu(self):
        """Spectator match: both fighters are driven by the AI."""
        self.combat = Combat(self.settings["map"])
        self._setup_combat()
        self.combat.countdown = ROUND_COUNTDOWN
        self.fighters = self.combat.fighters
        self.game_state = self.combat.snapshot()
        self.page = "practice"
        self.practice_mode = "cpu_vs_cpu"
        self.winner = None
        self.effects = []
        # 两侧各按自己的档位锁定，观战局可以一边困难一边普通。
        self.lock_match_ai((self.settings["ai_level_p1"],
                            self.settings["ai_level_p2"]))
        # Slightly desync the two AIs so they do not trade attacks in lockstep.
        self.ai[0].reset(clock=random.uniform(0., .3))
        self.ai[1].reset(clock=random.uniform(.3, .6))
        self.reset_match_fx()
        self.announce("CPU vs CPU", "电脑双人对战 · 观战模式", GOLD, 1.5)

    def reset_match_fx(self):
        self.hp_shown = [float(f.get('hp_max', DEFAULT_HP)) for f in self.fighters]
        self.hp_trail = list(self.hp_shown)
        self.energy_shown = [0., 0.]
        self.combo_shown = [0, 0]
        self.combo_pop = [0., 0.]
        self.round_seen = 1
        self.phase_seen = "game"
        self.countdown_seen = False
        self.particles = []
        self.paused = False
        self.time_stop_channels = {}
        self.flash = 0.
        self.shake = 0.

    def apply_combat_event(self, ev):
        kind = ev.get("event")
        attack = ev.get("attack", "")
        if kind == "hit" and attack == "super_pummel":
            # Grab super punches get their own rapid impact sound.
            self.audio.play("pummel_finish" if ev.get("final") else "pummel",
                            self.settings["sfx"])
        elif kind == "time_stop_cast":
            # 砸瓦鲁多的喊招音效：从时停生效提前到大招起手那一帧播放。
            # 记下播放用的 Channel，前摇被打断时要把它掐断。
            self.time_stop_channels[ev.get("player", 0)] = self.audio.play(
                "time_stop", self.settings["sfx"])
        elif kind == "time_stop_cancel":
            # 前摇被打断：说话/钟声立刻停下，避免声音盖过受击反馈。
            channel = self.time_stop_channels.pop(ev.get("player", 0), None)
            if channel:
                channel.stop()
        elif kind == "super":
            # 砸瓦鲁多的喊招音由 time_stop_cast 单独播放（用户可替换的素材），
            # 这里不再叠加通用的「大招提示音」，免得起手同时响两下。
            player = ev.get("player", 0)
            caster = self.fighters[player] if player in (0, 1) else None
            if caster is None or caster.get("super_kind") != "time_stop":
                self.audio.play(kind, self.settings["sfx"])
        elif kind == "time_stop":
            # 音效已在起手播放，生效帧保持沉默，只做视觉宣告。
            pass
        elif kind == "hit" and attack == "knife":
            # 飞刀命中：金属声已由 knife_rush 统一播放，这里不再叠通用打击音。
            pass
        elif kind == "hit" and attack == "ice_beam":
            # 冰束命中：一声冰霜脆响，与冻结状态生效同一帧。
            self.audio.play("ice_hit", self.settings["sfx"])
        elif kind == "vapor_beam":
            # 气化冷冻法射出冰束：冷气破空。
            self.audio.play("ice_fall", self.settings["sfx"])
        elif kind == "vapor_shatter":
            # 冻脆的身体被一拳打碎。
            self.audio.play("ice_shatter", self.settings["sfx"])
        elif kind == "hit" and attack == "time_punch":
            # 时停中的瞬发拳：每一拳一声干脆的打击音。
            self.audio.play("time_punch", self.settings["sfx"])
        elif kind in ("vapor_freeze", "ice_shadow"):
            # 结冰系技能开启：气化冷冻法起手 / 冰千年杀遁地。
            self.audio.play("ice_freeze", self.settings["sfx"])
        elif kind in ("projectile", "crouch_projectile"):
            # 迪奥的远程是飞刀，用金属刃响；红头巾的火焰弹走火焰声；
            # 其余角色仍用通用发波音。
            player = ev.get("player", 0)
            caster = self.fighters[player] if player in (0, 1) else None
            char_id = caster.get("char_id") if caster else None
            if char_id == "dio":
                self.audio.play("slash_hit", self.settings["sfx"])
            elif char_id == "red_scarf":
                self.audio.play("projectile_fire", self.settings["sfx"])
            else:
                self.audio.play("projectile", self.settings["sfx"])
        else:
            self.audio.play(kind, self.settings["sfx"])
        if kind == "hit":
            target = ev.get("target", 0)
            if target not in (0, 1): return
            f = self.fighters[target]
            blocked = bool(ev.get("blocked"))
            pummel = attack == "super_pummel"
            accent = CHARACTERS.get(self.fighters[1 - target].get("char_id", "red_scarf"),
                                    CHARACTERS["red_scarf"])["accent"]
            x, y = WORLD_X_OFF + f["x"], 420 - f.get("y", 0)
            color = CYAN if blocked else (accent if pummel else GOLD)
            self.effects.append({"kind": "hit", "x": x, "y": y,
                                 "damage": ev.get("damage", 0), "life": .42, "max": .42,
                                 "color": color, "blocked": blocked})
            self.spawn_particles(x, y, color, 14 if blocked else 10,
                                 speed=220, gravity=260, life=.42, size=5)
            heavy = attack == "super"
            laser = attack == "laser"
            self.shake = max(self.shake, .22 if heavy else .07 if laser else .13)
            source = 1 - target
            self.ai[source].patience = 0.
            caster = self.fighters[source]
            if pummel and not blocked:
                # Each punch spits flame tongues and embers; the final blow is
                # a heavier burst.
                final = bool(ev.get("final"))
                self.effects.append({"kind": "flame", "x": x, "y": y,
                                     "life": .28, "max": .28, "color": accent,
                                     "radius": 46 if final else 32,
                                     "angle": random.uniform(0, math.pi)})
                self.spawn_particles(x, y, accent, 12 if final else 8,
                                     speed=260, gravity=150, life=.4, size=6)
                self.spawn_particles(x, y, (255, 238, 190), 4, speed=160,
                                     gravity=-60, life=.3, size=4, rise=True)
                self.shake = max(self.shake, .32 if final else .16)
            if attack == "ice_beam" and not blocked:
                # 气化冷冻法命中：冰霜环从对手身上炸开（冻结状态由战斗核心接管）。
                self.spawn_particles(x, y, (206, 240, 255), 18, speed=230,
                                     gravity=60, life=.55, size=5)
                self.effects.append({"kind": "shock", "x": x, "y": y, "r0": 10,
                                     "r1": 66, "life": .3, "max": .3,
                                     "color": (196, 236, 255), "width": 4})
                self.shake = max(self.shake, .2)
            if attack == "super" and not blocked and caster.get("super_kind") == "rush_slash":
                # Each cut of the rushing super leaves a slash streak and rings
                # with its own icy blade sound.
                self.audio.play("slash_hit", self.settings["sfx"])
                accent = CHARACTERS.get(caster.get("char_id", "red_scarf"),
                                        CHARACTERS["red_scarf"])["accent"]
                self.effects.append({"kind": "slash", "x": x, "y": y,
                                     "life": .3, "max": .3, "color": accent,
                                     "angle": -0.85 if len(self.effects) % 2 else -0.4})
            if (attack == "super" and not blocked
                    and self.fighters[source].get("super_radius")):
                # Radial command super: blast wave centred on the caster plus a
                # knockdown callout over the victim.
                caster = self.fighters[source]
                accent = CHARACTERS.get(caster.get("char_id", "red_scarf"),
                                        CHARACTERS["red_scarf"])["accent"]
                radius = float(caster["super_radius"])
                cx, cy = WORLD_X_OFF + caster["x"], 555 - int(caster.get("y", 0)) - 72
                self.effects.append({"kind": "shock", "x": cx, "y": cy, "r0": 24,
                                     "r1": radius + 34, "life": .48, "max": .48,
                                     "color": accent, "width": 12})
                self.effects.append({"kind": "shock", "x": cx, "y": cy, "r0": 10,
                                     "r1": radius, "life": .34, "max": .34,
                                     "color": WHITE, "width": 6})
                self.spawn_particles(x, y, accent, 24, speed=420, gravity=90,
                                     life=.55, size=7)
                self.spawn_particles(x, 555, (255, 220, 150), 12, speed=260,
                                     gravity=-20, life=.45, size=5, rise=True)
                self.flash = max(self.flash, .5)
                self.shake = max(self.shake, .5)
        elif kind == "vapor_freeze":
            # 气化冷冻法起手：迪奥手心散开一圈冷气，冻结判定在有效帧才生效。
            player = ev.get("player", 0)
            if player in (0, 1):
                caster = self.fighters[player]
                x = WORLD_X_OFF + int(caster["x"]) + int(caster.get("face", 1)) * 46
                y = 555 - int(caster.get("y", 0)) - 96
                self.spawn_particles(x, y, (198, 238, 255), 14, speed=170,
                                     gravity=-30, life=.45, size=4, rise=True)
        elif kind == "vapor_shatter":
            # 冻结中挨打：冰壳碎开，冰屑四散。
            target = ev.get("target", 0)
            x = W // 2
            if target in (0, 1):
                x = WORLD_X_OFF + int(self.fighters[target]["x"])
            self.spawn_particles(x, 470, (226, 248, 255), 22, speed=340,
                                 gravity=140, life=.5, size=6)
            self.flash = max(self.flash, .18)
        elif kind == "time_stop":
            # 砸瓦鲁多：全屏泛白 + 大字公告 + 强震屏，宣告时间停止。
            self.flash = max(self.flash, .85)
            self.shake = max(self.shake, .55)
            self.announce("砸瓦鲁多", "时间停止 7 秒", GOLD, 1.9)
        elif kind == "knife_throw":
            # 时停中掏出一把飞刀：每把一声金属轻响，进度越满音高越亮。
            self.audio.play("slash_hit", self.settings["sfx"])
        elif kind == "knife_rush":
            # 时间恢复的瞬间飞刀齐射：连续三声刃响 + 白闪，强调"时间回来了"。
            for _ in range(3):
                self.audio.play("slash_hit", self.settings["sfx"])
            self.flash = max(self.flash, .28)
            self.shake = max(self.shake, .3)
        elif kind == "road_roller":
            # ROAD ROLLER DA!!：压路机砸地的重量级演出。
            self.audio.play("throw", self.settings["sfx"])
            self.audio.play("pummel_finish", self.settings["sfx"])
            self.flash = max(self.flash, .65)
            self.shake = max(self.shake, .85)
            self.announce("ROAD ROLLER DA!!", "压路机", GOLD, 1.7)
            target = ev.get("target", 0)
            x = W // 2
            if target in (0, 1):
                x = WORLD_X_OFF + int(self.fighters[target]["x"])
            self.effects.append({"kind": "roller", "x": x, "y": 555,
                                 "life": .42, "max": .42, "color": (208, 210, 216)})
        elif kind == "time_resume":
            # 时间恢复：一圈冲击波从场中扩散，提醒双方重新获得行动权。
            self.flash = max(self.flash, .3)
            self.shake = max(self.shake, .22)
            self.effects.append({"kind": "shock", "x": W // 2, "y": 470,
                                 "r0": 8, "r1": W * .7, "life": .4, "max": .4,
                                 "color": (240, 250, 255), "width": 6})
        elif kind == "knockdown":
            player = ev.get("player", 0)
            if player in (0, 1):
                f = self.fighters[player]
                x, y = WORLD_X_OFF + f["x"], 420 - f.get("y", 0)
                self.effects.append({"kind": "label", "text": "KNOCKDOWN 2s",
                                     "x": x, "y": y - 30, "life": .85, "max": .85,
                                     "color": GOLD})
                self.spawn_particles(x, 555, (120, 140, 170), 10, speed=180,
                                     gravity=-20, life=.4, size=4, rise=True)
                self.shake = max(self.shake, .22)
        elif kind == "lava_warn":
            # 熔岩地貌的预警圈亮起：低沉的嘶鸣提示火柱即将喷发。
            self.audio.play("lava_warn", self.settings["sfx"])
        elif kind == "lava_erupt":
            # 熔岩地貌的火柱喷发：地面震动、火星四溅。
            x = WORLD_X_OFF + ev.get("x", 510)
            self.audio.play("lava_erupt", self.settings["sfx"])
            self.effects.append({"kind": "flame", "x": x, "y": 465,
                                 "life": .38, "max": .38, "color": (255, 150, 60),
                                 "radius": 82, "angle": math.pi / 2})
            self.spawn_particles(x, 552, (255, 160, 60), 26, speed=380,
                                 gravity=180, life=.7, size=7)
            self.spawn_particles(x, 552, (255, 232, 170), 10, speed=240,
                                 gravity=-140, life=.8, size=5, rise=True)
            self.shake = max(self.shake, .34)
            self.flash = max(self.flash, .16)
        elif kind == "ice_fall":
            # 冰雪溶洞：冰棱破空而下，只有一声极短的风切声。
            self.audio.play("ice_fall", self.settings["sfx"])
        elif kind == "ice_hit":
            # 冰棱砸中角色：冻住一秒，碎冰四散。
            x = WORLD_X_OFF + ev.get("x", 510)
            self.audio.play("ice_hit", self.settings["sfx"])
            self.spawn_particles(x, 500, (198, 238, 255), 20, speed=210,
                                 gravity=140, life=.55, size=5)
            self.flash = max(self.flash, .12)
        elif kind == "ice_shatter":
            # 冰棱落地碎裂：地面炸开一片冰晶。
            x = WORLD_X_OFF + ev.get("x", 510)
            self.audio.play("ice_shatter", self.settings["sfx"])
            self.spawn_particles(x, 552, (208, 242, 255), 24, speed=330,
                                 gravity=260, life=.6, size=5)
            self.spawn_particles(x, 552, (255, 255, 255), 8, speed=180,
                                 gravity=-120, life=.7, size=4, rise=True)
            self.shake = max(self.shake, .18)
        elif kind == "grab_pull":
            player = ev.get("player", 0)
            if player in (0, 1):
                caster = self.fighters[player]
                victim = self.fighters[1 - player]
                accent = CHARACTERS.get(caster.get("char_id", "red_scarf"),
                                        CHARACTERS["red_scarf"])["accent"]
                cx, cy = WORLD_X_OFF + caster["x"], 555 - int(caster.get("y", 0)) - 66
                # Spiral of flame arcs converging on the caster as the foe is
                # dragged in.
                self.effects.append({"kind": "vortex", "x": cx, "y": cy,
                                     "life": .42, "max": .42,
                                     "color": accent, "radius": 86})
                self.spawn_particles(WORLD_X_OFF + victim["x"], 470, accent, 14,
                                     speed=170, gravity=-70, life=.4, size=5, rise=True)
                self.flash = max(self.flash, .3)
                self.shake = max(self.shake, .3)
        elif kind == "throw":
            target = ev.get("target", 0)
            if target in (0, 1):
                # The victim skids to a stop half an arena away, leaving a
                # flame trail and a burst of dust at the landing spot.
                f = self.fighters[target]
                accent = CHARACTERS.get(self.fighters[1 - target].get("char_id", "red_scarf"),
                                        CHARACTERS["red_scarf"])["accent"]
                x = WORLD_X_OFF + f["x"]
                x0 = WORLD_X_OFF + ev.get("from_x", f["x"])
                self.effects.append({"kind": "streak", "x": x, "y": 498,
                                     "x0": x0, "x1": x, "life": .32, "max": .32,
                                     "color": accent, "width": 20})
                self.effects.append({"kind": "shock", "x": x, "y": 540, "r0": 20,
                                     "r1": 88, "life": .4, "max": .4,
                                     "color": accent, "width": 10})
                self.spawn_particles(x, 555, (255, 170, 90), 22, speed=330,
                                     gravity=170, life=.55, size=7)
                self.flash = max(self.flash, .35)
                self.shake = max(self.shake, .5)
        elif kind == "super":
            self.flash = max(self.flash, .35)
            self.shake = max(self.shake, .3)
            player = ev.get("player", 0)
            if player in (0, 1):
                f = self.fighters[player]
                self.spawn_particles(WORLD_X_OFF + f["x"], 420, GOLD, 18,
                                     speed=260, gravity=-120, life=.6, size=6, rise=True)
                style = CHARACTERS.get(f.get("char_id", "red_scarf"),
                                       CHARACTERS["red_scarf"])
                accent = style["accent"]
                self.announce(style["super"].name, "", accent, 1.05)
                if f.get("super_radius"):
                    # Command super: flame gathers inward during startup, then erupts.
                    radius = float(f["super_radius"])
                    cx, cy = WORLD_X_OFF + f["x"], 555 - int(f.get("y", 0)) - 72
                    self.effects.append({"kind": "shock", "x": cx, "y": cy,
                                         "r0": radius, "r1": 26,
                                         "life": .32, "max": .32,
                                         "color": accent, "width": 9})
                    self.spawn_particles(cx, cy, accent, 22, speed=230,
                                         gravity=-160, life=.45, size=6)
        elif kind == "flame_buff":
            player = ev.get("player", 0)
            if player in (0, 1):
                f = self.fighters[player]
                style = CHARACTERS.get(f.get("char_id", "red_scarf"),
                                       CHARACTERS["red_scarf"])
                accent = style["accent"]
                x = WORLD_X_OFF + f["x"]
                for side in (-1, 1):
                    self.spawn_particles(x + side * 22, 402, accent, 10,
                                         speed=170, gravity=-140, life=.5,
                                         size=5, rise=True)
                self.flash = max(self.flash, .18)
                self.shake = max(self.shake, .16)
                self.announce(style.get("combo", {}).get("name", ""), "", accent, .9)
        elif kind == "ice_shadow":
            player = ev.get("player", 0)
            if player in (0, 1):
                f = self.fighters[player]
                style = CHARACTERS.get(f.get("char_id", "red_scarf"),
                                       CHARACTERS["red_scarf"])
                accent = style["accent"]
                self.spawn_particles(WORLD_X_OFF + f["x"], 500, accent, 14,
                                     speed=190, gravity=-60, life=.35,
                                     size=5, rise=True)
                self.flash = max(self.flash, .16)
                self.shake = max(self.shake, .14)
                self.announce(style.get("combo", {}).get("name", ""), "", accent, .9)
        elif kind == "rush":
            player = ev.get("player", 0)
            if player in (0, 1):
                f = self.fighters[player]
                accent = CHARACTERS.get(f.get("char_id", "red_scarf"),
                                        CHARACTERS["red_scarf"])["accent"]
                self.spawn_particles(WORLD_X_OFF + f["x"], 500, accent, 12,
                                     speed=180, gravity=80, life=.35, size=5)
                self.shake = max(self.shake, .22)
        elif kind == "dash":
            player = ev.get("player", 0)
            if player in (0, 1):
                f = self.fighters[player]
                self.spawn_particles(WORLD_X_OFF + f["x"], 550, (140, 160, 190), 8,
                                     speed=140, gravity=120, life=.35, size=4,
                                     rise=True)
        elif kind == "land":
            player = ev.get("player", 0)
            if player in (0, 1):
                f = self.fighters[player]
                self.spawn_particles(WORLD_X_OFF + f["x"], 550, (120, 140, 170), 6,
                                     speed=120, gravity=100, life=.3, size=3,
                                     rise=True)

    def update_effects(self, dt):
        for effect in self.effects:
            effect["life"] -= dt
        self.effects = [effect for effect in self.effects if effect["life"] > 0]
        for p in self.particles:
            p["vy"] += p["gravity"] * dt
            p["vx"] *= .97
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt
        self.particles = [p for p in self.particles if p["life"] > 0]
        self.shake = max(0., self.shake - dt)
        self.flash = max(0., self.flash - dt * .8)
        if self.announcement:
            self.announcement["t"] -= dt
            if self.announcement["t"] <= 0:
                self.announcement = None

    def update_practice(self, dt):
        frame_before = self.combat.frame
        own = self.own_input()
        ai = self.combat.fighters[1]
        if self.practice_mode == "training":
            cpu = {"left": False, "right": False, "punch": False, "kick": False, "jump": False}
            for ev in self.combat.step(dt, [own, cpu]):
                self.apply_combat_event(ev)
            ai["energy"] = MAX_ENERGY
            # dummy 永不按键，倒地到点自动起身（hp 未归零的情况）。
            if ai.get("knocked") and ai.get("stun", 0.) <= 0 and ai["hp"] > 0:
                ai["knocked"] = False
                ai["stagger"] = 0.
            self.combat.time_left = 65
        elif self.practice_mode == "cpu_vs_cpu":
            for ev in self.combat.step(dt, [self.ai[0].command(dt),
                                            self.ai[1].command(dt)]):
                self.apply_combat_event(ev)
        else:
            for ev in self.combat.step(dt, [own, self.ai[1].command(dt)]):
                self.apply_combat_event(ev)
        if self.combat.frame != frame_before:
            # 锁存的按下沿已经交给这一帧的模拟，清掉以免下一帧重复触发。
            self.press_latch.clear()
        self.fighters = self.combat.fighters
        self.game_state = self.combat.snapshot()

    def poll_network(self):
        if not self.client: return
        for _ in range(90):
            try: msg = self.client.events.get_nowait()
            except queue.Empty: break
            t = msg.get("type")
            if t == "room":
                self.players = msg.get("players", [])
                own = next((p for p in self.players if p["slot"] == self.client.slot), None)
                if own: self.ready = own["ready"]
                if msg.get("phase") == "game":
                    if self.page != "game":
                        self.reset_match_fx()
                        self.round_seen = 0
                    self.page = "game"
                    self.winner = None
                    self.effects = []
                    self.last_event = -1
                elif self.page in ("game", "result"):
                    self.page = "room"
                    self.winner = None
            elif t == "welcome":
                # Push the local choice for our own slot as soon as it is known.
                slot = self.client.slot or 0
                cid = self.char_p1 if slot == 0 else self.char_p2
                self.client.send({"type": "char", "char": cid})
            elif t == "state":
                self.game_state = msg
                self.fighters = msg.get("fighters", self.fighters)
            elif t == "combat":
                if msg.get("id", -1) > self.last_event:
                    self.last_event = msg.get("id", -1)
                    self.apply_combat_event(msg)
            elif t in ("error", "disconnected"):
                self.notify(msg.get("message", "与房间的连接已断开"))
                self.leave_room()
                self.page = "lan"
                break

    def send_input(self):
        if self.client and self.page == "game" and pygame.time.get_ticks() - self.last_input >= 35:
            self.client.send({"type": "input", **self.own_input()})
            self.last_input = pygame.time.get_ticks()
            # 已随这一帧发走，清掉锁存，等下一次发送前再收集新的点按。
            self.press_latch.clear()

    def leave_room(self):
        if self.client:
            self.client.close()
            self.client = None
        if self.server:
            self.server.stop()
            self.server = None
        self.players = []
        self.ready = False
        self.effects = []

    def back(self):
        self.set_focus(None)
        self.press_latch.clear()
        # 离开页面时收掉难度浮层，免得它跟着带回上一页。
        self.ai_picker_open = False
        origin, self.settings_return = self.settings_return, ""
        moves_origin, self.moves_return = self.moves_return, ""
        self.paused = False
        if self.page in ("room", "game", "result"):
            self.leave_room()
            self.page = "lan"
        elif self.page == "moves": self.page = "settings"
        elif self.page == "char_moves":
            # 回到暂停中的对局：仍保持暂停，由玩家点“继续游戏”恢复。
            self.page = moves_origin or "settings"
            self.paused = bool(moves_origin)
        elif self.page == "showcase": self.page = "select"
        elif self.page == "settings" and origin:
            # 回到暂停中的对局：保持暂停，由玩家点“继续游戏”恢复。
            self.page = origin
            self.paused = True
        elif self.page == "select":
            self.page = "room" if self.select_mode == "lan_pick" and self.client else "menu"
        elif self.page in ("practice", "lan"): self.page = "menu"
        else: self.page = "menu"

    def update_music(self):
        """Per-map BGM: battle pages loop their map's track, menus stay quiet."""
        if self.page not in ("game", "practice"):
            map_id = None
        else:
            gs = getattr(self, "game_state", None)
            map_id = (isinstance(gs, dict) and gs.get("map")) or self.settings["map"]
        play_map_music(map_id, self.settings["music"])

    def notify(self, message):
        self.notice = message
        self.notice_until = pygame.time.get_ticks() + 3600

    def key_input(self, event):
        if event.key == pygame.K_ESCAPE:
            if self.focus: self.set_focus(None)
            elif self.ai_picker_open:
                # 浮层常驻设置页，先关它，别让 ESC 直接退回菜单。
                self.ai_picker_open = False
            elif self.page == "practice":
                self.toggle_pause()
            elif self.page == "menu":
                if self.map_picker_open:
                    self.map_picker_open = False
                else:
                    self.running = False
            else: self.back()
            return
        if not self.focus: return
        if event.key in (pygame.K_RETURN, pygame.K_TAB):
            self.set_focus(None)
        elif event.key == pygame.K_BACKSPACE:
            self.fields[self.focus] = self.fields[self.focus][:-1]

    def text_input(self, text):
        """Commit keyboard / IME text into the focused field."""
        if not self.focus or not text or not text.isprintable():
            return
        if self.focus == "port":
            text = "".join(ch for ch in text if ch.isdigit())
            if not text:
                return
        limit = 12 if self.focus == "nickname" else 5 if self.focus == "port" else 45
        room = limit - len(self.fields[self.focus])
        if room > 0:
            self.fields[self.focus] += text[:room]

    def run(self):
        while self.running:
            dt = min(self.clock.tick(60) / 1000, .05)
            self.dt = dt
            self.now += dt
            self.sync_text_input()
            if self.page != self.last_page:
                self.page_fade = 1.
                self.last_page = self.page
                self.button_glow.clear()
                self.card_glow.clear()
            self.page_fade = max(0., self.page_fade - dt / .30)
            self.poll_network()
            self.update_effects(dt)
            self.update_pointer(dt)
            self.update_music()
            self.controls = []
            self.screen = self.canvas
            self.background("arena" if self.page in ("game", "result", "practice") else "menu")
            if self.page == "menu": self.menu()
            elif self.page == "select": self.select_page()
            elif self.page == "showcase": self.showcase_page()
            elif self.page == "lan": self.lan()
            elif self.page == "settings": self.settings_page()
            elif self.page == "moves": self.moves_page()
            elif self.page == "char_moves": self.char_moves_page()
            elif self.page == "room": self.room()
            elif self.page in ("game", "result", "practice"):
                if self.page == "practice" and not self.paused: self.update_practice(dt)
                self._arena()
                self.send_input()
            if pygame.time.get_ticks() < self.notice_until:
                r = self.rect(245, 15, 610, 45, (70, 54, 70), 10)
                self.text(self.notice, r.centerx, r.centery, 19, WHITE, True)
            self.screen = self.display_surface
            dw, dh = self.display_surface.get_size()
            self.display_surface.fill(BG)
            if self.shake > 0 and self.page in ("practice", "game", "result"):
                amp = int(min(12, self.shake * 60))
                offset = (random.randint(-amp, amp), random.randint(-amp, amp))
            else:
                offset = (0, 0)
            if self.scaled is not None:
                # Fullscreen: manually upscale the logical canvas every frame,
                # either stretched or aspect-fit (letterbox borders stay BG).
                if self.letterbox is not None:
                    pygame.transform.scale(
                        self.canvas, self.letterbox.get_size(), self.letterbox)
                    self.display_surface.blit(
                        self.letterbox,
                        (self.letterbox_pos[0] + offset[0],
                         self.letterbox_pos[1] + offset[1]))
                else:
                    pygame.transform.scale(self.canvas, (dw, dh), self.scaled)
                    self.display_surface.blit(self.scaled, offset)
            else:
                self.display_surface.blit(self.canvas, offset)
            if self.flash > 0:
                flash = pygame.Surface((dw, dh))
                flash.fill((255, 255, 255))
                flash.set_alpha(int(min(150, self.flash * 320)))
                self.display_surface.blit(flash, (0, 0))
            if self.page_fade > 0:
                self.fade_surface.set_alpha(int(210 * (self.page_fade ** 2)))
                self.display_surface.blit(self.fade_surface, (0, 0))
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.set_focus(None)
                    self.running = False
                elif ev.type == pygame.KEYDOWN:
                    self.latch_combat_key(ev.key)
                    self.key_input(ev)
                elif ev.type == pygame.TEXTINPUT: self.text_input(ev.text)
                elif ev.type == pygame.MOUSEWHEEL and self.page == "select":
                    self.select_scroll -= ev.y * 60
                elif (ev.type == pygame.MOUSEWHEEL and self.page == "menu"
                      and self.map_picker_open):
                    self.map_scroll = max(0., self.map_scroll - ev.y * 60)
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    pos = self.to_logical(ev.pos)
                    pos = (pos[0] - offset[0], pos[1] - offset[1])
                    target = next((action for r, action in reversed(self.controls)
                                   if r.collidepoint(pos)), None)
                    now_ms = pygame.time.get_ticks()
                    double = (now_ms - self.last_click_ms <= 320 and
                              abs(pos[0] - self.last_click_pos[0]) <= 10 and
                              abs(pos[1] - self.last_click_pos[1]) <= 10)
                    self.last_click_ms, self.last_click_pos = now_ms, pos
                    if isinstance(target, tuple) and target[0] == "focus":
                        self.set_focus(target[1])
                    elif isinstance(target, tuple) and target[0] == "card":
                        self.set_focus(None)
                        self.pick_char(target[1], target[2])
                        if double:
                            self.open_showcase(target[2])
                    else:
                        self.set_focus(None)
                        if callable(target): target()
            pygame.display.flip()
        self.leave_room()
        pygame.quit()