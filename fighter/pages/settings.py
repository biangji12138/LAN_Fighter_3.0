"""Settings and moves screens plus settings mutation handlers."""
import pygame

from ..attacks import ATTACKS
from ..characters import CHARACTERS
from ..config import save_settings
from ..arena import AI_SHORT, AI_TINTS
from ..theme import (PANEL, PANEL_HI, WHITE, MUTED, CYAN, GREEN, GOLD, shade)


class SettingsPage:
    """Settings / moves pages.

    Mixin for :class:`fighter.ui.GameApp`; no ``__init__`` of its own. Expects
    the host to provide ``screen``, ``controls``, ``settings``, ``fields`` and
    the shared helpers ``header`` / ``panel`` / ``rect`` / ``text`` / ``input``
    / ``button`` / ``key_pills`` / ``set_page`` / ``set_display`` / ``back`` /
    ``notify``.
    """

    def open_settings(self):
        # 对战中从暂停菜单进来时记住来源，返回时恢复对局（仍保持暂停）。
        self.settings_return = "practice" if self.page == "practice" else ""
        self.page = "settings"
        self.focus = None

    def settings_page(self):
        self.header("设置", "更改昵称、音效、AI 难度与风格、视频模式与默认连接地址")
        self.panel(225, 150, 760, 525, PANEL, 18, (47, 66, 98), GOLD)
        # No group heading here: input() already draws a label 27px above each
        # field, so a section title in the same band collided with them.
        self.input("nickname", "默认玩家昵称", (300, 202, 360, 48), 12)
        self.input("server_ip", "默认服务器 IP", (300, 276, 360, 48), 45)
        self.input("port", "默认连接端口", (695, 276, 210, 48), 5)
        pygame.draw.line(self.screen, (46, 63, 92), (260, 350), (950, 350), 1)
        self.text("音频 · 画面 · 手柄", 300, 370, 16, MUTED)
        for idx, (key, label) in enumerate((("music", "背景音乐"),
                                            ("sfx", "游戏音效"),
                                            ("fullscreen", "全屏模式"),
                                            ("gamepad", "手柄操作"))):
            x, y = 300 + idx * 168, 396
            self.text(label, x, y, 18, MUTED)
            self.button("开启" if self.settings[key] else "关闭", (x, 420, 132, 44),
                        lambda k=key: self.toggle(k), GREEN if self.settings[key] else PANEL_HI)
        pygame.draw.line(self.screen, (46, 63, 92), (260, 490), (950, 490), 1)
        self.text("AI 难度与角色风格", 300, 508, 18, MUTED)
        # 难度是开赛参数：点芯片弹四档浮层，与主菜单的难度浮层是同一套实现。
        level = self.settings["ai_level"]
        self.ai_chip((300, 534, 220, 44), f"AI 难度：{AI_SHORT[level]}",
                     AI_TINTS[level], self.open_ai_picker, 18, ("ai-level-chip",))
        char_on = self.settings["char_ai"]
        self.button("风格:开" if char_on else "风格:关",
                    (828, 534, 122, 44),
                    lambda: self.toggle("char_ai"),
                    GREEN if char_on else PANEL_HI)
        self.button("返回", (260, 625, 155, 45), self.back, PANEL_HI)
        self.button("查看招式表", (445, 625, 190, 45), lambda: self.set_page("moves"), PANEL_HI)
        self.button("保存设置", (750, 625, 200, 45), self.save)
        if self.ai_picker_open:
            self.ai_picker()

    def moves_page(self):
        self.header("招式表", "按键与连招 · 角色专属大招 / 连招请到角色展示页查看")
        self.panel(225, 150, 760, 525, PANEL, 18, (47, 66, 98), CYAN)
        # ---------- left: key bindings ----------
        self.text("按键", 260, 174, 18, CYAN)
        pygame.draw.line(self.screen, (46, 63, 92), (260, 199), (603, 199), 1)
        binds = (
            ("左右移动", "A / D"),
            ("跳跃 / 二段跳", "W / 空格"),
            ("下蹲", "S"),
            ("站立防御", "L"),
            ("蹲防", "S + L"),
            ("轻拳", "J"),
            ("轻脚", "K"),
            ("抓取", "I"),
            ("远程攻击", "U / S + U"),
            ("蹲拳", "S + J"),
            ("下踢", "S + K"),
            ("空中拳", "空中 J"),
            ("冲刺", "双击 A / D"),
            ("暂停 / 返回", "ESC"),
        )
        for idx, (action, key) in enumerate(binds):
            y = 209 + idx * 26
            if idx % 2 == 0:
                self.rect(251, y - 7, 354, 23, (29, 42, 66), 7)
            self.text(action, 260, y - 2, 16, WHITE)
            self.text(key, 465, y - 2, 16, GOLD)
        self.text("空挥必须完整收招；命中或格挡后开取消窗口。", 260, 574, 15, GREEN)
        self.text("窗口内按下一招立即衔接，每套最多取消 3 次。", 260, 596, 15, GREEN)
        # ---------- right: combos ----------
        self.text("连招", 640, 174, 18, CYAN)
        pygame.draw.line(self.screen, (46, 63, 92), (640, 199), (963, 199), 1)
        combos = (
            ("轻拳起手", ("J", "K")),
            ("蹲拳起手", ("S+J", "K")),
            ("空中拳起手", ("空中 J", "K")),
            ("抓取追打", ("I", "J", "K")),
        )
        for idx, (label, keys) in enumerate(combos):
            y = 213 + idx * 56
            self.text(label, 640, y - 8, 16, MUTED)
            self.key_pills(keys, 640, y + 22, CYAN, 16)
        # Four short blocks instead of one dense list: the eye gets a break
        # between energy, hints, defence rules and scaling.
        for y, line, tint in ((424, "能量：近战命中 +10、远程命中 +8。", GOLD),
                              (442, "受伤方获得一半，大招命中不回能。", GOLD),
                              (468, "更多专属连招与角色大招按键，", GOLD),
                              (486, "双击角色卡进入角色展示页查看。", GOLD),
                              (512, "S + 攻击键为下蹲技：站立防御挡不住，", MUTED),
                              (530, "蹲防除抓取外全挡；下蹲可躲高位发波，", MUTED),
                              (548, "站起来则会被击中。", MUTED),
                              (576, "连段递减：85→70→55→40→30%", GREEN),
                              (594, "推离逐段拉大 · 格挡中断连段重算", GREEN)):
            self.text(line, 640, y, 15, tint)
        self.button("返回设置", (260, 625, 180, 45), lambda: self.set_page("settings"), PANEL_HI)

    def current_char_id(self):
        """本机正在使用的角色：联机按自己的槽位，单机 / 练习看 P1。"""
        slot = (self.client.slot if self.client else 0) or 0
        return self.char_p2 if slot else self.char_p1

    def open_char_moves(self):
        """暂停面板 → 当前角色招式表；返回时回到暂停中的对局。"""
        self.moves_return = self.page if self.page in ("practice", "game") else ""
        self.page = "char_moves"
        self.press_latch.clear()

    def char_moves_page(self):
        """当前角色的招式表：小技能 / 大招 / 专属连招 + 通用按键速查。"""
        cid = self.current_char_id()
        style = CHARACTERS.get(cid, CHARACTERS["red_scarf"])
        accent = style["accent"]
        attack = style.get("super") or ATTACKS["super"]
        skill = style.get("projectile") or {}
        combo = style.get("combo") or {}
        super_keys = style.get("super_keys") or (
            ("S", "S", "J+K") if style.get("super_command") else ("J+K",))
        combo_atk = combo.get("attack")
        combo_stats = (f"伤害 {combo_atk.damage} · 能耗 {int(combo_atk.energy)}"
                       if combo_atk else f"能耗 {int(combo.get('energy', 0))}")
        cards = (
            ("小技能", skill.get("name", "远程"),
             f"伤害 {skill.get('damage', 0)} · 能耗 0",
             style.get("skill_desc") or "向前发射远程弹道", ("U", "S+U")),
            ("大招", attack.name,
             f"伤害 {attack.damage} · 能耗 {int(attack.energy)}",
             style.get("super_desc") or "向前突进一击，命中击飞", super_keys),
            ("专属连招", combo.get("name", ""), combo_stats,
             style.get("combo_desc") or combo.get("note", ""),
             combo.get("steps", ("J", "K"))),
        )
        self.header("招式表", f"{style.get('name', '')} · {style.get('identity', '')} · 当前角色")
        self.panel(225, 150, 760, 525, PANEL, 18, (47, 66, 98), accent)
        for idx, (label, name, stats, effect, keys) in enumerate(cards):
            top = 176 + idx * 92
            self.rect(255, top, 700, 82, shade(PANEL_HI, .82), 12, (44, 60, 88))
            self.text(label, 271, top + 9, 16, GOLD)
            self.text(name, 348, top + 7, 20, accent, shadow=True)
            self.key_pills(keys, 505, top + 18, accent, 14,
                           "/" if label == "小技能" else "→")
            self.text("效果 " + effect, 271, top + 37, 15, MUTED)
            self.text(stats, 271, top + 59, 15, MUTED)
        pygame.draw.line(self.screen, (46, 63, 92), (260, 452), (950, 452), 1)
        self.text("通用按键", 271, 462, 15, CYAN)
        binds = (("左右移动", "A / D"), ("跳跃 / 二段跳", "W / 空格"),
                 ("下蹲", "S"), ("站立防御", "L"), ("蹲防", "S + L"),
                 ("轻拳", "J"), ("轻脚", "K"), ("抓取", "I"),
                 ("远程攻击", "U / S + U"), ("蹲拳", "S + J"),
                 ("下踢", "S + K"), ("冲刺", "双击 A / D"))
        for idx, (action, key) in enumerate(binds):
            col, row = divmod(idx, 6)
            x = 271 + col * 368
            y = 490 + row * 22
            self.text(action, x, y, 15, WHITE)
            self.text(key, x + 132, y, 15, GOLD)
        self.button("返回对战", (260, 625, 180, 45), self.back, PANEL_HI)

    def persist(self):
        """Write the current settings to disk; instant-save entry point."""
        try:
            save_settings(self.settings)
        except OSError as exc:
            self.notify("保存失败：" + str(exc)[:35])

    def toggle(self, key):
        self.settings[key] = not self.settings[key]
        # Fullscreen re-applies immediately; so does stretch while fullscreen,
        # so the picture flips between fill and aspect-fit on the spot.
        if key == "fullscreen" or (key == "stretch" and self.settings["fullscreen"]):
            try:
                self.set_display()
            except pygame.error:
                self.settings["fullscreen"] = not self.settings["fullscreen"]
                self.notify("无法切换到全屏模式")
        self.persist()

    def set_ai_level(self, level, slot=None):
        """设置难度：slot=None 为「对战 AI」的对手，0 / 1 为 AI 对打的两侧。"""
        key = "ai_level" if slot is None else f"ai_level_p{slot + 1}"
        self.settings[key] = level
        self.persist()

    def commit_fields(self):
        """Push the text fields into settings without nagging.

        Called whenever a text field loses focus, so the stored profile
        (nickname / server / port) stays current without pressing save.
        An invalid port keeps the previous value silently; the save button
        is the place that reports validation errors.
        """
        self.settings.update(nickname=self.fields["nickname"].strip()[:12] or "玩家",
                             server_ip=self.fields["server_ip"].strip() or "127.0.0.1")
        try:
            port = int(self.fields["port"])
        except ValueError:
            port = None
        if port is not None and 1024 <= port <= 65535:
            self.settings["port"] = port
            self.fields["port"] = str(port)
        self.persist()

    def save(self):
        try: port = int(self.fields["port"])
        except ValueError:
            self.notify("端口必须是数字")
            return
        if not 1024 <= port <= 65535:
            self.notify("端口范围：1024 - 65535")
            return
        self.settings.update(nickname=self.fields["nickname"].strip()[:12] or "玩家",
                             server_ip=self.fields["server_ip"].strip() or "127.0.0.1", port=port)
        self.fields["nickname"] = self.settings["nickname"]
        self.fields["server_ip"] = self.settings["server_ip"]
        self.fields["port"] = str(port)
        self.persist()
        self.notify("设置已保存")
