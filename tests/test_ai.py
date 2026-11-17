"""Practice-mode AI behaviour, exercised through AIController instances."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fighter.ui import GameApp
from fighter.combat import Combat


@contextmanager
def ai_random(value):
    """钉死 AI 的全部随机源。

    只 patch random.random 时，random.uniform（反应延迟）与 random.choices
    （选招）仍走真实熵，用例会随进程抖动；这里一并固定为区间的中点与
    候选列表的第一项。
    """
    with patch("fighter.ai.random.random", return_value=value), \
            patch("fighter.ai.random.uniform",
                  side_effect=lambda a, b: (a + b) / 2.), \
            patch("fighter.ai.random.choices",
                  side_effect=lambda seq, **kw: [seq[0]]):
        yield


class AITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = GameApp()
        cls.app.screen = cls.app.canvas

    def setUp(self):
        app = self.app
        app.char_p1 = "red_scarf"
        app.char_p2 = "blue_headband"
        app.settings["ai_level"] = "normal"
        app.settings["char_ai"] = False   # 只测"难度"轴的用例关闭角色风格层

    def _fresh_duel(self, distance, energy=0, foe_hp=None):
        self.app.combat = Combat()
        self.app._setup_combat()
        self.app.combat.countdown = 0.
        self.app.combat.fighters[0]["x"] = 400.
        self.app.combat.fighters[1]["x"] = 400. + distance
        self.app.combat.fighters[0]["energy"] = energy
        if foe_hp is not None:
            self.app.combat.fighters[1]["hp"] = foe_hp
        # clock past the decision cooldown so the AI commits on the first frame.
        # 这两局没有走 practice()，清掉上一条用例留下的开场锁定参数，
        # 让难度与风格继续跟随 settings（下面几条用例要在 _fresh_duel 之后改设置）。
        for ai in self.app.ai:
            ai.set_level(None)
            ai.set_style(None)
        self.app.ai[0].reset(clock=9.)
        self.app.ai[1].reset(clock=9.)

    def test_char_style_locks_when_the_match_starts(self):
        # 风格开关同样只在下局生效：局内关闭不会立刻切回通用 AI。
        self.app.settings["char_ai"] = True
        self.app.practice()
        self.app.settings["char_ai"] = False
        self.assertTrue(self.app.ai[1].style_on)
        self.assertIsNotNone(self.app.ai[1]._style(self.app.combat.fighters[1]))

    def test_ai_chains_a_signature_combo(self):
        self._fresh_duel(90)
        seen = set()
        with ai_random(.9):
            for _ in range(160):
                cmd = self.app.ai[0].command(1 / 60)
                events = self.app.combat.step(1 / 60, [cmd, {"left": False, "right": False}])
                seen.update(e["event"] for e in events
                            if e.get("player") == 0 and e["event"] in ("punch", "kick", "grab"))
        self.assertIn("punch", seen)
        self.assertIn("kick", seen)
        self.assertLess(self.app.combat.fighters[1]["hp"],
                        self.app.combat.fighters[1]["hp_max"])

    def test_ai_arms_and_uses_its_super_with_full_energy(self):
        self._fresh_duel(80, energy=100)
        seen_super = False
        with ai_random(.05):
            for _ in range(90):
                cmd = self.app.ai[0].command(1 / 60)
                events = self.app.combat.step(1 / 60, [cmd, {"left": False, "right": False}])
                if any(e["event"] == "super" and e.get("player") == 0 for e in events):
                    seen_super = True
                    break
        self.assertTrue(seen_super)
        self.assertEqual(self.app.combat.fighters[0]["energy"], 0)

    def test_ai_holds_button_presses_across_high_refresh_frames(self):
        self._fresh_duel(90)
        first = self.app.ai[0].command(1 / 144)
        second = self.app.ai[0].command(1 / 144)
        self.assertTrue(first.get("punch") or second.get("punch"))
        self.assertGreater(self.app.ai[0].pulse, 0.)
        # The same press must still be held on the next frame so a 60 Hz
        # physics tick can sample it even on a 144 Hz display.
        third = self.app.ai[0].command(1 / 144)
        self.assertTrue(third.get("punch") or third.get("kick"))

    def test_ai_backs_off_from_a_knocked_down_opponent(self):
        self._fresh_duel(60)
        foe = self.app.combat.fighters[1]
        foe["knocked"] = True
        foe["stun"] = 2.0
        cmd = self.app.ai[0].command(1 / 60)
        self.assertTrue(cmd["left"])
        self.assertFalse(cmd["punch"] or cmd["kick"] or cmd["projectile"])
        start = self.app.combat.fighters[0]["x"]
        for _ in range(60):
            cmd = self.app.ai[0].command(1 / 60)
            self.app.combat.step(1 / 60, [cmd, {"left": False, "right": False}])
        self.assertLess(self.app.combat.fighters[0]["x"], start)
        self.assertGreater(abs(self.app.combat.fighters[0]["x"] - foe["x"]), 150)

    def test_ai_retreats_after_a_combo_then_approaches_again(self):
        self._fresh_duel(60)
        self.app.ai[0].retreat = .5
        cmd = self.app.ai[0].command(1 / 60)
        self.assertTrue(cmd["left"])
        self.assertFalse(cmd["punch"] or cmd["kick"])
        # A wounded opponent is rushed down instead of zoned out.
        self.app.ai[0].retreat = 0.
        self.app.combat.fighters[1]["hp"] = 200
        self.app.combat.fighters[1]["x"] = 560.
        cmd = self.app.ai[0].command(1 / 60)
        self.assertTrue(cmd["right"])

    def test_ai_pre_guards_a_mash_rhythm(self):
        # Regression: jab spam cycles faster than any reaction delay, so the
        # AI must read the rhythm and pre-emptively raise guard instead of
        # waiting for the react timer that can never win that race.
        self._fresh_duel(90)
        self.app.settings["ai_level"] = "medium"
        guarded = 0
        with ai_random(0.0):
            for i in range(240):
                foe_keys = {"punch": True} if i % 2 == 0 else {}
                cmd = self.app.ai[0].command(1 / 60)
                self.app.combat.step(1 / 60, [cmd, foe_keys])
                guarded += 1 if cmd.get("guard") else 0
        self.assertGreater(guarded, 10)

    def test_ai_counters_recovery_frames(self):
        # Regression: when the victim's stun decays mid-spam, the AI used to
        # re-path instead of punishing the spammer's own recovery window.
        self._fresh_duel(90)
        self.app.settings["ai_level"] = "medium"
        foe = self.app.combat.fighters[1]
        foe["attack_kind"] = "punch"
        # punch: startup 4 + active 7 -> frame 12 is squarely in recovery.
        foe["action_frame"] = 12
        seen = False
        with ai_random(0.0):
            for _ in range(30):
                cmd = self.app.ai[0].command(1 / 60)
                events = self.app.combat.step(1 / 60, [cmd, {}])
                if any(e["event"] == "punch" and e.get("player") == 0
                       for e in events):
                    seen = True
                    break
        self.assertTrue(seen)

    def test_ai_crouch_guards_an_incoming_shot(self):
        self._fresh_duel(200)
        self.app.combat.projectiles = [{
            "x": 600, "y": 112, "vx": -420, "damage": 14, "lifetime": .5,
            "owner": 1, "attack": "projectile", "color": (255, 130, 60),
            "size": 8, "hit": False}]
        with ai_random(0.):
            cmd = self.app.ai[0].command(1 / 60)
        self.assertTrue(cmd["guard"])
        self.assertTrue(cmd["down"])

    def test_ai_grabs_a_crouching_guard(self):
        self._fresh_duel(70)
        self.app.combat.fighters[1]["action"] = "crouch_guard"
        self.app.ai[0].command(1 / 60)      # queues the plan
        cmd = self.app.ai[0].command(1 / 60)
        self.assertTrue(cmd["grab"])

    def test_ai_grab_connects_with_a_crouching_guard(self):
        # The AI used to queue grabs at reach + 6 while combat only connects at
        # reach, so every throw whiffed against a crouching guard.
        self._fresh_duel(70)
        foe = self.app.combat.fighters[1]
        foe["action"] = "crouch_guard"
        hit = False
        for _ in range(90):
            cmd = self.app.ai[0].command(1 / 60)
            events = self.app.combat.step(
                1 / 60, [cmd, {"down": True, "guard": True}])
            if any(e["event"] == "hit" and e.get("player") == 0
                   and e.get("attack") == "grab" and not e.get("blocked")
                   for e in events):
                hit = True
                break
        self.assertTrue(hit)
        self.assertLess(foe["hp"], foe["hp_max"])

    def test_hard_ai_pressures_instead_of_zoning(self):
        self._fresh_duel(190)
        with ai_random(1.):
            normal = self.app.ai[0].command(1 / 60)
        # Normal zones a healthy opponent: back off when they are too close.
        self.assertTrue(normal["left"])
        self._fresh_duel(190)
        self.app.settings["ai_level"] = "hard"
        with ai_random(1.):
            hard = self.app.ai[0].command(1 / 60)
        # Hard judges the situation itself and walks into pressure range.
        self.assertTrue(hard["right"])

    def test_ai_forces_an_approach_through_projectile_spam(self):
        self._fresh_duel(300)
        start = self.app.combat.fighters[0]["x"]
        forced = False
        with ai_random(0.):
            for _ in range(360):
                self.app.combat.projectiles = [{
                    "x": 620, "y": 112, "vx": -420, "damage": 14, "lifetime": .5,
                    "owner": 1, "attack": "projectile", "color": (255, 130, 60),
                    "size": 8, "hit": False}]
                cmd = self.app.ai[0].command(1 / 60)
                self.app.combat.step(1 / 60, [cmd, {"left": False, "right": False}])
                forced = forced or self.app.ai[0].force > 0
        self.assertTrue(forced)
        self.assertGreater(self.app.combat.fighters[0]["x"], start + 40)

    def test_ai_level_locks_when_the_match_starts(self):
        # 设置页改档不应当在局内生效：开局锁定，名字与实际行为保持一致。
        self.app.settings["ai_level"] = "normal"
        self.app.practice()
        self.app.settings["ai_level"] = "hell"
        self.assertEqual(self.app.ai[1].level, "normal")
        self.assertEqual(self.app.ai[1]._tier(), 0)
        self.assertEqual(self.app._fighter_label(1)[0], "普通AI")

    def test_cpu_vs_cpu_uses_a_separate_level_per_side(self):
        self.app.settings["ai_level_p1"] = "hard"
        self.app.settings["ai_level_p2"] = "normal"
        self.app.cpu_vs_cpu()
        self.assertEqual(self.app.ai[0]._tier(), 2)
        self.assertEqual(self.app.ai[1]._tier(), 0)
        self.assertEqual(self.app._fighter_label(0)[0], "困难AI 1")
        self.assertEqual(self.app._fighter_label(1)[0], "普通AI 2")

    def test_ai_goes_low_against_a_standing_guard(self):
        self._fresh_duel(100)
        self.app.combat.fighters[1]["action"] = "guard"
        self.app.ai[0].command(1 / 60)      # queues the plan
        cmd = self.app.ai[0].command(1 / 60)
        self.assertTrue(cmd["down"])
        self.assertTrue(cmd["kick"])

    def test_ai_aborts_a_plan_it_can_no_longer_reach(self):
        self._fresh_duel(300)
        self.app.ai[0]._queue_plan(["punch"])
        for _ in range(40):
            self.app.ai[0].command(1 / 60)
        self.assertIsNone(self.app.ai[0].plan)

    def test_ai_backdashes_after_a_knockdown_then_harasses(self):
        self._fresh_duel(60)
        foe = self.app.combat.fighters[1]
        foe["knocked"] = True
        foe["stun"] = 2.0
        start = self.app.combat.fighters[0]["x"]
        fired = False
        for _ in range(200):
            cmd = self.app.ai[0].command(1 / 60)
            events = self.app.combat.step(1 / 60, [cmd, {"right": True}])
            if any(e["event"] == "projectile" and e.get("player") == 0
                   for e in events):
                fired = True
                break
        self.assertLess(self.app.combat.fighters[0]["x"], start - 60)
        self.assertTrue(fired)


if __name__ == "__main__":
    unittest.main()
