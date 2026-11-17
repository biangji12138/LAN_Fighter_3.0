"""Battle arena rendering and stage definitions.

A stage is pure data: palettes and labels only. New stages are added by one
dict entry here; the renderer reads MAPS[current] and needs no code change.
"""
import math

import pygame

from .attacks import ATTACKS
from . import assets
from .characters import CHARACTERS
from .skeleton import _dim
from .combat import (ARENA_LEFT, ARENA_RIGHT, DEFAULT_HP, MAX_ENERGY,
                     NECK_HEIGHT, attack_spec, shadow_phase, SHADOW_BURROW,
                     SHADOW_HIDE, LAVA_PILLAR_DURATION, LAVA_PILLAR_HEIGHT,
                     LASER_STARTUP, LASER_EYE_HEIGHT, LASER_CROUCH_EYE_HEIGHT,
                     LASER_HALF_THICK, body_span)
from .skeleton import draw as draw_stickman
from .theme import (W, H, WHITE, MUTED, CYAN, RED, GREEN, GOLD,
                    BLUE, mix)

# 战斗世界坐标 → 画布横坐标偏移：把 ARENA_LEFT..ARENA_RIGHT（combat.py）居中到
# 画布上。战斗逻辑不感知画布宽度，渲染层的换算统一走这个偏移。
WORLD_X_OFF = (W - (ARENA_RIGHT - ARENA_LEFT)) // 2 - ARENA_LEFT

# HUD 名字：练习模式按 AI 难度显示，配色与设置页难度按钮一致。
AI_LABELS = {"normal": "普通AI", "medium": "中等AI",
             "hard": "困难AI", "hell": "地狱AI"}
AI_SHORT = {"normal": "普通", "medium": "中等", "hard": "困难", "hell": "地狱"}
AI_TINTS = {"normal": BLUE, "medium": CYAN, "hard": GOLD, "hell": RED}

# 技能训练帧数据面板用的招式中文名。
FRAME_LABELS = {
    'punch': '轻拳', 'kick': '轻脚', 'low_kick': '下踢',
    'jump_punch': '空中拳', 'crouch_punch': '蹲拳', 'grab': '抓取',
    'projectile': '远程波', 'crouch_projectile': '低位波',
    'super': '大招', 'flame_buff': '火焰架势', 'lightning_strike': '落雷',
    'laser': '石面鬼之眼', 'ice_shadow': '冰千年杀',
    'tackle': '借过一下', 'shield_buff': '护盾', 'vapor_freeze': '气化冷冻法',
}

MAPS = {
    "dojo": {
        "name": "原初战场",
        "desc": "经典霓虹擂台 · 无机关干扰",
        "sky_top": (33, 51, 84),
        "sky_bottom": (12, 20, 36),
        "horizon": (46, 84, 140, 9),
        "spot_left": (128, 190, 255, 26),
        "spot_right": (128, 190, 255, 20),
        "pillar": (30, 44, 68),
        "pillar_rim": (54, 76, 110),
        "pillar_cap": (24, 35, 55),
        "pillar_glint": (80, 126, 176),
        "pillar_stud": (74, 110, 156),
        "grid": (34, 50, 76),
        "floor_top": (50, 64, 90),
        "floor_bottom": (26, 36, 54),
        "floor_ray": (54, 70, 98),
        "lip": (128, 166, 206),
        "floor_edge": (26, 40, 60),
    },
    "lava": {
        "name": "熔岩地貌",
        "desc": "地面随机喷发火柱 · 命中 20 伤害",
        # 背景图放在 assets/backgrounds/lava.jpg，可自行替换同名文件。
        "bg": "lava",
        "sky_top": (62, 27, 24),
        "sky_bottom": (22, 11, 14),
        "horizon": (126, 52, 32, 9),
        "spot_left": (255, 156, 66, 18),
        "spot_right": (255, 120, 48, 14),
        "pillar": (46, 28, 26),
        "pillar_rim": (88, 48, 38),
        "pillar_cap": (34, 20, 20),
        "pillar_glint": (154, 82, 52),
        "pillar_stud": (172, 92, 54),
        "grid": (58, 33, 30),
        "floor_top": (52, 33, 30),
        "floor_bottom": (22, 13, 15),
        "floor_ray": (74, 39, 32),
        "lip": (255, 142, 70),
        "floor_edge": (46, 22, 18),
    },
    "ice": {
        "name": "冰雪溶洞",
        "desc": "洞顶坠落冰棱 · 命中冰冻 1 秒",
        # 背景图放在 assets/backgrounds/ice.jpg，可自行替换同名文件。
        "bg": "ice",
        "sky_top": (38, 62, 86),
        "sky_bottom": (10, 19, 31),
        "horizon": (96, 152, 190, 9),
        "spot_left": (176, 228, 255, 20),
        "spot_right": (146, 212, 250, 16),
        "pillar": (28, 44, 62),
        "pillar_rim": (64, 100, 132),
        "pillar_cap": (18, 30, 44),
        "pillar_glint": (116, 172, 208),
        "pillar_stud": (130, 186, 220),
        "grid": (42, 62, 82),
        "floor_top": (40, 58, 78),
        "floor_bottom": (14, 24, 36),
        "floor_ray": (52, 76, 100),
        "lip": (186, 232, 255),
        "floor_edge": (28, 44, 60),
    },
}
DEFAULT_MAP = "dojo"


def get_map(map_id):
    """Return the requested stage, falling back to the default one."""
    return MAPS.get(map_id) or MAPS[DEFAULT_MAP]


class ArenaPage:
    """Battle stage rendering.

    Host dependencies (supplied by GameApp): ``screen``, ``fonts``, ``dt``,
    ``now``, ``fighters``, ``hp_shown``, ``hp_trail``, ``game_state``,
    ``page``, ``practice_mode``, ``settings``, plus ``text`` / ``rect`` /
    ``panel`` / ``draw_fighter`` helpers.
    """

    def stage(self):
        """Current stage data record (see MAPS).

        Online matches carry the host's map id in the state snapshot, so both
        clients render the same stage even if their local settings differ.
        """
        map_id = self.game_state.get("map") or self.settings.get("map", DEFAULT_MAP)
        return get_map(map_id)

    def _arena(self):
        m = self.stage()
        phase = self.game_state.get("phase", "game")
        self.sync_match_state(phase)
        # ---------- arena shell: full-canvas sky, spotlights, pillars, floor ----------
        cx = W // 2
        arena_bottom = 555   # 战斗地面线，与战斗逻辑一致，不随画布缩放
        backdrop = (assets.cover("backgrounds", m["bg"], (W, arena_bottom))
                    if m.get("bg") else None)
        if backdrop is not None:
            # 地图自带背景图：铺满整个画布天空区，再压一层暗色薄纱保证角色可读。
            self.screen.blit(backdrop, (0, 0))
            veil = pygame.Surface((W, arena_bottom), pygame.SRCALPHA)
            veil.fill((8, 6, 10, 70))
            self.screen.blit(veil, (0, 0))
        else:
            for y in range(0, arena_bottom, 10):
                t = y / float(arena_bottom)
                pygame.draw.rect(self.screen, mix(m["sky_top"], m["sky_bottom"], t),
                                 (0, y, W, 10))
            horizon = pygame.Surface((W, H), pygame.SRCALPHA)
            for step in range(16):
                rx = 560 - step * 26
                pygame.draw.ellipse(horizon, m["horizon"],
                                    (cx - rx, 440 - step * 4, rx * 2, 150 + step * 7))
            self.screen.blit(horizon, (0, 0))
            cones = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.polygon(cones, m["spot_left"],
                                [(44, 0), (204, 0), (392, arena_bottom + 6),
                                 (10, arena_bottom + 6)])
            pygame.draw.polygon(cones, m["spot_right"],
                                [(W - 44, 0), (W - 204, 0), (W - 392, arena_bottom + 6),
                                 (W - 10, arena_bottom + 6)])
            self.screen.blit(cones, (0, 0))
            for px in (26, W - 26):
                pygame.draw.rect(self.screen, m["pillar"], (px - 15, 0, 30, arena_bottom))
                pygame.draw.rect(self.screen, m["pillar_rim"], (px - 15, 0, 30, arena_bottom), 1)
                pygame.draw.rect(self.screen, m["pillar_cap"], (px - 22, 0, 44, 14))
                pygame.draw.line(self.screen, m["pillar_glint"], (px - 8, 14),
                                 (px - 8, arena_bottom - 8), 1)
                for ly in (150, 240, 330, 420):
                    pygame.draw.circle(self.screen, m["pillar_stud"], (px, ly), 3)
            for i in range(10):
                px = 34 + i * 128
                pygame.draw.line(self.screen, m["grid"], (px, 200), (px, 545), 1)
        # floor with perspective rays and a bright neon lip
        for i in range(32):
            pygame.draw.rect(self.screen, mix(m["floor_top"], m["floor_bottom"], i / 31.),
                             (0, 555 + i * 4, W, 4))
        for i in range(-12, 13):
            pygame.draw.line(self.screen, m["floor_ray"], (cx + i * 26, 555),
                             (cx + i * 82, H), 1)
        pygame.draw.line(self.screen, m["lip"], (0, 555), (W, 555), 3)
        pygame.draw.line(self.screen, m["floor_edge"], (0, 598), (W, 598), 1)
        for idx, f in enumerate(self.fighters):
            barx = 70 if idx == 0 else W - 451
            hp_max = max(1., float(f.get("hp_max", DEFAULT_HP)))
            hp = max(0., min(hp_max, float(f["hp"])))
            self.hp_shown[idx] += (hp - self.hp_shown[idx]) * min(1., self.dt * 9)
            if self.hp_shown[idx] >= self.hp_trail[idx]:
                self.hp_trail[idx] = self.hp_shown[idx]
            else:
                self.hp_trail[idx] += (self.hp_shown[idx] - self.hp_trail[idx]) * min(1., self.dt * 3.2)
            char = CHARACTERS.get(f.get("char_id", "red_scarf"), CHARACTERS["red_scarf"])
            plate = pygame.Rect(barx - 8, 8, 396, 104)
            pygame.draw.rect(self.screen, (10, 17, 30), plate, border_radius=10)
            pygame.draw.rect(self.screen, (40, 55, 82), plate, 1, border_radius=10)
            pygame.draw.rect(self.screen, char['accent'], (barx - 8, 8, 4, 104),
                             border_radius=2)
            self.rect(barx, 18, 380, 23, (41, 50, 66), 6)
            trail = max(0., min(380., 380 * self.hp_trail[idx] / hp_max))
            if trail > 0:
                tx = barx if idx == 0 else barx + 380 - int(trail)
                self.rect(tx, 18, int(trail), 23, (255, 214, 170), 5)
            filled = max(0., min(380., 380 * self.hp_shown[idx] / hp_max))
            if filled > 0:
                fx = barx if idx == 0 else barx + 380 - int(filled)
                color = GREEN if hp >= hp_max * .4 else RED
                self.rect(fx, 18, int(filled), 23, color, 5)
                pygame.draw.line(self.screen, tuple(min(255, v + 45) for v in color),
                                 (fx + 8, 24), (fx + int(filled) - 8, 24), 2)
            # 灰色护盾条：叠加在血条末端，宽度按护盾/最大血量比例。
            shield = f.get("shield", 0)
            if shield > 0:
                shield_w = max(0., min(380 - filled, 380 * shield / hp_max))
                if idx == 0:
                    sx = barx + int(filled)
                    self.rect(sx, 18, int(shield_w), 23, (160, 160, 170), 5)
                else:
                    sx = barx + 380 - int(filled) - int(shield_w)
                    self.rect(sx, 18, int(shield_w), 23, (160, 160, 170), 5)
                pygame.draw.line(self.screen, (210, 210, 220),
                                 (sx + 2, 22), (sx + int(shield_w) - 2, 22), 1)
            for tick in range(1, 10):
                tx0 = barx + int(380 * tick / 10)
                pygame.draw.line(self.screen, (32, 43, 60), (tx0, 20), (tx0, 39), 1)
            pygame.draw.rect(self.screen, (24, 34, 50), (barx, 18, 380, 23), 1,
                             border_radius=6)
            energy = f.get("energy", 0)
            self.energy_shown[idx] += (energy - self.energy_shown[idx]) * min(1., self.dt * 8)
            en = max(0., min(380., 380 * self.energy_shown[idx] / MAX_ENERGY))
            self.rect(barx, 45, 380, 12, (30, 43, 62), 6)
            # Gold means the super is affordable, not "bar is completely full".
            ready = energy >= attack_spec(f, 'super').energy
            if en > 0:
                ex = barx if idx == 0 else barx + 380 - int(en)
                self.rect(ex, 45, int(en), 12, GOLD if ready else CYAN, 6)
            who, who_tint = self._fighter_label(idx)
            self._hud_line(who, who_tint,
                           f"HP {int(f['hp'])}/{int(f['hp_max'])}", barx, 58, 18)
            self._hud_line(char['name'], mix(char['accent'], WHITE, .45),
                           f"能量 {int(energy)}", barx, 82, 18)
            self.draw_fighter(f, idx)
            if f.get("frozen", 0) > 0:
                self.draw_frozen(f)
            if (f.get("attack_kind") == "super" and f.get("super_radius")
                    and f.get("super_kind") != "grab_pummel"):
                # Radial super: a spinning ring of flame around the body.
                spec = f.get("super_spec") or ATTACKS["super"]
                frame = f.get("action_frame", 0)
                if spec.startup <= frame < spec.startup + spec.active:
                    radius = float(f["super_radius"])
                    cx, cy = WORLD_X_OFF + int(f["x"]), 555 - int(f.get("y", 0)) - 72
                    accent = CHARACTERS.get(f.get("char_id", "red_scarf"),
                                            CHARACTERS["red_scarf"])["accent"]
                    for k in range(12):
                        angle = self.now * 6 + k * (math.pi / 6)
                        inner = radius * .55
                        outer = radius * (1.02 + .03 * math.sin(self.now * 12 + k))
                        pygame.draw.line(
                            self.screen, accent,
                            (cx + math.cos(angle) * inner, cy + math.sin(angle) * inner),
                            (cx + math.cos(angle) * outer, cy + math.sin(angle) * outer), 3)
                    pygame.draw.circle(self.screen, (255, 236, 190), (cx, cy),
                                       int(radius * .5), 2)
            combo = f.get("combo", 0)
            if combo > self.combo_shown[idx]:
                self.combo_shown[idx] = combo
                self.combo_pop[idx] = 1.
            elif combo == 0:
                self.combo_shown[idx] = 0
            self.combo_pop[idx] = max(0., self.combo_pop[idx] - self.dt * 2.6)
            if self.combo_shown[idx] >= 2 and \
                    self.game_state.get("frame", 0) - f.get("last_hit_frame", -9999) < 55:
                pop = self.combo_pop[idx]
                self.text(f"{self.combo_shown[idx]} HITS",
                          190 if idx == 0 else W - 190, 122 - int(9 * pop),
                          26 if pop > .6 else 19, GOLD, True)
        for pillar in self.game_state.get("fire_pillars", []):
            self.draw_fire_pillar(pillar)
        for shard in self.game_state.get("ice_shards", []):
            self.draw_ice_shard(shard)
        scores = self.game_state.get("scores", [0, 0])
        time_left = self.game_state.get("time_left", 65)
        training = self.game_state.get("training_mode", False)
        warn = time_left <= 10
        timer_box = pygame.Rect(W // 2 - 94, 7, 188, 76)
        pygame.draw.rect(self.screen, (8, 14, 26), timer_box.move(0, 4), border_radius=14)
        pygame.draw.rect(self.screen, (18, 29, 49), timer_box, border_radius=13)
        pygame.draw.rect(self.screen, (48, 68, 100), timer_box, 1, border_radius=13)
        pygame.draw.line(self.screen, GOLD, (timer_box.x + 18, timer_box.y + 1),
                         (timer_box.right - 18, timer_box.y + 1), 2)
        self.text(str(math.ceil(time_left)), W // 2, 30, 30,
                  RED if warn and int(self.now * 4) % 2 else GOLD, True, shadow=True)
        if training:
            self.text("技能训练", W // 2, 61, 16, CYAN, True)
        else:
            self.text(f"{scores[0]}   :   {scores[1]}   |   R{self.game_state.get('round', 1)}",
                      W // 2, 61, 16, CYAN, True)
            for side in (0, 1):
                base = W // 2 - 80 if side == 0 else W // 2 + 80
                for win in range(2):
                    px = base + (win * 14 if side == 0 else -win * 14)
                    filled = scores[side] > win
                    pygame.draw.circle(self.screen, GOLD if filled else (44, 60, 88),
                                       (px, 77), 4)
        for strike in self.game_state.get('strikes', []):
            sx = WORLD_X_OFF + int(strike.get('x', 0))
            gy = 555
            tip_y = gy - int(strike.get('y', 0))
            top_y = gy - int(strike.get('top', 620))
            radius = int(strike.get('radius', 70))
            if strike.get('hit'):
                # Short impact flash after the bolt lands.
                fade = max(0., strike.get('life', 0.) / .14)
                flash = int(46 * fade) + 6
                pygame.draw.circle(self.screen, (255, 250, 210), (sx, tip_y), flash)
                pygame.draw.circle(self.screen, (255, 214, 64), (sx, tip_y),
                                   flash + 6, 3)
            elif strike.get('delay', 0) > 0:
                # Warning ring: "two people wide" yellow circle on the floor.
                pulse = .5 + .5 * math.sin(self.now * 12)
                pygame.draw.ellipse(self.screen, (255, 214, 64),
                                    (sx - radius, gy - 15, radius * 2, 30), 3)
                inner = int(radius * (.5 + .2 * pulse))
                pygame.draw.ellipse(self.screen, (255, 240, 150),
                                    (sx - inner, gy - 10, inner * 2, 20), 2)
            else:
                # Falling bolt: a jagged vertical lightning line.
                drop = max(1, tip_y - top_y)
                pts = [(sx if k in (0, 5) else sx + (13 if k % 2 else -13),
                        top_y + int(drop * k / 5)) for k in range(6)]
                pygame.draw.lines(self.screen, (255, 200, 40), False, pts, 8)
                pygame.draw.lines(self.screen, (255, 252, 210), False, pts, 3)
        # 石面鬼之眼：从双眼射出的一道血色激光（画在所有角色之上）。
        for f in self.game_state.get('fighters', []):
            self.draw_laser(f)
        for proj in self.game_state.get('projectiles', []):
            px = WORLD_X_OFF + int(proj["x"])
            py = 555 - int(proj.get("y", NECK_HEIGHT))
            color = proj.get("color", (255, 200, 80))
            size = proj.get("size", 7)
            if proj.get("style") == "beam":
                # Blue ice beam: a straight glowing line with a bright tip.
                direction = 1 if proj.get('vx', 0) >= 0 else -1
                length = max(40, int(proj.get("length", 120)))
                tail_x = px - direction * length
                faint = tuple(int(v * .35) for v in color)
                pygame.draw.line(self.screen, faint, (tail_x, py), (px, py), size + 4)
                pygame.draw.line(self.screen, color, (tail_x, py), (px, py), size)
                pygame.draw.line(self.screen, WHITE,
                                 (tail_x + direction * length // 3, py), (px, py), 2)
                pygame.draw.circle(self.screen, WHITE, (px, py), 3)
                pygame.draw.circle(self.screen, color, (px, py), size, 1)
                continue
            if proj.get("style") == "shuriken":
                # 冰手里剑的十字形刃：四枚刃呈十字形，随飞行持续旋转。
                angle = proj.get("angle", 0.0)
                arm = max(8, int(proj.get("length", 16) or 16))
                # 飞行拖尾。
                tx = px - int(proj.get('vx', 0) * .012)
                pygame.draw.circle(self.screen, tuple(int(v * .35) for v in color),
                                   (tx, py), max(2, size - 2))
                for k in range(2):
                    a = angle + k * math.pi / 2
                    dx, dy = math.cos(a), math.sin(a)
                    tip_x, tip_y = int(px + dx * arm), int(py + dy * arm)
                    butt_x, butt_y = int(px - dx * arm * 0.5), int(py - dy * arm * 0.5)
                    pygame.draw.line(self.screen, color, (butt_x, butt_y),
                                     (tip_x, tip_y), max(2, size - 2))
                    mid_x, mid_y = int(px + dx * arm * 0.3), int(py + dy * arm * 0.3)
                    pygame.draw.line(self.screen, WHITE, (mid_x, mid_y),
                                     (tip_x, tip_y), 1)
                pygame.draw.circle(self.screen, WHITE, (px, py), max(2, size // 2))
                pygame.draw.circle(self.screen, color, (px, py), max(2, size // 2), 1)
                continue
            if proj.get("style") == "knife":
                # 时停飞刀：悬停时是静止的银色刃（带一圈呼吸微光），
                # 时间恢复后拖出淡色尾迹飞向对手。
                direction = int(proj.get("face", 1) or 1)
                if proj.get("vx", 0):
                    direction = 1 if proj["vx"] >= 0 else -1
                blade = max(18, int(proj.get("length", 26)))
                tip_x = px + direction * blade // 2
                butt_x = px - direction * blade // 2
                if not proj.get("frozen"):
                    for k in range(1, 4):
                        tx = px - direction * blade * k
                        faint = tuple(int(v * (.30 + .12 * (3 - k))) for v in color)
                        pygame.draw.line(self.screen, faint, (tx - direction * 10, py),
                                         (tx, py), max(1, size - k))
                else:
                    pulse = int(2 + 2 * (0.5 + 0.5 * math.sin(self.now * 6 + px)))
                    pygame.draw.circle(self.screen, (255, 250, 210), (px, py), pulse + 4, 1)
                pygame.draw.line(self.screen, color, (butt_x, py), (tip_x, py), max(2, size - 1))
                pygame.draw.line(self.screen, WHITE,
                                 (butt_x + direction * 4, py), (tip_x, py), 1)
                # 金色刀柄。
                handle = 8
                pygame.draw.line(self.screen, GOLD, (butt_x, py),
                                 (butt_x - direction * handle, py), 4)
                continue
            if proj.get("style") == "carrier":
                # 让开！推人墙：一面缓行的灰黄色弧面波，半人高。
                direction = 1 if proj.get('vx', 0) >= 0 else -1
                wave_h = 110
                wave_w = max(16, size * 2)
                base = pygame.Rect(px - direction * wave_w, py - wave_h // 2,
                                   wave_w, wave_h)
                # 外层柔光。
                faint = tuple(int(v * .35) for v in color)
                pygame.draw.ellipse(self.screen, faint, base.inflate(14, 10))
                # 主体弧面。
                pygame.draw.ellipse(self.screen, color, base)
                pygame.draw.ellipse(self.screen, _dim(color, .78),
                                    base.inflate(-8, -6), 2)
                # 推起的尘土拖尾。
                for i in range(2, 0, -1):
                    dust_x = px - direction * (wave_w + i * 8)
                    pygame.draw.circle(self.screen, faint,
                                       (dust_x, py + wave_h // 2 - 4), 4 + i)
                continue
            for i in range(3, 0, -1):
                tx = px - int(proj.get('vx', 0) * .012 * i)
                faint = tuple(int(v * (.30 + .16 * (3 - i))) for v in color)
                pygame.draw.circle(self.screen, faint, (tx, py), max(2, size - i * 2))
            pygame.draw.circle(self.screen, color, (px, py), size)
            pygame.draw.circle(self.screen, WHITE, (px, py), size, 1)
            pygame.draw.circle(self.screen, color, (px, py), size + 4, 1)
        for effect in self.effects:
            progress = effect["life"] / effect["max"]
            xx, yy = effect["x"], effect["y"]
            color = effect.get("color", GOLD)
            if effect["kind"] == "hit":
                radius = int((1-progress)*24+8)
                pygame.draw.circle(self.screen, color, (int(xx), int(yy)), radius, 3)
                label = "BLOCK" if effect.get("blocked") else "-" + str(effect["damage"])
                self.text(label, int(xx), int(yy - 33 - 26*(1-progress)), 26, color, True)
            elif effect["kind"] == "shock":
                # Expanding blast ring, used by the radial command super.
                grow = 1 - progress
                radius = int(effect["r0"] + (effect["r1"] - effect["r0"])
                             * (1 - (1 - grow) ** 2))
                width = max(1, int(effect.get("width", 8) * progress))
                pygame.draw.circle(self.screen, color, (int(xx), int(yy)), max(1, radius), width)
                bright = tuple(min(255, v + 70) for v in color)
                pygame.draw.circle(self.screen, bright, (int(xx), int(yy)),
                                   max(1, radius - 10), 2)
            elif effect["kind"] == "slash":
                # A quick diagonal cut for each hit of the rushing super.
                angle = effect.get("angle", -.7)
                length = int(40 + 26 * (1 - progress))
                dx, dy = math.cos(angle) * length, math.sin(angle) * length
                pygame.draw.line(self.screen, color, (int(xx - dx), int(yy - dy)),
                                 (int(xx + dx), int(yy + dy)), 4)
                pygame.draw.line(self.screen, WHITE, (int(xx - dx * .8), int(yy - dy * .8)),
                                 (int(xx + dx * .8), int(yy + dy * .8)), 1)
            elif effect["kind"] == "flame":
                # Grab-super punch: flame tongues burst out of the impact point.
                grow = 1 - progress
                radius = effect.get("radius", 30) * (1 - (1 - grow) ** 2)
                angle = effect.get("angle", 0)
                for k in range(6):
                    a = angle + k * math.pi / 3
                    pygame.draw.line(self.screen, color,
                                     (int(xx + math.cos(a) * radius * .35),
                                      int(yy + math.sin(a) * radius * .35)),
                                     (int(xx + math.cos(a) * radius),
                                      int(yy + math.sin(a) * radius)), 3)
                pygame.draw.circle(self.screen, (255, 245, 200),
                                   (int(xx), int(yy)), max(1, int(radius * .26)), 2)
            elif effect["kind"] == "vortex":
                # Grab-super pull: three flame arcs spiral inward on the caster.
                radius = effect.get("radius", 90) * progress
                spin = (1 - progress) * 5.2
                for k in range(3):
                    pts = []
                    for step in range(12):
                        t = step / 11.
                        a = spin + k * 2.094 + t * 1.6
                        r = radius * (1 - t * .32)
                        pts.append((xx + math.cos(a) * r,
                                    yy + math.sin(a) * r * .55))
                    pygame.draw.lines(self.screen, color, False, pts, 3)
            elif effect["kind"] == "streak":
                # Grab-super throw: a tapered trail from the grab point to the
                # landing spot.
                y0 = effect.get("y", yy)
                width = max(2, int(effect.get("width", 18) * progress))
                pygame.draw.line(self.screen, color, (int(effect["x0"]), int(y0)),
                                 (int(effect["x1"]), int(y0)), width)
                pygame.draw.line(self.screen, (255, 245, 210),
                                 (int(effect["x0"]), int(y0)),
                                 (int(effect["x1"]), int(y0)), max(1, width // 4))
            elif effect["kind"] == "roller":
                # ROAD ROLLER DA!!：压路机从高空砸下，落地后短暂停留。
                drop = int(170 * progress)
                cy = int(yy - 96 - drop)
                body = effect.get("color", (208, 210, 216))
                dark = tuple(int(v * .62) for v in body)
                # 滚筒（横向圆柱）与车架。
                pygame.draw.rect(self.screen, body,
                                 (int(xx) - 52, cy - 22, 104, 44), border_radius=10)
                pygame.draw.rect(self.screen, dark,
                                 (int(xx) - 52, cy - 22, 104, 44), 3, border_radius=10)
                pygame.draw.rect(self.screen, (232, 190, 44),
                                 (int(xx) - 34, cy - 58, 68, 30), border_radius=5)
                pygame.draw.rect(self.screen, (120, 96, 20),
                                 (int(xx) - 34, cy - 58, 68, 30), 2, border_radius=5)
                pygame.draw.circle(self.screen, dark, (int(xx), cy), 16, 3)
                if progress < .55:
                    # 落地冲击：地面扬尘与横向扩散环。
                    grow = 1 - progress
                    pygame.draw.ellipse(self.screen, dark,
                                        (int(xx) - int(70 * grow) - 40, yy - 12,
                                         int(140 * grow) + 80, 24), 3)
            elif effect["kind"] == "label":
                surf = self.fonts[19].render(effect["text"], True, color)
                surf.set_alpha(int(255 * max(0., min(1., progress)) ** .7))
                rect = surf.get_rect(center=(int(xx),
                                             int(yy - 26 * (1 - progress))))
                self.screen.blit(surf, rect)
            else:
                pygame.draw.circle(self.screen, color, (int(xx), int(yy)),
                                   int(8+17*(1-progress)), 2)
        for p in self.particles:
            fade = p["life"] / p["max"]
            pygame.draw.circle(self.screen, p["color"], (int(p["x"]), int(p["y"])),
                               max(1, int(p["size"] * fade)))
        # 砸瓦鲁多：整屏压暗 + 中央倒计时，强调"世界静止"。
        time_stop = self.game_state.get("time_stop", 0.)
        if time_stop and time_stop > 0 and phase == "game":
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((6, 8, 26, 104))
            self.screen.blit(veil, (0, 0))
            blink = int(self.now * 8) % 2
            self.text(f"时间停止  {time_stop:.1f}s", W // 2, H - 30, 24,
                      WHITE if blink else GOLD, True, shadow=True)
        if phase in ("round_end", "match_end"):
            self.panel(W // 2 - 280, 287, 560, 118, (14, 24, 44), 16, (58, 78, 110), GOLD)
            winner = self.game_state.get("round_winner")
            match_winner = self.game_state.get("winner")
            sides = ("电脑" if self.practice_mode == "cpu_vs_cpu" else "玩家") \
                if self.page == "practice" else "玩家"
            if phase == "match_end":
                label = f"{sides} {match_winner + 1} 赢得整场比赛！" if match_winner is not None else "比赛结束"
                sub = "三局两胜 · 即将返回联机房间" if self.page != "practice" else "按 R 再战一场 / ESC 返回"
            else:
                label = "本回合平局" if winner is None else f"{sides} {winner + 1} 赢得本回合！"
                sub = "下一回合即将开始"
            self.text(label, W // 2, 327, 30, GOLD, True, shadow=True)
            self.text(sub, W // 2, 376, 19, MUTED, True)
        if training:
            self.draw_frame_data()
        self.draw_countdown()
        self.draw_banner()
        if self.paused:
            self.pause_overlay()

    def draw_fire_pillar(self, pillar):
        """熔岩地貌：地面预警圈亮起后，喷出一人高的火柱。"""
        sx = WORLD_X_OFF + int(pillar.get("x", 0))
        gy = 555
        radius = int(pillar.get("radius", 70))
        if pillar.get("delay", 0) > 0:
            pulse = .5 + .5 * math.sin(self.now * 14)
            pygame.draw.ellipse(self.screen, (255, 108, 30),
                                (sx - radius, gy - 14, radius * 2, 28), 3)
            inner = int(radius * (.42 + .22 * pulse))
            pygame.draw.ellipse(self.screen, (255, 208, 110),
                                (sx - inner, gy - 9, inner * 2, 18), 2)
            for k in range(6):
                ex = sx + int(math.sin(self.now * 2.6 + k * 1.7) * radius * .72)
                ey = gy - int((self.now * 34 + k * 11) % 42)
                pygame.draw.circle(self.screen, (255, 176, 76), (ex, ey), 2)
            return
        life = float(pillar.get("life", 0.))
        t = 1. - max(0., min(1., life / LAVA_PILLAR_DURATION))
        scale = min(1., t / .16) * (1. - max(0., (t - .7) / .3))
        height = max(6, int(LAVA_PILLAR_HEIGHT * scale))
        width = max(8, int(radius * (1.02 - .3 * t)))
        top = gy - height
        flicker = int(8 * math.sin(self.now * 22))
        pygame.draw.polygon(self.screen, (236, 74, 20), (
            (sx - width, gy),
            (sx - int(width * .70), top + int(height * .30)),
            (sx - int(width * .34) + flicker, top + int(height * .05)),
            (sx + flicker, top - int(height * .06)),
            (sx + int(width * .38) - flicker, top + int(height * .12)),
            (sx + int(width * .72), top + int(height * .40)),
            (sx + width, gy)))
        pygame.draw.polygon(self.screen, (255, 168, 48), (
            (sx - int(width * .62), gy),
            (sx - int(width * .40), top + int(height * .42)),
            (sx + flicker, top + int(height * .18)),
            (sx + int(width * .42), top + int(height * .46)),
            (sx + int(width * .62), gy)))
        pygame.draw.polygon(self.screen, (255, 246, 210), (
            (sx - int(width * .26), gy),
            (sx + flicker // 2, top + int(height * .46)),
            (sx + int(width * .26), gy)))
        pygame.draw.ellipse(self.screen, (255, 196, 96),
                            (sx - radius, gy - 12, radius * 2, 24), 2)
        for k in range(5):
            ex = sx + int(math.sin(self.now * 4 + k * 1.3) * width * .8)
            ey = top + int((self.now * 70 + k * 17) % max(1, height))
            pygame.draw.circle(self.screen, (255, 214, 130), (ex, ey), 2)

    def draw_ice_shard(self, shard):
        """冰雪溶洞：从洞顶直坠而下的冰棱，没有预警，只有极快的落影。"""
        sx = WORLD_X_OFF + int(shard.get("x", 0))
        gy = 555
        height = max(0., float(shard.get("y", 0.)))
        radius = int(shard.get("radius", 44))
        tip_y = gy - int(height)
        half = max(6, int(radius * .86))
        length = 132
        # 地面投影：越接近地面越清晰。
        near = 1. - min(1., height / 520.)
        shadow_w = int(half * (.35 + .65 * near))
        pygame.draw.ellipse(self.screen, (26, 44, 62),
                            (sx - shadow_w, gy - 7, shadow_w * 2, 12))
        if height <= 0.:
            return
        body = [(sx, tip_y),
                (sx - half, tip_y - int(length * .42)),
                (sx - int(half * .55), tip_y - length),
                (sx + int(half * .55), tip_y - length),
                (sx + half, tip_y - int(length * .42))]
        pygame.draw.polygon(self.screen, (126, 186, 222), body)
        pygame.draw.polygon(self.screen, (176, 220, 244), [
            (sx, tip_y), (sx - int(half * .5), tip_y - int(length * .5)),
            (sx - int(half * .16), tip_y - int(length * .88))])
        pygame.draw.lines(self.screen, (238, 252, 255), True, body, 2)
        pygame.draw.line(self.screen, WHITE, (sx - int(half * .36), tip_y - 16),
                         (sx + int(half * .3), tip_y - 16), 1)
        # 高速下落留下的残影。
        for k in range(3):
            ty = tip_y - length - 8 - k * 18
            pygame.draw.line(self.screen, (168, 214, 240), (sx, ty), (sx, ty - 12), 2)

    def draw_frozen(self, f):
        """冰雪溶洞：被冰棱砸中的角色被一层冰壳封住。"""
        cx = WORLD_X_OFF + int(f.get("x", 0))
        gy = 555 - int(f.get("y", 0))
        block = pygame.Rect(cx - 30, gy - 122, 60, 122)
        shell = pygame.Surface((block.width, block.height), pygame.SRCALPHA)
        shell.fill((150, 214, 246, 92))
        self.screen.blit(shell, block)
        pygame.draw.rect(self.screen, (216, 246, 255), block, 2, border_radius=8)
        pygame.draw.polygon(self.screen, (242, 253, 255), [
            (block.x + 10, block.y + 18), (block.x + 32, block.y + 5),
            (block.x + 26, block.y + 32)])
        pygame.draw.line(self.screen, (238, 251, 255),
                         (block.x + 12, block.bottom - 12), (block.x + 29, block.y + 30), 1)
        pygame.draw.line(self.screen, (192, 232, 250),
                         (block.right - 12, block.bottom - 16),
                         (block.right - 26, block.y + 52), 1)

    def _fighter_label(self, idx):
        """HUD 名字：联机用房间昵称；练习模式按本局锁定的难度显示 AI 名。"""
        if self.page != "practice":
            return next((p["nick"] for p in self.players if p["slot"] == idx),
                        "P" + str(idx + 1)), WHITE
        # 读开场锁定的档位而不是设置里的当前值：中途改设置不会让名字和
        # 实际行为分叉。
        level = self.ai[idx].level or self.settings.get("ai_level", "normal")
        if self.practice_mode == "cpu_vs_cpu":
            return f"{AI_LABELS[level]} {idx + 1}", AI_TINTS[level]
        if idx == 0:
            return "你", WHITE
        if self.practice_mode == "training":
            return "训练 AI", WHITE
        return AI_LABELS[level], AI_TINTS[level]

    def _hud_line(self, left, left_color, right, barx, y, size=19):
        """HUD 信息行：左段文字（超宽自动截断），右段数值右对齐防溢出。"""
        max_w = 380 - self.fonts[size].size(right)[0] - 14
        while left and self.fonts[size].size(left)[0] > max_w:
            left = left[:-1]
        self.text(left, barx, y, size, left_color)
        self.text(right, barx + 380 - self.fonts[size].size(right)[0], y, size, WHITE)

    def draw_frame_data(self):
        """技能训练专属：实时显示当前 / 上一招的帧数据、阶段与取消窗口。"""
        if self.page != "practice" or self.practice_mode != "training":
            return
        state = self.game_state
        if state.get("phase") != "game" or self.paused or state.get("countdown", 0) > 0:
            return
        f = self.fighters[0]
        live = f.get("attack_kind") or ""
        if live:
            self.frame_data_move = live
        kind = self.frame_data_move
        label = FRAME_LABELS.get(kind, kind or "—")
        try:
            spec = attack_spec(f, kind) if kind else None
        except KeyError:
            spec = None
        x, y, w, h = 24, 560, 360, 108
        self.panel(x, y, w, h, (11, 19, 32), 12, (44, 62, 92))
        self.text("帧数据 · 训练", x + 14, y + 7, 14, CYAN)
        self.text(label, x + 14, y + 25, 18, WHITE if kind else MUTED)
        if spec is None:
            self.text("普通技 / 特殊技出招后显示帧数据", x + 14, y + 54, 14, MUTED)
            return
        af = int(f.get("action_frame", 0)) if live == kind else -1
        if af < 0:
            phase, tint = "待机", MUTED
        elif af < spec.startup:
            phase, tint = "起手", GOLD
        elif af < spec.startup + spec.active:
            phase, tint = "有效", RED
        else:
            phase, tint = "收招", CYAN
        phase_txt = f"{phase} {af + 1}/{spec.total}" if af >= 0 else phase
        self.text(phase_txt, x + w - 14 - self.fonts[15].size(phase_txt)[0],
                  y + 27, 15, tint)
        self.text(f"起手 {spec.startup}   有效 {spec.active}   收招 {spec.recovery}",
                  x + 14, y + 50, 15, MUTED)
        hit_adv, blk_adv = spec.hit_advantage, spec.block_advantage
        self.text(f"命中 {hit_adv:+d}", x + 14, y + 69, 15,
                  GREEN if hit_adv >= 0 else RED)
        self.text(f"格挡 {blk_adv:+d}", x + 118, y + 69, 15,
                  GREEN if blk_adv >= 0 else RED)
        if f.get("combo", 0) > 1:
            self.text(f"连段 {f['combo']} 段", x + 232, y + 69, 15, GOLD)
        cancel_left = int(f.get("cancel_left", 0)) if live == kind else 0
        air_left = int(f.get("air_cancel_left", 0)) if live == kind else 0
        if air_left > 0:
            cancel_txt, c_color = f"空中挥空取消 · 剩 {air_left} 帧", GOLD
        elif cancel_left > 0:
            cancel_txt, c_color = f"取消窗口 · 剩 {cancel_left} 帧", GOLD
        elif spec.cancel:
            cancel_txt, c_color = f"取消窗口 {spec.cancel} 帧（命中后开）", MUTED
        else:
            cancel_txt, c_color = "不可取消", MUTED
        self.text(cancel_txt, x + 14, y + 87, 14, c_color)

    def draw_laser(self, f, ground=555):
        """石面鬼之眼：一条从双眼射出的血色细光柱，打到墙就断。"""
        if f.get('attack_kind') != 'laser':
            return
        frame = int(f.get('action_frame', 0))
        cfg = f.get('projectile_config') or {}
        color = cfg.get('color', (214, 24, 46))
        face = f.get('face', 1)
        eye_y = ground - int(f.get('y', 0) +
                             (LASER_CROUCH_EYE_HEIGHT if f.get('laser_low')
                              else LASER_EYE_HEIGHT))
        sx = WORLD_X_OFF + int(f['x'] + face * 9)
        # 起手阶段：眼中的红光逐渐收束成线。
        if frame < LASER_STARTUP:
            t = (frame + 1) / float(max(1, LASER_STARTUP))
            pygame.draw.circle(self.screen, _dim(color, .9), (sx, eye_y),
                               int(4 + 9 * t), 2)
            pygame.draw.circle(self.screen, (255, 240, 242), (sx, eye_y), 3)
            return
        wall = ((ARENA_RIGHT - f['x']) if face > 0 else (f['x'] - ARENA_LEFT))
        length = max(0., min(float(cfg.get('length', 430.)), wall))
        end_y = eye_y
        # 光柱打在对手身上时略微下压到其胸口，蹲姿也能看出"烧在身上"，而不是
        # 从头顶飞过去。
        for g in self.game_state.get('fighters', []):
            if g is f or g.get('knocked') or g.get('invuln', 0) > 0:
                continue
            distance = (g['x'] - f['x']) * face
            if not (0. <= distance <= length):
                continue
            low, high = body_span(g)
            top = ground - int(high)
            bottom = ground - int(low)
            if top - LASER_HALF_THICK <= eye_y <= bottom + LASER_HALF_THICK:
                end_y = max(top + 4, min(bottom - 4, eye_y))
                length = distance
                break
        ex = WORLD_X_OFF + int(f['x'] + face * (9 + length))
        if ex == sx:
            return
        # 外层柔光 + 内层亮芯，末端收一个爆点。
        pygame.draw.line(self.screen, _dim(color, .30), (sx, eye_y), (ex, end_y), 13)
        pygame.draw.line(self.screen, _dim(color, .72), (sx, eye_y), (ex, end_y), 6)
        pygame.draw.line(self.screen, (255, 226, 230), (sx, eye_y), (ex, end_y), 2)
        pygame.draw.circle(self.screen, color, (ex, end_y), 6, 1)
        pygame.draw.circle(self.screen, (255, 236, 238), (ex, end_y), 2)
        pygame.draw.circle(self.screen, _dim(color, .55), (sx, eye_y), 11, 2)

    def draw_fighter(self, f, idx, ground=555):
        if f.get('attack_kind') == 'ice_shadow' and shadow_phase(f) in ('burrow', 'hide'):
            self._draw_shadow_marker(f, idx, ground)
            return
        draw_stickman(pygame, self.screen, f, idx, ground, WORLD_X_OFF)

    def _draw_shadow_marker(self, f, idx, ground=555):
        """冰千年杀潜行标记：一小撮尘土从钻入点缓缓移向敌人脚下。"""
        accent = CHARACTERS.get(f.get("char_id", "red_scarf"),
                                CHARACTERS["red_scarf"])["accent"]
        x = WORLD_X_OFF + int(f['x'])
        enemy_x = x
        if len(self.fighters) > 1:
            enemy_x = WORLD_X_OFF + int(self.fighters[1 - idx]['x'])
        phase = shadow_phase(f)
        if phase == 'burrow':
            t = f.get('action_frame', 0) / float(SHADOW_BURROW)
            mx = x + (enemy_x - x) * t
            r = max(3, int(10 * (1. - t)))
        else:
            t = (f.get('action_frame', 0) - float(SHADOW_BURROW)) / float(SHADOW_HIDE)
            mx = x + (enemy_x - x) * max(0., min(1., t))
            r = 3
        pygame.draw.circle(self.screen, mix(accent, (20, 24, 34), .3),
                           (int(mx), ground), r)
