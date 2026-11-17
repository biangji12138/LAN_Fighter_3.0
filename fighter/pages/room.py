"""Multiplayer room lobby: player slots, ready toggle and match start."""
import pygame

from ..characters import CHARACTERS
from ..theme import (PANEL, PANEL_HI, WHITE, MUTED, BLUE, CYAN, RED,
                     GREEN, GOLD, shade)

from .lan import local_ip


class RoomPage:
    """Room lobby page.

    Mixin for :class:`fighter.ui.GameApp`; no ``__init__`` of its own. Expects
    the host to provide ``screen``, ``controls``, ``fields``, ``players``,
    ``ready``, ``client`` / ``server``, ``char_p1`` / ``char_p2`` and the
    shared helpers ``header`` / ``panel`` / ``rect`` / ``text`` / ``button`` /
    ``draw_avatar``.
    """

    def room(self):
        self.header("对战房间", "联机后选择自己的角色并准备，房主可发起游戏")
        self.panel(170, 160, 870, 447, PANEL, 18, (47, 66, 98), CYAN)
        self.text("房间端口：" + self.fields["port"], 213, 186, 21, CYAN)
        self.text("房主 IP：" + local_ip() if self.server else "已连接至：" + self.fields["server_ip"],
                  213, 218, 18, MUTED)
        pygame.draw.line(self.screen, (46, 63, 92), (205, 254), (1005, 254), 1)
        for i, x in enumerate((210, 635)):
            peer = next((p for p in self.players if p["slot"] == i), None)
            occupied = peer is not None
            accent = (68, 132, 190) if occupied else (44, 58, 84)
            self.panel(x, 284, 365, 171, shade(PANEL_HI, .92), 14, accent)
            self.rect(x + 16, 300, 90, 22, shade(accent, .42), 11)
            self.text("玩家 " + str(i + 1), x + 61, 311, 14, WHITE, True)
            self.text("房主" if i == 0 else "客机", x + 118, 303, 16, MUTED)
            if peer:
                style = CHARACTERS.get(peer.get("char", ""), CHARACTERS["red_scarf"])
                self.draw_avatar(style['id'], x + 62, 390, 58, style['accent'])
                self.text(peer["nick"], x + 118, 366, 25, WHITE)
                mine = self.client and peer["slot"] == self.client.slot
                self.text("角色：" + style['name'] + ("  ·  你" if mine else ""),
                          x + 118, 400, 18, style['accent'])
                color = GREEN if peer["ready"] else GOLD
                pill = pygame.Rect(x + 118, 424, 82, 22)
                self.rect(*pill, shade(color, .30), 11, color)
                self.text("已准备" if peer["ready"] else "未准备",
                          pill.centerx, pill.centery, 14, color, True)
            else:
                pygame.draw.circle(self.screen, (52, 68, 96), (x + 62, 390), 29, 1)
                self.text("?", x + 62, 390, 24, (78, 96, 126), True)
                self.text("等待玩家加入...", x + 118, 382, 22, MUTED)
                self.text("角色：—", x + 118, 412, 18, MUTED)
                self.text("空位", x + 118, 436, 16, MUTED)
        self.button("取消准备" if self.ready else "准备", (215, 495, 210, 56), self.toggle_ready,
                    PANEL_HI if self.ready else GREEN)
        self.button("选择角色", (455, 495, 200, 56), self.open_lan_select, PANEL_HI)
        self.button("开始对战", (694, 495, 256, 59), self.start_game, BLUE,
                    bool(self.client and self.client.slot == 0 and len(self.players) == 2 and
                         all(p["ready"] for p in self.players)))
        self.button("退出房间", (115, 620, 185, 45), self.back, RED)

    def toggle_ready(self):
        if self.client:
            self.ready = not self.ready
            if self.ready:
                slot = self.client.slot or 0
                cid = self.char_p1 if slot == 0 else self.char_p2
                self.client.send({"type": "char", "char": cid})
            self.client.send({"type": "ready", "value": self.ready})

    def start_game(self):
        if self.client: self.client.send({"type": "start"})
