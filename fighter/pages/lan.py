"""LAN connection screen: host/join choice, profile fields, room entry."""
import socket

import pygame

from ..network import RoomClient, RoomServer
from ..theme import PANEL, PANEL_HI, BLUE, CYAN, GREEN, MUTED


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class LanPage:
    """LAN connect page.

    Mixin for :class:`fighter.ui.GameApp`; no ``__init__`` of its own. Expects
    the host to provide ``screen``, ``controls``, ``focus``, ``mode``,
    ``fields``, ``client`` / ``server``, ``players``, ``ready`` and the shared
    helpers ``header`` / ``panel`` / ``rect`` / ``text`` / ``input`` /
    ``button`` / ``notify`` / ``leave_room``.
    """

    def open_lan(self):
        self.page = "lan"
        self.focus = None
        self.mode = "join"

    def lan(self):
        self.header("双人对抗", "同一 Wi-Fi 或交换机局域网 · 房主创建房间，另一名玩家加入")
        self.panel(225, 157, 760, 445, PANEL, 18, (47, 66, 98), CYAN)
        self.text("连接方式", 330, 170, 16, MUTED)
        self.button("创建房间", (330, 193, 260, 54), lambda: self.change_mode("host"),
                    BLUE if self.mode == "host" else PANEL_HI)
        self.button("加入房间", (620, 193, 260, 54), lambda: self.change_mode("join"),
                    BLUE if self.mode == "join" else PANEL_HI)
        pygame.draw.line(self.screen, (46, 63, 92), (260, 272), (950, 272), 1)
        self.text("玩家资料", 330, 280, 16, MUTED)
        self.input("nickname", "玩家昵称", (345, 332, 520, 49), 12)
        if self.mode == "join":
            self.input("server_ip", "房主的局域网 IP 地址", (345, 432, 520, 49), 45)
        else:
            self.rect(345, 418, 520, 49, (18, 29, 48), 12, (52, 84, 128))
            pygame.draw.circle(self.screen, GREEN, (367, 442), 5)
            self.text("本机 IP：" + local_ip(), 385, 431, 20, CYAN)
        self.input("port", "端口（1024 - 65535）", (345, 528, 230, 47), 5)
        self.button("创建并进入房间" if self.mode == "host" else "连接房间",
                    (615, 524, 250, 55), self.enter_room)
        self.button("返回主菜单", (115, 608, 190, 49), self.back, PANEL_HI)

    def change_mode(self, mode):
        self.mode = mode
        self.focus = None

    def enter_room(self):
        try: port = int(self.fields["port"])
        except ValueError:
            self.notify("请填写有效端口"); return
        if not 1024 <= port <= 65535:
            self.notify("端口范围：1024 - 65535"); return
        nick = self.fields["nickname"].strip()[:12] or "玩家"
        self.leave_room()
        try:
            if self.mode == "host":
                self.server = RoomServer(port, self.settings["map"])
                self.server.start()
                ip = "127.0.0.1"
            else:
                ip = self.fields["server_ip"].strip()
                if not ip: raise ValueError("请填写房主 IP")
            self.client = RoomClient()
            self.client.connect(ip, port, nick)
            self.players = []
            self.ready = False
            self.page = "room"
        except (OSError, ValueError) as exc:
            self.leave_room()
            self.notify("无法连接：" + str(exc)[:65])
