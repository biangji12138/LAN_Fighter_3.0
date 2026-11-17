"""Menu character cards, direct practice start and LAN-only self selection."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import queue
import unittest
from unittest.mock import patch

from fighter.ui import GameApp
from fighter.characters import CHARACTERS
from fighter.combat import ROUND_COUNTDOWN
from fighter.theme import W


class StubClient:
    """Minimal RoomClient stand-in for UI flow tests."""

    def __init__(self, slot):
        self.slot = slot
        self.sent = []
        self.events = queue.Queue()

    def send(self, message):
        self.sent.append(message)


class SelectionMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = GameApp()
        cls.app.screen = cls.app.canvas

    def setUp(self):
        app = self.app
        app.page = "menu"
        app.char_p1 = "red_scarf"
        app.char_p2 = "blue_headband"
        app.select_mode = "menu"
        app.select_slot = 0
        app.client = None
        app.controls = []
        app.ai_picker_open = False
        app.settings["ai_level"] = "normal"
        app.settings["ai_level_p1"] = "normal"
        app.settings["ai_level_p2"] = "normal"
        app.settings["char_ai"] = False   # 只测“难度”轴的用例关闭角色风格层

    def test_menu_cards_open_their_own_slot(self):
        self.app.menu()
        cards = [action for rect, action in self.app.controls
                 if callable(action)
                 and rect.x in (W // 2 - 338 - 106, W // 2 + 338 - 106)]
        self.assertEqual(len(cards), 2)
        cards[0]()
        self.assertEqual((self.app.page, self.app.select_slot, self.app.select_mode),
                         ("select", 0, "menu"))
        cards[1]()
        self.assertEqual((self.app.page, self.app.select_slot), ("select", 1))

    def test_menu_puts_dual_level_chips_above_the_ai_card(self):
        # 「AI 对打」两侧档位挂在 P2 角色卡正上方：两枚直选芯片，点一下切一档。
        app = self.app
        app.page = "menu"
        app.controls = []
        app.menu()
        chips = sorted((r for r, action in app.controls
                        if callable(action) and (r.width, r.height) == (100, 30)),
                       key=lambda r: r.x)
        self.assertEqual(len(chips), 2)
        card_top = 274
        for chip in chips:
            self.assertLess(chip.bottom, card_top)              # 不压住角色卡
            self.assertGreater(chip.centerx, W // 2)            # 在 P2 卡一侧
        with patch("fighter.pages.settings.save_settings"):
            self.assertEqual(app.settings["ai_level_p1"], "normal")
            app.cycle_ai_level(0)
            app.cycle_ai_level(0)
            app.cycle_ai_level(1)
        self.assertEqual(app.settings["ai_level_p1"], "hard")
        self.assertEqual(app.settings["ai_level_p2"], "medium")

    def test_settings_page_owns_the_single_ai_level_chip(self):
        # 对战 AI 的难度入口搬到设置页：点芯片弹四档浮层，选完立即落盘。
        app = self.app
        app.page = "settings"
        app.ai_picker_open = False
        app.controls = []
        with patch("fighter.pages.settings.save_settings"):
            app.settings_page()
            chip = next(r for r, action in app.controls
                        if callable(action) and (r.width, r.height) == (220, 44))
            self.assertEqual(chip.topleft, (300, 534))
            app.open_ai_picker()
            app.controls = []
            app.settings_page()
            self.assertTrue(app.ai_picker_open)
            app.choose_ai_level("hard")
        self.assertFalse(app.ai_picker_open)
        self.assertEqual(app.settings["ai_level"], "hard")

    def test_confirming_menu_selection_returns_to_menu(self):
        self.app.open_select(0)
        self.app.pick_char(0, "blue_headband")
        self.app.confirm_select()
        self.assertEqual(self.app.page, "menu")
        self.assertEqual(self.app.char_p1, "blue_headband")

    def test_practice_starts_directly_with_both_characters(self):
        self.app.pick_char(0, "blue_headband")
        self.app.pick_char(1, "red_scarf")
        self.app.practice()
        self.assertEqual(self.app.page, "practice")
        self.assertEqual(self.app.practice_mode, "normal")
        self.assertEqual(self.app.combat.fighters[0]["char_id"], "blue_headband")
        self.assertEqual(self.app.combat.fighters[1]["char_id"], "red_scarf")
        self.assertEqual(self.app.combat.fighters[0]["projectile_config"]["damage"], 11)
        self.assertEqual(self.app.combat.fighters[1]["projectile_config"]["damage"], 14)
        self.assertEqual(self.app.combat.fighters[0]["hp"], CHARACTERS["blue_headband"]["health"])
        self.assertEqual(self.app.combat.fighters[1]["hp"], CHARACTERS["red_scarf"]["health"])

    def test_training_starts_directly_without_select_page(self):
        self.app.pick_char(1, "blue_headband")
        self.app.training()
        self.assertEqual(self.app.page, "practice")
        self.assertEqual(self.app.practice_mode, "training")
        self.assertEqual(self.app.combat.fighters[1]["char_id"], "blue_headband")
        self.assertEqual(self.app.combat.countdown, 0.)

    def test_regular_practice_keeps_the_countdown(self):
        self.app.practice()
        self.assertEqual(self.app.combat.countdown, ROUND_COUNTDOWN)

    def test_cpu_vs_cpu_drives_both_sides(self):
        self.app.pick_char(0, "red_scarf")
        self.app.pick_char(1, "blue_headband")
        self.app.cpu_vs_cpu()
        self.assertEqual(self.app.page, "practice")
        self.assertEqual(self.app.practice_mode, "cpu_vs_cpu")
        self.assertEqual(self.app.combat.countdown, ROUND_COUNTDOWN)
        self.assertEqual(self.app.combat.fighters[1]["char_id"], "blue_headband")
        # Skip the countdown: both AI fighters must close in with no keyboard input.
        self.app.combat.countdown = 0.
        start = [f["x"] for f in self.app.combat.fighters]
        for _ in range(24):
            self.app.update_practice(1 / 60)
        fighters = self.app.combat.fighters
        self.assertGreater(fighters[0]["x"], start[0])
        self.assertLess(fighters[1]["x"], start[1])

    def test_cpu_vs_cpu_fighters_exchange_damage(self):
        self.app.cpu_vs_cpu()
        self.app.combat.countdown = 0.
        for _ in range(600):
            self.app.update_practice(1 / 60)
        total_hp = sum(f["hp"] for f in self.app.combat.fighters)
        total_max = sum(f["hp_max"] for f in self.app.combat.fighters)
        self.assertLess(total_hp, total_max)

    def test_select_page_only_edits_the_focused_slot(self):
        self.app.pick_char(0, "blue_headband")
        self.app.pick_char(1, "blue_headband")
        self.app.select_slot = 1
        self.app.controls = []
        self.app.select_page()
        cards = [action for _, action in self.app.controls
                 if isinstance(action, tuple) and action[0] == "card"]
        self.assertEqual(len(cards), len(CHARACTERS))
        self.assertTrue(all(card[1] == 1 for card in cards))
        self.app.pick_char(cards[0][1], cards[0][2])   # first card = red_scarf, offered for slot 1 only
        self.assertEqual(self.app.char_p2, "red_scarf")
        self.assertEqual(self.app.char_p1, "blue_headband")

    def test_select_page_has_no_selection_buttons(self):
        self.app.select_slot = 0
        self.app.controls = []
        self.app.select_page()
        # Only the confirm / back buttons remain; the cards themselves drive the pick.
        buttons = [action for _, action in self.app.controls if callable(action)]
        self.assertEqual(len(buttons), 2)

    def test_showcase_page_opens_and_returns_to_select(self):
        self.app.open_select(0)
        self.app.open_showcase("blue_headband")
        self.assertEqual((self.app.page, self.app.showcase_cid), ("showcase", "blue_headband"))
        self.app.screen = self.app.canvas
        self.app.showcase_page()   # must render without raising
        self.app.back()
        self.assertEqual((self.app.page, self.app.select_mode), ("select", "menu"))

    def test_showcase_shows_move_speed_label(self):
        app = self.app
        for cid, speed in (("red_scarf", CHARACTERS["red_scarf"]["move_speed"]),
                           ("blue_headband", CHARACTERS["blue_headband"]["move_speed"])):
            app.open_showcase(cid)
            calls = []
            original = app.text
            app.text = lambda value, *a, **k: calls.append(str(value)) or original(value, *a, **k)
            try:
                app.showcase_page()
            finally:
                app.text = original
            self.assertTrue(any("移动速度" in line and str(speed) in line for line in calls))

    def test_characters_expose_showcase_profile(self):
        for char in CHARACTERS.values():
            self.assertTrue(char["gender"])
            self.assertTrue(char["identity"])
            self.assertTrue(char["bio"])
            self.assertGreater(char["health"], 0)
            self.assertGreater(char["move_speed"], 0)
            self.assertTrue(char["super"].name)
            self.assertTrue(char["combo"]["steps"])


class LanSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = GameApp()
        cls.app.screen = cls.app.canvas

    def setUp(self):
        app = self.app
        app.page = "menu"
        app.char_p1 = "red_scarf"
        app.char_p2 = "blue_headband"
        app.select_mode = "menu"
        app.select_slot = 0
        app.client = None
        app.controls = []
        app.settings["ai_level"] = "normal"
        app.settings["char_ai"] = False   # 只测“难度”轴的用例关闭角色风格层

    def test_room_select_forces_own_slot(self):
        self.app.client = StubClient(1)
        self.app.select_slot = 0
        self.app.open_lan_select()
        self.assertEqual((self.app.page, self.app.select_slot, self.app.select_mode),
                         ("select", 1, "lan_pick"))

    def test_lan_confirm_sends_only_my_character(self):
        self.app.client = StubClient(1)
        self.app.open_lan_select()
        self.app.pick_char(1, "red_scarf")
        self.app.select_page()
        self.app.confirm_select()
        self.assertEqual(self.app.page, "room")
        self.assertEqual(self.app.client.sent[-1], {"type": "char", "char": "red_scarf"})

    def test_host_lan_confirm_sends_p1_character(self):
        self.app.client = StubClient(0)
        self.app.open_lan_select()
        self.app.pick_char(0, "blue_headband")
        self.app.confirm_select()
        self.assertEqual(self.app.client.sent[-1], {"type": "char", "char": "blue_headband"})

    def test_welcome_pushes_local_character_to_server(self):
        self.app.client = StubClient(0)
        self.app.client.events.put({"type": "welcome", "slot": 0})
        self.app.char_p1 = "blue_headband"
        self.app.poll_network()
        self.assertEqual(self.app.client.sent, [{"type": "char", "char": "blue_headband"}])

    def test_back_from_lan_select_returns_to_room(self):
        self.app.client = StubClient(0)
        self.app.select_mode = "lan_pick"
        self.app.page = "select"
        self.app.back_from_select()
        self.assertEqual(self.app.page, "room")
        self.app.client = None
        self.app.back_from_select()
        self.assertEqual(self.app.page, "menu")


if __name__ == "__main__":
    unittest.main()
