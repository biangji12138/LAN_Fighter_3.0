"""Character-selection screen and its navigation/state handlers."""
import pygame

from ..characters import CHARACTERS
from ..theme import (PANEL, PANEL_HI, WHITE, MUTED, CYAN,
                     GREEN, GOLD, shade, mix)


class SelectPage:
    """Character selection page.

    Mixin for :class:`fighter.ui.GameApp`; no ``__init__`` of its own. Expects
    the host to provide ``screen``, ``controls``, ``card_glow``, ``dt``,
    ``now``, ``select_slot`` / ``select_scroll`` / ``select_mode``,
    ``char_p1`` / ``char_p2``, ``client`` and the shared helpers ``header`` /
    ``panel`` / ``text`` / ``rect`` / ``button`` / ``portrait_image`` /
    ``fighter_art``.
    """

    def open_select(self, slot):
        self.select_slot = slot
        self.select_scroll = 0.0
        self.select_mode = "menu"
        self.page = "select"

    def open_lan_select(self):
        if not self.client:
            return
        self.select_slot = self.client.slot or 0
        self.select_scroll = 0.0
        self.select_mode = "lan_pick"
        self.page = "select"

    def pick_char(self, slot, char_id):
        if slot == 0:
            self.char_p1 = char_id
        else:
            self.char_p2 = char_id

    def confirm_select(self):
        if self.select_mode == "lan_pick":
            if not self.client:
                self.page = "menu"
                return
            slot = self.client.slot or 0
            cid = self.char_p1 if slot == 0 else self.char_p2
            self.client.send({"type": "char", "char": cid})
            self.page = "room"
        else:
            self.page = "menu"

    def back_from_select(self):
        self.page = "room" if self.select_mode == "lan_pick" and self.client else "menu"

    def select_page(self):
        slot = self.select_slot
        chosen = self.char_p1 if slot == 0 else self.char_p2
        if self.select_mode == "lan_pick":
            who = "P1 · 你" if slot == 0 else "P2 · 你"
            self.header("选择我的角色", f"联机中只为自己选择角色 · {who}")
        else:
            who = "P1 · 玩家" if slot == 0 else "人机 / P2 · 对手"
            self.header("选择角色", f"正在为 {who} 选择角色")
        self.panel(225, 157, 760, 490, PANEL, 18, (47, 66, 98),
                   CHARACTERS[chosen]['accent'])
        mouse = self.mouse
        items = list(CHARACTERS.items())
        # ---- grid geometry ----
        # The scroll axis is vertical: extra characters add rows below the
        # first one instead of stretching a single row past the panel.
        view = pygame.Rect(245, 196, 720, 282)
        card_w, card_h, gap_x, gap_y = 168, 200, 26, 18
        cols = max(1, (view.width + gap_x) // (card_w + gap_x))
        rows = (len(items) + cols - 1) // cols
        total_h = rows * card_h + max(0, rows - 1) * gap_y
        max_scroll = max(0, total_h - view.height)
        self.select_scroll = max(0., min(float(self.select_scroll), float(max_scroll)))
        # A grid shorter than the viewport is centred; a taller one starts at
        # view.y and only moves up by the clamped offset, so the first row can
        # never slide above the panel even if the wheel keeps spinning.
        top = view.y - int(self.select_scroll)
        if max_scroll == 0:
            top = view.y + (view.height - total_h) // 2
        # Clipping is what actually keeps cards inside the frame: artwork and
        # outlines are cut at the viewport edge instead of bleeding over the
        # panel border or the footer.
        clip = self.screen.get_clip()
        self.screen.set_clip(view)
        for idx, (cid, style) in enumerate(items):
            row, col = divmod(idx, cols)
            row_count = min(cols, len(items) - row * cols)
            row_w = row_count * card_w + (row_count - 1) * gap_x
            cx = view.centerx - row_w // 2 + col * (card_w + gap_x) + card_w // 2
            card = pygame.Rect(cx - card_w // 2, top + row * (card_h + gap_y), card_w, card_h)
            # Hit area is the visible part only: the clipped remainder must not
            # react to hover or clicks, and a fully hidden card gets an empty
            # rect that can never be hit.
            hit = card.clip(view)
            accent = style['accent']
            if hit.height == 0 or hit.width == 0:
                self.card_glow[("card", cid)] = 0.
                self.controls.append((hit, ("card", slot, cid)))
                continue
            key = ("card", cid)
            glow = self.card_glow.get(key, 0.)
            glow += ((1. if hit.collidepoint(mouse) else 0.) - glow) * min(1., self.dt * 9)
            self.card_glow[key] = glow
            # Hover stays glow + rim only: a vertical lift would be sliced off
            # by the clip rect on whichever row sits against the frame edge.
            selected = chosen == cid
            ctop = card.y
            pygame.draw.rect(self.screen, (5, 9, 17),
                             (card.x, ctop + 5, card_w, card_h), border_radius=13)
            pygame.draw.rect(self.screen, shade(PANEL_HI, .76),
                             (card.x, ctop, card_w, card_h), border_radius=12)
            pygame.draw.rect(self.screen, PANEL_HI,
                             (card.x + 2, ctop + 2, card_w - 4, card_h - 4),
                             border_radius=10)
            pygame.draw.rect(self.screen, mix(PANEL_HI, accent, .42),
                             (card.x + 4, ctop + 4, card_w - 8, 3), border_radius=2)
            rim = accent if (selected or glow > .05) else (52, 72, 104)
            pygame.draw.rect(self.screen, rim, (card.x, ctop, card_w, card_h),
                             2, border_radius=12)
            if selected:
                pygame.draw.rect(self.screen, accent,
                                 (card.x - 2, ctop - 2, card_w + 4, card_h + 4),
                                 1, border_radius=13)
            # art: portrait when provided, procedural stickman otherwise
            art = self.portrait_image(cid, 92)
            if art is not None:
                self.screen.blit(art, art.get_rect(center=(cx, ctop + 74)))
            else:
                figure = self.fighter_art(cid, (104, 124),
                                          walk=self.now * 3.2 + idx * 1.5)
                self.screen.blit(figure, (cx - 52, ctop + 8))
            if selected:
                center = (card.right - 16, ctop + 16)
                pygame.draw.circle(self.screen, accent, center, 9)
                pygame.draw.circle(self.screen, WHITE, center, 9, 1)
                pygame.draw.line(self.screen, WHITE,
                                 (center[0] - 3, center[1]),
                                 (center[0] - 1, center[1] + 2), 2)
                pygame.draw.line(self.screen, WHITE,
                                 (center[0] - 1, center[1] + 2),
                                 (center[0] + 4, center[1] - 3), 2)
            pygame.draw.line(self.screen, (48, 66, 96),
                             (card.x + 12, ctop + card_h - 62),
                             (card.x + card_w - 12, ctop + card_h - 62), 1)
            self.text(style['name'], cx, ctop + card_h - 44, 19, accent, True)
            self.text("双击查看详情", cx, ctop + card_h - 22, 14,
                      CYAN if glow > .4 else MUTED, True)
            self.controls.append((hit, ("card", slot, cid)))
        self.screen.set_clip(clip)
        # Fade the rows that run past the viewport edge, so a peeking card reads
        # as "more below" instead of a hard slice through the artwork.
        if max_scroll > 0:
            fade = pygame.Surface((view.width, 26), pygame.SRCALPHA)
            for row_y in range(26):
                pygame.draw.line(fade, (*PANEL, int(250 * (row_y / 25) ** 2)),
                                 (0, row_y), (view.width, row_y))
            if top + total_h > view.bottom:
                self.screen.blit(fade, (view.left, view.bottom - 26))
            if top < view.top:
                self.screen.blit(pygame.transform.flip(fade, False, True),
                                 (view.left, view.top))
        if max_scroll > 0:
            # Vertical scrollbar pinned to the panel's inner edge.
            track = pygame.Rect(view.right + 6, view.y, 5, view.height)
            pygame.draw.rect(self.screen, (32, 46, 68), track, border_radius=3)
            thumb_h = max(48, int(view.height * view.height / total_h))
            ratio = self.select_scroll / max_scroll
            thumb = pygame.Rect(track.x, view.y + int((view.height - thumb_h) * ratio),
                                5, thumb_h)
            pygame.draw.rect(self.screen, CYAN, thumb, border_radius=3)
        slot_label = "P1" if slot == 0 else "P2"
        self.text(f"当前 {slot_label} 角色：{CHARACTERS[chosen]['name']}", 605, 500, 19, GOLD, True)
        hint = "单击卡片选择角色 · 双击卡片查看角色展示"
        if max_scroll > 0:
            hint = "滚轮上下浏览 · " + hint
        self.text(hint, 605, 524, 16, MUTED, True)
        self.button("确认", (455, 558, 300, 48), self.confirm_select, GREEN)
        self.button("返回", (260, 558, 150, 48), self.back_from_select, PANEL_HI)
