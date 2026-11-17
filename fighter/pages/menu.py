"""Main-menu screen: logo, character cards and mode buttons."""
import math

import pygame

from .. import assets
from ..arena import DEFAULT_MAP, MAPS, AI_SHORT, AI_TINTS
from ..characters import CHARACTERS
from ..config import AI_LEVELS, save_settings
from ..theme import (W, H, PANEL_HI, WHITE, MUTED, BLUE, CYAN, GOLD, shade,
                     mix)


class MenuPage:
    """Main menu page.

    Mixin for :class:`fighter.ui.GameApp`; no ``__init__`` of its own. Expects
    the host to provide ``screen``, ``controls``, ``button_glow``, ``dt``,
    ``now``, ``char_p1`` / ``char_p2`` and the shared helpers ``text`` /
    ``rect`` / ``button`` / ``portrait_image`` / ``fighter_art``.
    """

    def menu(self):
        pulse = .5 + .5 * math.sin(self.now * 2.2)
        # ---- neon halo behind the logo ----
        halo = pygame.Surface((560, 440), pygame.SRCALPHA)
        for step in range(22):
            radius = 200 - step * 7
            pygame.draw.circle(halo, (34, 104, 176, 3 + step), (280, 196), max(4, radius))
        self.screen.blit(halo, (W // 2 - 280, -34))
        # Title lockup: a closed ring at this radius cut through "LAN" /
        # "FIGHTER" and the 451px-wide subtitle, so the logo is framed by a
        # symmetric rule with pulsing end caps instead.
        self.text("LAN", W // 2, 128, 56, CYAN, True, True)
        self.text("FIGHTER", W // 2, 188, 56, WHITE, True, True)
        rule = 222
        pygame.draw.line(self.screen, (34, 66, 108), (W // 2 - 310, rule + 1),
                         (W // 2 + 310, rule + 1), 2)
        pygame.draw.line(self.screen, (58, 118, 176), (W // 2 - 310, rule),
                         (W // 2 + 310, rule), 1)
        for cap_x in (W // 2 - 310, W // 2 + 310):
            pygame.draw.circle(self.screen, (44, 120, 180), (cap_x, rule),
                               int(7 + 3 * pulse), 1)
            pygame.draw.circle(self.screen, CYAN, (cap_x, rule), 3)
        self.text("融合型火柴人格斗", W // 2, 248, 18, MUTED, True)
        self.rect(W - 154, 28, 112, 34, (17, 28, 48), 17, (54, 86, 130))
        self.text("LAN 3.0", W - 98, 45, 16, CYAN, True)
        self.menu_char_card(0, W // 2 - 338)
        self.menu_char_card(1, W // 2 + 338)
        # 「AI 对打」两侧各有自己的档位，芯片直接挂在 P2 角色卡上方排成两枚，
        # 点一下前进一档，不用弹浮层，也不占中间按钮列的空间。
        for slot, x in ((0, W // 2 + 234), (1, W // 2 + 342)):
            self.ai_dual_chip((x, 234, 100, 30), slot)
        # One primary CTA, three secondary entries, one quiet utility: the old
        # five saturated hues competed with the character cards for attention.
        self.button("对战 AI", (W // 2 - 190, 274, 380, 54), self.practice, BLUE)
        self.button("技能训练", (W // 2 - 190, 346, 380, 54), self.training, PANEL_HI)
        self.button("AI 对打", (W // 2 - 190, 418, 380, 54), self.cpu_vs_cpu, PANEL_HI)
        self.button("双人对抗", (W // 2 - 190, 490, 380, 54), self.open_lan,
                    mix(PANEL_HI, CYAN, .20))
        self.button("设置", (W // 2 - 190, 562, 380, 54), self.open_settings,
                    shade(PANEL_HI, .86))
        self.button(f"地图 · {self.current_map_name()}", (W - 330, 620, 250, 48),
                    self.open_map_picker, mix(PANEL_HI, GOLD, .18))
        self.text("ESC 退出程序", W // 2, 646, 16, MUTED, True)
        if self.map_picker_open:
            self.map_picker()

    def current_map_name(self):
        return MAPS.get(self.settings.get("map", DEFAULT_MAP), MAPS[DEFAULT_MAP])["name"]

    def open_map_picker(self):
        self.map_picker_open = True
        self.map_scroll = 0.

    def close_map_picker(self):
        self.map_picker_open = False

    def choose_map(self, map_id):
        self.settings["map"] = map_id
        self.map_picker_open = False
        try:
            save_settings(self.settings)
        except OSError:
            self.notify("地图已切换，但保存设置失败")
        else:
            self.notify(f"已选择地图：{MAPS[map_id]['name']}")

    def map_picker(self):
        """地图选择面板：卡片按三列纵排，滚轮上下浏览，地图再多也不会挤出面板。"""
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((4, 8, 15, 200))
        self.screen.blit(veil, (0, 0))
        self.panel(W // 2 - 490, 150, 980, 420, (18, 29, 49), 20, (64, 88, 122), GOLD)
        self.text("选择地图", W // 2, 192, 30, WHITE, True, shadow=True)
        self.text("每张舞台都有专属场地机关 · 联机时以房主所选地图为准",
                  W // 2, 226, 15, MUTED, True)
        # 先注册全屏拦截，避免点击面板外误触菜单按钮；卡片随后加入，优先响应。
        self.controls.append((pygame.Rect(0, 0, W, H), None))
        # ---- 网格与滚动几何（与选角页一致：纵向滚动）----
        view = pygame.Rect(W // 2 - 455, 248, 910, 252)
        cards = list(MAPS.items())
        card_w, card_h, gap_x, gap_y = 291, 220, 18, 18
        cols = 3
        rows = (len(cards) + cols - 1) // cols
        total_h = rows * card_h + max(0, rows - 1) * gap_y
        max_scroll = max(0, total_h - view.height)
        self.map_scroll = max(0., min(float(self.map_scroll), float(max_scroll)))
        top = view.y - int(self.map_scroll)
        if max_scroll == 0:
            top = view.y + (view.height - total_h) // 2
        # 裁剪是保证卡片不出框的关键：滚到视口外的部分直接切掉。
        clip = self.screen.get_clip()
        self.screen.set_clip(view)
        for idx, (map_id, data) in enumerate(cards):
            row, col = divmod(idx, cols)
            row_count = min(cols, len(cards) - row * cols)
            row_w = row_count * card_w + (row_count - 1) * gap_x
            x = view.centerx - row_w // 2 + col * (card_w + gap_x)
            card = pygame.Rect(x, top + row * (card_h + gap_y), card_w, card_h)
            self.map_card(map_id, data, card, card.clip(view))
        self.screen.set_clip(clip)
        if max_scroll > 0:
            # 视口上下边缘渐隐，提示还有内容。
            fade = pygame.Surface((view.width, 26), pygame.SRCALPHA)
            for row_y in range(26):
                pygame.draw.line(fade, (18, 29, 49, int(250 * (row_y / 25) ** 2)),
                                 (0, row_y), (view.width, row_y))
            if top + total_h > view.bottom:
                self.screen.blit(fade, (view.left, view.bottom - 26))
            if top < view.top:
                self.screen.blit(pygame.transform.flip(fade, False, True),
                                 (view.left, view.top))
            track = pygame.Rect(view.right + 6, view.y, 5, view.height)
            pygame.draw.rect(self.screen, (32, 46, 68), track, border_radius=3)
            thumb_h = max(48, int(view.height * view.height / total_h))
            ratio = self.map_scroll / max_scroll
            thumb = pygame.Rect(track.x,
                                view.y + int((view.height - thumb_h) * ratio),
                                5, thumb_h)
            pygame.draw.rect(self.screen, CYAN, thumb, border_radius=3)
        hint = "滚轮上下浏览 · 点击卡片切换地图" if max_scroll > 0 else "点击卡片切换地图"
        self.text(hint, W // 2, 506, 14, MUTED, True)
        self.button("关闭", (W // 2 - 80, 522, 160, 40), self.close_map_picker, PANEL_HI)

    def map_card(self, map_id, data, card, hit):
        selected = self.settings.get("map", DEFAULT_MAP) == map_id
        accent = GOLD if selected else (56, 84, 118)
        key = ("map", map_id)
        # 完全滚出视口的卡片不绘制、不响应悬停，只保留一个空命中区。
        if hit.width <= 0 or hit.height <= 0:
            self.button_glow[key] = 0.
            self.controls.append((hit, lambda m=map_id: self.choose_map(m)))
            return
        hovered = hit.collidepoint(self.mouse)
        glow = self.button_glow.get(key, 0.)
        glow += ((1. if hovered else 0.) - glow) * min(1., self.dt * 11)
        self.button_glow[key] = glow
        # 滚动状态下不做上浮，避免悬停时被视口裁掉边。
        top = card.y
        pygame.draw.rect(self.screen, (5, 9, 17),
                         (card.x, top + 6, card.width, card.height), border_radius=18)
        pygame.draw.rect(self.screen, (17, 27, 44) if selected else (12, 20, 34),
                         (card.x, top, card.width, card.height), border_radius=16)
        pygame.draw.rect(self.screen,
                         accent if selected or glow > .05 else (44, 62, 92),
                         (card.x, top, card.width, card.height), 2, border_radius=16)
        preview = pygame.Rect(card.x + 12, top + 12, card.width - 24, 108)
        art = (assets.cover("backgrounds", data["bg"], preview.size)
               if data.get("bg") else None)
        if art is not None:
            self.screen.blit(art, preview)
        else:
            for step in range(9):
                color = mix(data["sky_top"], data["sky_bottom"], step / 8.)
                pygame.draw.rect(self.screen, color,
                                 (preview.x, preview.y + step * 12, preview.width, 12))
            pygame.draw.circle(self.screen, mix(data["sky_top"], data["lip"], .45),
                               (preview.centerx, preview.bottom - 16), 30, 2)
            pygame.draw.line(self.screen, data["lip"], (preview.x, preview.bottom - 14),
                             (preview.right, preview.bottom - 14), 2)
        pygame.draw.rect(self.screen, accent, preview, 1, border_radius=8)
        self.text(data["name"], card.centerx, top + 138, 22, accent, True)
        self.text(data["desc"], card.centerx, top + 164, 14, MUTED, True)
        self.rect(card.centerx - 46, top + 188, 92, 26,
                  mix(accent, (10, 18, 30), .7), 13, accent)
        self.text("使用中" if selected else "点击选择", card.centerx, top + 201, 14,
                  accent if selected else CYAN, True)
        self.controls.append((hit, lambda m=map_id: self.choose_map(m)))

    # ------------------------------------------------------------- AI 难度
    def ai_chip(self, rect, label, tint, action, size=18, key=None):
        """难度芯片：小胶囊按钮，点击执行 action。

        key 用于稳定悬停缓动：直选芯片的标签会随档位变化，不能拿标签当键，
        否则每切一档光晕都要从零重来。
        """
        r = pygame.Rect(rect)
        key = key or ("ai-chip", r.x, r.y, label)
        hovered = r.collidepoint(self.mouse)
        glow = self.button_glow.get(key, 0.)
        glow += ((1. if hovered else 0.) - glow) * min(1., self.dt * 12)
        self.button_glow[key] = glow
        bg = mix(shade(tint, .52), WHITE, .10 + .16 * glow)
        draw = r.inflate(int(6 * glow), int(4 * glow))
        pygame.draw.rect(self.screen, (5, 9, 17), draw.move(0, 3), border_radius=11)
        pygame.draw.rect(self.screen, bg, draw, border_radius=10)
        pygame.draw.rect(self.screen, mix(tint, WHITE, .50), draw, 1, border_radius=10)
        self.text(label, draw.centerx - 4, draw.centery, size, WHITE, True, shadow=True)
        ax = draw.right - 13
        pygame.draw.polygon(self.screen, mix(WHITE, tint, .25), (
            (ax - 4, draw.centery - 3), (ax + 4, draw.centery - 3),
            (ax, draw.centery + 3)))
        self.controls.append((r, action))

    def ai_dual_chip(self, rect, slot):
        """「AI 对打」单侧档位芯片：直选，点一下在四档里前进一档。"""
        level = self.settings[f"ai_level_p{slot + 1}"]
        side = "左" if slot == 0 else "右"
        self.ai_chip(rect, f"{side} {AI_SHORT[level]}", AI_TINTS[level],
                     lambda: self.cycle_ai_level(slot), 15, ("ai-dual", slot))

    def cycle_ai_level(self, slot):
        level = self.settings[f"ai_level_p{slot + 1}"]
        step = AI_LEVELS.index(level) if level in AI_LEVELS else -1
        self.set_ai_level(AI_LEVELS[(step + 1) % len(AI_LEVELS)], slot)

    def open_ai_picker(self):
        self.ai_picker_open = True
        # 设置页可能正有输入框在聚焦：先提交并失焦，免得浮层开着还在吃键盘。
        if self.focus:
            self.set_focus(None)

    def close_ai_picker(self):
        self.ai_picker_open = False

    def choose_ai_level(self, level):
        self.set_ai_level(level)
        self.ai_picker_open = False

    def ai_picker(self):
        """难度浮层：「对战 AI」的对手档位，四档单选。"""
        top, height = 214, 268
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((4, 8, 15, 200))
        self.screen.blit(veil, (0, 0))
        self.panel(W // 2 - 280, top, 560, height, (18, 29, 49), 20,
                   (64, 88, 122), CYAN)
        self.text("AI 难度", W // 2, top + 40, 30, WHITE, True, shadow=True)
        self.text("开局后本局固定 · 改选只在下一局生效", W // 2, top + 74, 15,
                  MUTED, True)
        # 先注册全屏拦截：点面板外只关闭浮层，不会误触下面的菜单 / 设置按钮。
        self.controls.append((pygame.Rect(0, 0, W, H), self.close_ai_picker))
        self._ai_level_row(top + 112)
        self.button("关闭", (W // 2 - 80, top + height - 72, 160, 44),
                    self.close_ai_picker, PANEL_HI)

    def _ai_level_row(self, y):
        """一行四档难度按钮。"""
        current = self.settings["ai_level"]
        for i, value in enumerate(AI_LEVELS):
            self.button(AI_SHORT[value], (W // 2 - 256 + i * 130, y, 118, 44),
                        lambda v=value: self.choose_ai_level(v),
                        AI_TINTS[value] if current == value else PANEL_HI)

    def menu_char_card(self, slot, cx):
        """Clickable character card beside the menu buttons (left = P1, right = AI)."""
        cid = self.char_p1 if slot == 0 else self.char_p2
        style = CHARACTERS[cid]
        accent = style['accent']
        title = "P1 · 玩家" if slot == 0 else "人机 · 对手"
        card = pygame.Rect(cx - 106, 274, 212, 342)
        hovered = card.collidepoint(self.mouse)
        key = ("menu-char", slot)
        glow = self.button_glow.get(key, 0.)
        glow += ((1. if hovered else 0.) - glow) * min(1., self.dt * 11)
        self.button_glow[key] = glow
        lift = int(glow * 7)
        top = card.y - lift
        pygame.draw.rect(self.screen, (5, 9, 17),
                         (card.x, top + 7, card.width, card.height), border_radius=20)
        pygame.draw.rect(self.screen, shade(PANEL_HI, .74),
                         (card.x, top, card.width, card.height), border_radius=18)
        face = pygame.Rect(card.x + 2, top + 2, card.width - 4, card.height - 4)
        pygame.draw.rect(self.screen, PANEL_HI, face, border_radius=16)
        pygame.draw.rect(self.screen, mix(PANEL_HI, accent, .30),
                         (card.x + 4, top + 4, card.width - 8, 5), border_radius=2)
        pygame.draw.rect(self.screen, accent if glow > .05 else (52, 72, 104),
                         (card.x, top, card.width, card.height), 2, border_radius=18)
        # role chip
        chip = pygame.Rect(cx - 52, top + 16, 104, 26)
        self.rect(*chip, shade(accent, .32), 13, accent)
        self.text(title, cx, chip.centery, 15, WHITE, True)
        # art: portrait image when provided, otherwise the animated stickman
        art = self.portrait_image(cid, 168)
        if art is not None:
            self.screen.blit(art, art.get_rect(center=(cx, top + 130)))
        else:
            figure = self.fighter_art(cid, (160, 190), walk=self.now * 3.2 + slot * 2,
                                      face=1 if slot == 0 else -1)
            self.screen.blit(figure, (cx - 80, top + 36))
        # Name block is anchored to the card bottom so both cards read as the
        # same height as the five-button column beside them.
        pygame.draw.line(self.screen, (48, 66, 96),
                         (card.x + 16, top + 246), (card.x + card.width - 16, top + 246), 1)
        self.text(style['name'], cx, top + 274, 24, accent, True, True)
        self.text("远程：" + style['projectile']['name'], cx, top + 302, 16, MUTED, True)
        self.text("点击更换角色", cx, top + 330, 14, CYAN if glow > .4 else MUTED, True)
        self.controls.append((card, lambda s=slot: self.open_select(s)))
