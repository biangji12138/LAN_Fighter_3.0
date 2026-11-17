"""Settings page: instant persistence, blur commit, fullscreen switching."""
import json
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fighter import config
from fighter.theme import W, H
from fighter.ui import GameApp


class SettingsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "settings.json"
        # Redirect the profile store before the app loads its settings.
        cls.patcher = patch.object(config, "config_path", return_value=cls.path)
        cls.patcher.start()
        cls.app = GameApp()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.app.settings.update(dict(config.DEFAULTS))
        self.app.fields = {"nickname": self.app.settings["nickname"],
                           "server_ip": self.app.settings["server_ip"],
                           "port": str(self.app.settings["port"])}
        self.app.focus = None
        self.app.page = "settings"
        # Rebuild the display in windowed mode: the dummy SDL driver does not
        # always honour set_mode sizes right after a FULLSCREEN switch.
        self.app.set_display()

    def stored(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_toggle_persists_instantly(self):
        self.app.settings["sfx"] = True
        self.app.toggle("sfx")
        self.assertFalse(self.app.settings["sfx"])
        self.assertFalse(self.stored()["sfx"])

    def test_ai_level_persists_instantly(self):
        self.app.set_ai_level("hard")
        self.assertEqual(self.stored()["ai_level"], "hard")

    def test_ai_level_per_slot_persists(self):
        # AI 对打的两侧难度分开存：芯片可以一边困难一边普通。
        self.app.set_ai_level("hell", slot=0)
        self.app.set_ai_level("normal", slot=1)
        self.assertEqual(self.stored()["ai_level_p1"], "hell")
        self.assertEqual(self.stored()["ai_level_p2"], "normal")

    def test_old_save_inherits_the_slot_difficulty(self):
        # 旧存档只有全局 ai_level：两侧沿用该档，不要突然掉回普通。
        self.path.write_text(json.dumps({"ai_level": "hell"}), encoding="utf-8")
        loaded = config.load_settings()
        self.assertEqual(loaded["ai_level"], "hell")
        self.assertEqual(loaded["ai_level_p1"], "hell")
        self.assertEqual(loaded["ai_level_p2"], "hell")

    def test_blur_commits_text_fields(self):
        self.app.fields["nickname"] = " 夜行者 "
        self.app.fields["port"] = "51234"
        self.app.focus = "nickname"
        self.app.set_focus(None)
        self.assertEqual(self.app.settings["nickname"], "夜行者")
        self.assertEqual(self.app.settings["port"], 51234)
        self.assertEqual(self.stored()["port"], 51234)

    def test_blur_keeps_previous_port_on_garbage(self):
        self.app.fields["port"] = "abc"
        self.app.focus = "port"
        self.app.set_focus(None)
        self.assertEqual(self.app.settings["port"], config.DEFAULTS["port"])

    def test_pause_settings_returns_to_the_paused_battle(self):
        """暂停菜单的“设置”返回后必须回到对局并保持暂停。"""
        self.app.page = "practice"
        self.app.paused = True
        self.app.open_settings()
        self.assertEqual(self.app.page, "settings")
        self.app.back()
        self.assertEqual(self.app.page, "practice")
        self.assertTrue(self.app.paused)
        self.assertEqual(self.app.settings_return, "")

    def test_settings_from_menu_backs_to_menu(self):
        self.app.page = "settings"
        self.app.paused = False
        self.app.back()
        self.assertEqual(self.app.page, "menu")
        self.assertFalse(self.app.paused)

    def test_fullscreen_toggle_switches_and_reverts(self):
        was = self.app.settings["fullscreen"]
        self.app.toggle("fullscreen")
        try:
            self.assertEqual(self.app.settings["fullscreen"], not was)
            dw, dh = self.app.display_surface.get_size()
            # scaled buffer exists iff the physical size differs from the canvas
            self.assertEqual((dw, dh) != (W, H), self.app.scaled is not None)
            self.assertEqual(self.stored()["fullscreen"], self.app.settings["fullscreen"])
        finally:
            self.app.toggle("fullscreen")
        self.assertFalse(self.app.settings["fullscreen"])
        # Only assert the buffer cleanup when the driver honoured the size.
        if self.app.display_surface.get_size() == (W, H):
            self.assertIsNone(self.app.scaled)

    def test_music_toggle_persists_instantly(self):
        self.app.toggle("music")
        self.assertFalse(self.app.settings["music"])
        self.assertFalse(self.stored()["music"])
        # The per-frame BGM dispatcher must tolerate a missing/absent mixer.
        self.app.update_music()
        self.app.toggle("music")
        self.app.update_music()

    def test_fullscreen_aspect_fit_letterbox(self):
        self.app.settings["fullscreen"] = True
        self.app.set_display()
        try:
            dw, dh = self.app.display_surface.get_size()
            if (dw, dh) == (W, H):
                self.assertIsNone(self.app.letterbox)  # ratios already match
            else:
                self.assertIsNotNone(self.app.letterbox)
                self.assertEqual(self.app.scale[0], self.app.scale[1])
                bx, by = self.app.letterbox_pos
                self.assertGreaterEqual(bx, 0)
                self.assertGreaterEqual(by, 0)
                self.assertLessEqual(bx * 2 + self.app.letterbox.get_width(), dw + 1)
        finally:
            self.app.settings["fullscreen"] = False
            self.app.set_display()


if __name__ == "__main__":
    unittest.main()
