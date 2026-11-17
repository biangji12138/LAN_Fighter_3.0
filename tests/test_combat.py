"""Gameplay and result tests, independent of pygame."""
import unittest
from fighter.combat import (Combat, ROUND_COUNTDOWN, BODY_TOP, BODY_BOTTOM,
                            CROUCH_TOP, NECK_HEIGHT, CROUCH_PROJ_HEIGHT, MAX_ENERGY,
                            MAX_CANCEL_CHAIN, COMBO_SCALING, COMBO_WINDOW, PUSH_GROWTH,
                            GUARD_PUSHBACK, GETUP_INVULN_FRAMES, FATIGUE_RECOVERY,
                            HIT_ENERGY_GAIN, ARENA_LEFT, ARENA_RIGHT, GRAB_PULL_FRAMES,
                            shadow_phase, SHADOW_BURROW, SHADOW_HIDE, body_span,
                            AIR_WHIFF_CANCEL_FRAMES, KNIFE_MAX, KNIFE_DAMAGE,
                            ROLLER_DAMAGE, ROLLER_REQUIRED_HITS)
from fighter.attacks import ATTACKS
from fighter.characters import CHARACTERS


class CombatTests(unittest.TestCase):
    def test_jump_and_land(self):
        game = Combat()
        game.step(.02, [{"jump": True}, {}])
        self.assertGreater(game.fighters[0]["y"], 0)
        highest = game.fighters[0]["y"]
        for _ in range(60):
            game.step(.02, [{"jump": False}, {}])
            highest = max(highest, game.fighters[0]["y"])
        self.assertGreater(highest, 60)
        self.assertEqual(game.fighters[0]["y"], 0)

    def test_punch_kick_hit_and_cooldown(self):
        game = Combat()
        game.fighters[0]["x"] = 400
        game.fighters[1]["x"] = 485
        events = []
        for _ in range(8):
            events += game.step(.02, [{"punch": True}, {}])
        self.assertEqual(game.fighters[1]["hp"], 1000 - 9)
        self.assertEqual(len([e for e in events if e["event"] == "hit"]), 1)
        # Holding the button should NOT trigger repeated attacks.
        for _ in range(40):
            game.step(.02, [{"punch": True}, {}])
        self.assertEqual(game.fighters[1]["hp"], 1000 - 9)
        game.step(.02, [{"punch": False}, {}])
        for _ in range(10):
            game.step(.02, [{"kick": True}, {}])
        # The kick lands inside the same combo, so it is scaled down.
        kick = max(1, int(ATTACKS["kick"].damage * COMBO_SCALING[1]))
        self.assertEqual(game.fighters[1]["hp"], 1000 - 9 - kick)

    def test_out_of_reach_and_airborne_miss(self):
        game = Combat()
        game.fighters[0]["x"] = 200
        game.fighters[1]["x"] = 600
        for _ in range(15):
            game.step(.02, [{"kick": True}, {}])
        self.assertEqual(game.fighters[1]["hp"], 1000)
        game = Combat()
        game.fighters[0]["x"] = 400
        game.fighters[1]["x"] = 480
        game.fighters[1]["y"] = 210
        for _ in range(15):
            game.step(.02, [{"punch": True}, {}])
        self.assertEqual(game.fighters[1]["hp"], 1000)

    def test_two_wins_match_then_round_reset(self):
        game = Combat()
        game.finish_round(0)
        self.assertEqual(game.phase, "round_end")
        self.assertEqual(game.scores, [1, 0])
        for _ in range(60):
            game.step(.05)
        self.assertEqual(game.phase, "game")
        self.assertEqual(game.round, 2)
        self.assertEqual(game.fighters[1]["hp"], 1000)
        game.finish_round(0)
        self.assertEqual(game.phase, "match_end")
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.scores, [2, 0])

    def test_time_out_win_or_draw(self):
        game = Combat()
        game.time_left = .01
        game.fighters[0]["hp"] = 55
        game.fighters[1]["hp"] = 40
        game.step(.02)
        self.assertEqual(game.round_winner, 0)
        draw = Combat()
        draw.time_left = .01
        draw.step(.02)
        self.assertIsNone(draw.round_winner)
        self.assertEqual(draw.scores, [0, 0])


class SuperArtTests(unittest.TestCase):
    """J + K super: same frame or a short 6-frame input window."""

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["energy"] = 100

    def press(self, keys):
        events = self.game.step(1 / 60, [keys, {}])
        return events

    def test_same_frame_punch_and_kick_starts_super(self):
        self.press({"punch": True, "kick": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 0)

    def test_short_input_gap_still_starts_super(self):
        # Humans rarely hit J and K on the exact same frame; 1-4 frame gaps
        # must still be read as a super command. The punch must play out in
        # full first, then the buffered super takes over.
        for gap in (1, 2, 4, 6):
            game = Combat()
            game.fighters[0]["energy"] = 100
            game.step(1 / 60, [{"punch": True}, {}])
            for _ in range(gap - 1):
                game.step(1 / 60, [{"punch": True}, {}])
            game.step(1 / 60, [{"punch": True, "kick": True}, {}])
            for _ in range(ATTACKS["punch"].total + 6):
                game.step(1 / 60, [{}, {}])
            self.assertEqual(game.fighters[0]["attack_kind"], "super", f"gap={gap}")
            self.assertEqual(game.fighters[0]["energy"], 0, f"gap={gap}")

    def test_gap_outside_window_does_not_start_super(self):
        self.press({"punch": True})
        for _ in range(6):
            self.press({"punch": True})
        # Kick arrives past the 6-frame window: normal punch keeps playing.
        self.press({"punch": True, "kick": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "punch")
        self.assertEqual(self.game.fighters[0]["energy"], 100)

    def test_super_needs_full_energy(self):
        self.game.fighters[0]["energy"] = 99
        self.press({"punch": True, "kick": True})
        self.assertNotEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 99)

    def test_super_not_allowed_airborne(self):
        self.game.fighters[0]["y"] = 120.
        self.game.fighters[0]["vy"] = 0.
        self.press({"punch": True, "kick": True})
        self.assertNotEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 100)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "jump_punch")

    def test_super_hits_for_super_damage(self):
        self.game.fighters[0]["x"] = 400
        self.game.fighters[1]["x"] = 490
        self.press({"punch": True, "kick": True})
        self.assertEqual(self.game.fighters[0]["energy"], 0)
        for _ in range(40):
            self.press({"punch": True, "kick": True})
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 340)


class CommandSuperTests(unittest.TestCase):
    """Red scarf super: tap S twice then J+K. Pulls the foe in, pummels, throws."""

    def setUp(self):
        self.game = Combat()
        self.game.set_loadout(0, CHARACTERS["red_scarf"])
        self.game.set_loadout(1, CHARACTERS["blue_headband"])
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 490.

    def run_frames(self, keys, frames=1):
        for _ in range(frames):
            self.game.step(1 / 60, [keys, {}])

    def command(self):
        # S, release, S, release, then J + K.
        self.run_frames({"down": True})
        self.run_frames({})
        self.run_frames({"down": True})
        self.run_frames({})
        self.run_frames({"punch": True, "kick": True})

    def run_super(self):
        """Play the whole super until the victim is thrown to the floor."""
        self.command()
        for _ in range(300):
            self.game.step(1 / 60, [{}, {}])
            if self.game.fighters[1]["knocked"]:
                return

    def test_ssjk_command_starts_super(self):
        self.command()
        self.assertEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 0)

    def test_punch_and_kick_alone_do_not_start_red_super(self):
        # Without the S S prefix, J+K must fall back to an ordinary attack.
        self.run_frames({"punch": True, "kick": True})
        self.assertNotEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 100)

    def test_ssjk_needs_full_energy(self):
        self.game.fighters[0]["energy"] = 99
        self.command()
        self.assertNotEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 99)

    def test_grab_super_pummels_four_times_at_full_health(self):
        self.run_super()
        # Four punches of 40 at full caster health.
        self.assertEqual(self.game.fighters[1]["hp"], 800 - 160)
        self.assertTrue(self.game.fighters[1]["knocked"])
        # One tick of the victim's own update has already run.
        self.assertGreaterEqual(self.game.fighters[1]["stun"], 1.98)

    def test_grab_super_adds_hits_as_the_caster_loses_health(self):
        # 40% health lost: two extra punches (6 x 40).
        self.game.fighters[0]["hp"] = 600
        self.run_super()
        self.assertEqual(self.game.fighters[1]["hp"], 800 - 240)

    def test_grab_super_caps_at_ten_hits(self):
        # 90% health lost: six extra punches, capped at 10 (400 total).
        self.game.fighters[0]["hp"] = 100
        self.run_super()
        self.assertEqual(self.game.fighters[1]["hp"], 800 - 400)

    def test_grab_super_pulls_a_foe_from_double_radius(self):
        # The pull range is a 300 px radius, twice the old blast radius.
        self.game.fighters[1]["x"] = 280.
        self.command()
        for _ in range(80):
            self.game.step(1 / 60, [{}, {}])
            if self.game.fighters[0]["pummel_hits"]:
                break
        caster = self.game.fighters[0]
        self.assertGreater(caster["pummel_hits"], 0)
        # Wait out the pull-in animation so the victim reaches the caster's front.
        for _ in range(GRAB_PULL_FRAMES + 2):
            self.game.step(1 / 60, [{}, {}])
        victim = self.game.fighters[1]
        self.assertAlmostEqual(victim["x"], caster["x"] + caster["face"] * 54.)
        self.assertEqual(victim["face"], -caster["face"])

    def test_grab_super_misses_outside_the_pull_range(self):
        self.game.fighters[1]["x"] = 60.
        self.command()
        self.run_frames({}, frames=140)
        self.assertEqual(self.game.fighters[1]["hp"], 800)
        self.assertEqual(self.game.fighters[1]["action"], "idle")

    def test_grab_super_throws_half_the_map(self):
        self.run_super()
        victim = self.game.fighters[1]
        # Held at caster.x + 54, then hurled another 464 px (half the arena).
        self.assertAlmostEqual(victim["x"], 400. + 54. + 464.)
        self.assertTrue(victim["knocked"])

    def test_knockdown_blocks_actions_for_two_seconds(self):
        self.run_super()
        victim = self.game.fighters[1]
        self.assertTrue(victim["knocked"])
        self.assertGreaterEqual(victim["stun"], 1.98)
        # The action reflects the next simulation tick.
        self.run_frames({}, frames=1)
        self.assertEqual(victim["action"], "downed")
        # J does nothing while the victim is on the ground.
        for _ in range(60):
            self.game.step(1 / 60, [{}, {"punch": True}])
            self.assertEqual(victim["attack_kind"], "")
            self.assertEqual(victim["action"], "downed")
        # Wait out the rest of the 2 s knockdown; the victim keeps lying down
        # (and stays untouchable) until the player sends a command.
        for _ in range(140):
            self.game.step(1 / 60, [{}, {}])
            if victim["stun"] <= 0:
                break
        self.assertTrue(victim["knocked"])
        self.assertEqual(victim["action"], "downed")
        # Any command gets them up immediately and lets them act right away.
        self.game.step(1 / 60, [{}, {"punch": True}])
        self.assertFalse(victim["knocked"])
        self.assertEqual(victim["attack_kind"], "punch")

    def test_blue_headband_rush_super_uses_double_tap_punch_command(self):
        game = Combat()
        game.set_loadout(0, CHARACTERS["blue_headband"])
        game.set_loadout(1, CHARACTERS["red_scarf"])
        game.fighters[0]["energy"] = 100
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 490.
        # D D then J J: double tap the direction key, then punch twice.
        for keys in ({"right": True}, {}, {"right": True}, {}, {"punch": True}, {},
                     {"punch": True}):
            game.step(1 / 60, [keys, {}])
        # The first punch must finish before the buffered super begins.
        for _ in range(ATTACKS["punch"].total + 4):
            game.step(1 / 60, [{}, {}])
        self.assertEqual(game.fighters[0]["attack_kind"], "super")
        # Once the active frames start the caster flashes behind the target and
        # turns back to cut them.
        hp_before = game.fighters[1]["hp"]
        for _ in range(20):
            game.step(1 / 60, [{}, {}])
        self.assertGreater(game.fighters[0]["x"], game.fighters[1]["x"])
        self.assertEqual(game.fighters[0]["face"], -1)
        for _ in range(60):
            game.step(1 / 60, [{}, {}])
        # Five cuts of 30 damage each.
        self.assertEqual(hp_before - game.fighters[1]["hp"], 150)

    def test_blue_headband_ice_shadow_dives_and_bursts_under_foe(self):
        game = Combat()
        game.set_loadout(0, CHARACTERS["blue_headband"])
        game.set_loadout(1, CHARACTERS["red_scarf"])
        game.fighters[0]["energy"] = 100
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 490.
        # S S 移动键 J：双击下蹲、点一下方向键、再按拳。
        for keys in ({"down": True}, {}, {"down": True}, {}, {"right": True}, {},
                     {"punch": True}, {}):
            game.step(1 / 60, [keys, {}])
        self.assertEqual(game.fighters[0]["attack_kind"], "ice_shadow")
        self.assertEqual(game.fighters[0]["energy"], 70)
        # 钻地前摇后进入潜行阶段，身体埋入地下（隐藏、无敌）。
        for _ in range(SHADOW_BURROW):
            game.step(1 / 60, [{}, {}])
        self.assertEqual(shadow_phase(game.fighters[0]), "hide")
        self.assertLess(game.fighters[0]["y"], 0)
        # 潜行 1 秒后从敌人脚下冲出，命中 70 伤害并瞬移至敌人附近。
        hp_before = game.fighters[1]["hp"]
        for _ in range(SHADOW_HIDE + 2):
            game.step(1 / 60, [{}, {}])
        self.assertEqual(hp_before - game.fighters[1]["hp"], 70)
        self.assertGreater(game.fighters[0]["y"], 0)

    def test_interrupted_ice_shadow_returns_to_the_ground(self):
        """钻地被击倒时必须复位高度，否则重力不生效会卡在地下。"""
        game = Combat()
        game.set_loadout(0, CHARACTERS["blue_headband"])
        game.set_loadout(1, CHARACTERS["red_scarf"])
        game.fighters[0]["energy"] = 100
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 490.
        for keys in ({"down": True}, {}, {"down": True}, {}, {"right": True}, {},
                     {"punch": True}, {}):
            game.step(1 / 60, [keys, {}])
        for _ in range(4):
            game.step(1 / 60, [{}, {}])
        self.assertEqual(game.fighters[0]["attack_kind"], "ice_shadow")
        self.assertLess(game.fighters[0]["y"], 0)
        # 击倒打断钻地：攻击被取消，高度必须回到地面。
        game._knock_down(0, [])
        game.step(1 / 60, [{}, {}])
        self.assertEqual(game.fighters[0]["attack_kind"], "")
        self.assertEqual(game.fighters[0]["y"], 0)
        self.assertTrue(game.fighters[0]["knocked"])
        # 倒地期间也保持在地面上，不会重新陷下去。
        for _ in range(30):
            game.step(1 / 60, [{}, {}])
            self.assertEqual(game.fighters[0]["y"], 0)

    def test_red_scarf_ssu_buff_powers_the_next_three_attacks(self):
        game = Combat()
        game.set_loadout(0, CHARACTERS["red_scarf"])
        game.set_loadout(1, CHARACTERS["blue_headband"])
        game.fighters[0]["energy"] = 100
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 490.
        # S S U: double tap down, then the projectile button.
        for keys in ({"down": True}, {}, {"down": True}, {}, {"projectile": True}, {}):
            game.step(1 / 60, [keys, {}])
        self.assertEqual(game.fighters[0]["attack_kind"], "flame_buff")
        self.assertEqual(game.fighters[0]["buff_charges"], 3)
        self.assertEqual(game.fighters[0]["energy"], 75)
        for _ in range(40):
            game.step(1 / 60, [{}, {}])
        self.assertEqual(game.fighters[0]["attack_kind"], "")
        hp = game.fighters[1]["hp"]
        game.step(1 / 60, [{"punch": True}, {}])
        for _ in range(10):
            game.step(1 / 60, [{}, {}])
        # Punch 9 + flame bonus 50.
        self.assertEqual(hp - game.fighters[1]["hp"], 59)
        self.assertEqual(game.fighters[0]["buff_charges"], 2)

    def test_red_scarf_buff_finisher_throws_a_projectile(self):
        game = Combat()
        game.set_loadout(0, CHARACTERS["red_scarf"])
        game.set_loadout(1, CHARACTERS["blue_headband"])
        game.fighters[0]["energy"] = 100
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 490.
        for keys in ({"down": True}, {}, {"down": True}, {}, {"projectile": True}, {}):
            game.step(1 / 60, [keys, {}])
        for _ in range(40):
            game.step(1 / 60, [{}, {}])
        # Three connecting kicks: the third one also fires a projectile.
        hits = 0
        for _ in range(3):
            game.step(1 / 60, [{"kick": True}, {}])
            for _ in range(35):
                events = game.step(1 / 60, [{}, {}])
                if any(e["event"] == "hit" and e["player"] == 0 for e in events):
                    hits += 1
                    if hits == 3:
                        self.assertGreaterEqual(len(game.projectiles), 1)
                        self.assertEqual(game.fighters[0]["buff_charges"], 0)
                        return
        self.fail("the third charged kick never connected")


class DoubleJumpTests(unittest.TestCase):
    """W / space may be used a second time before landing, once per airtime."""

    def jump_at(self, frames, presses):
        events, _ = self.jump_curve(frames, presses)
        return events

    def jump_curve(self, frames, presses):
        events, peak = [], 0.
        for n in range(frames):
            keys = {"jump": True} if n in presses else {}
            events += self.game.step(1 / 60, [keys, {}])
            peak = max(peak, self.game.fighters[0]["y"])
        return events, peak

    def setUp(self):
        self.game = Combat()

    def test_second_jump_boosts_vertical_speed(self):
        self.jump_at(8, (0,))
        before = self.game.fighters[0]["vy"]
        self.jump_at(1, (0,))
        self.assertTrue(self.game.fighters[0]["air_jump"])
        self.assertGreater(self.game.fighters[0]["vy"], before)
        self.assertGreater(self.game.fighters[0]["y"], 0)

    def test_double_jump_reaches_higher_than_single(self):
        _, peak_single = self.jump_curve(90, (0,))
        self.game = Combat()
        _, peak_double = self.jump_curve(90, (0, 14))
        self.assertGreater(peak_double, peak_single + 30)

    def test_triple_jump_is_blocked(self):
        events = self.jump_at(30, (0, 10, 20))
        jumps = [e for e in events if e["event"] == "jump" and e["player"] == 0]
        self.assertEqual(len(jumps), 2)
        self.assertTrue(jumps[1].get("air"))
        self.assertTrue(self.game.fighters[0]["air_jump"])

    def test_air_jump_resets_after_landing(self):
        self.jump_at(30, (0, 10))
        self.assertTrue(self.game.fighters[0]["air_jump"])
        self.jump_at(80, ())
        self.assertEqual(self.game.fighters[0]["y"], 0.)
        self.assertFalse(self.game.fighters[0]["air_jump"])
        # A fresh hop can still use the second jump.
        self.jump_at(30, (0, 10))
        self.assertTrue(self.game.fighters[0]["air_jump"])


class ProjectileHitboxTests(unittest.TestCase):
    """Shots fly at neck height and use the whole body box, head included."""

    CONFIG = {"damage": 14, "speed": 420, "lifetime": .8,
              "color": (255, 130, 60), "size": 8}

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["projectile_config"] = dict(self.CONFIG)

    def advance(self, frames, opponent_keys=None):
        for _ in range(frames):
            self.game.step(1 / 60, [{}, opponent_keys or {}])

    def test_shot_spawns_at_neck_height(self):
        self.game.fighters[0]["x"] = 300
        self.game.fighters[1]["x"] = 800
        self.game.step(1 / 60, [{"projectile": True}, {}])
        self.advance(12)
        self.assertEqual(len(self.game.projectiles), 1)
        self.assertEqual(self.game.projectiles[0]["y"], NECK_HEIGHT)

    def test_neck_shot_hits_grounded_opponent(self):
        self.game.fighters[0]["x"] = 400
        self.game.fighters[1]["x"] = 520
        self.game.step(1 / 60, [{"projectile": True}, {}])
        self.advance(20)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 14)

    def test_neck_shot_flies_over_a_crouching_opponent(self):
        self.game.fighters[0]["x"] = 400
        self.game.fighters[1]["x"] = 520
        self.game.step(1 / 60, [{"projectile": True}, {}])
        self.advance(20, {"down": True})
        self.assertEqual(self.game.fighters[1]["hp"], 1000)
        self.assertEqual(len(self.game.projectiles), 1)

    def test_neck_shot_hits_when_opponent_stands_into_it(self):
        # Crouch under the shot, then stand up while it is still in flight:
        # the current posture decides, so the shot connects.
        self.game.fighters[0]["x"] = 300
        self.game.fighters[1]["x"] = 640
        self.game.step(1 / 60, [{"projectile": True}, {}])
        self.advance(30, {"down": True})
        self.assertEqual(self.game.fighters[1]["hp"], 1000)
        self.advance(22, {})
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 14)

    def test_standing_guard_blocks_a_high_shot(self):
        self.game.fighters[0]["x"] = 400
        self.game.fighters[1]["x"] = 520
        self.game.step(1 / 60, [{"projectile": True}, {"guard": True}])
        self.advance(26, {"guard": True})
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 2)

    def test_standing_guard_does_not_stop_a_low_shot(self):
        self.game.fighters[0]["x"] = 400
        self.game.fighters[1]["x"] = 520
        self.game.step(1 / 60, [{"down": True, "projectile": True}, {"guard": True}])
        self.advance(26, {"guard": True})
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 14)

    def test_crouch_guard_blocks_a_low_shot(self):
        self.game.fighters[0]["x"] = 400
        self.game.fighters[1]["x"] = 520
        self.game.step(1 / 60, [{"down": True, "projectile": True},
                                {"down": True, "guard": True}])
        self.advance(26, {"down": True, "guard": True})
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 2)

    def test_crouch_guard_ducks_under_a_high_shot(self):
        self.game.fighters[0]["x"] = 400
        self.game.fighters[1]["x"] = 520
        self.game.step(1 / 60, [{"projectile": True}, {"down": True, "guard": True}])
        self.advance(26, {"down": True, "guard": True})
        self.assertEqual(self.game.fighters[1]["hp"], 1000)

    def test_shot_above_the_head_misses(self):
        self.game.fighters[1]["x"] = 500
        self.game.projectiles = [{"x": 500, "y": BODY_TOP + 40, "vx": 0.,
                                  "damage": 14, "lifetime": .5, "owner": 0,
                                  "color": self.CONFIG["color"],
                                  "size": self.CONFIG["size"], "hit": False}]
        self.game.step(1 / 60, [{}, {}])
        self.assertEqual(self.game.fighters[1]["hp"], 1000)
        self.assertEqual(len(self.game.projectiles), 1)

    def test_shot_below_a_jumping_opponent_misses(self):
        self.game.fighters[1]["x"] = 500
        self.game.fighters[1]["y"] = 120.
        self.game.fighters[1]["vy"] = 0.
        self.game.projectiles = [{"x": 500, "y": 60., "vx": 0.,
                                  "damage": 14, "lifetime": .5, "owner": 0,
                                  "color": self.CONFIG["color"],
                                  "size": self.CONFIG["size"], "hit": False}]
        self.game.step(1 / 60, [{}, {}])
        self.assertEqual(self.game.fighters[1]["hp"], 1000)

    def test_vertical_body_box_reaches_above_head_centre(self):
        # A shot level with the top of the head still connects: the box covers
        # the full drawn figure instead of only the feet position.
        self.game.fighters[1]["x"] = 500
        self.game.projectiles = [{"x": 500, "y": BODY_TOP - 4., "vx": 0.,
                                  "damage": 14, "lifetime": .5, "owner": 0,
                                  "color": self.CONFIG["color"],
                                  "size": self.CONFIG["size"], "hit": False}]
        self.game.step(1 / 60, [{}, {}])
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 14)


class RoundCountdownTests(unittest.TestCase):
    """Every round opens with a frozen three-second countdown."""

    def tick(self, game, frames):
        for _ in range(frames):
            game.step(1 / 60, [{}, {}])

    def test_new_round_starts_with_three_second_countdown(self):
        game = Combat()
        game.finish_round(0)
        for _ in range(200):               # exhaust the round-end pause
            game.step(1 / 60, [{}, {}])
            if game.phase == "game":
                break
        self.assertEqual(game.round, 2)
        self.assertEqual(game.phase, "game")
        self.assertEqual(game.countdown, ROUND_COUNTDOWN)
        self.assertEqual(game.snapshot()["countdown"], 3.0)

    def test_countdown_freezes_fighters_and_clock(self):
        game = Combat()
        game.start_round()
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 480.
        x0, hp0, time0 = game.fighters[0]["x"], game.fighters[1]["hp"], game.time_left
        events = []
        for _ in range(120):               # 2 seconds of held input inside the countdown
            events += game.step(1 / 60, [{"punch": True, "right": True}, {}])
        self.assertAlmostEqual(game.time_left, time0, places=2)
        self.assertEqual(game.fighters[0]["x"], x0)
        self.assertEqual(game.fighters[1]["hp"], hp0)
        self.assertFalse([e for e in events if e["event"] == "punch"])
        self.assertAlmostEqual(game.countdown, ROUND_COUNTDOWN - 2, delta=.05)

    def test_round_clock_runs_after_countdown(self):
        game = Combat()
        game.start_round()
        game.countdown = 0.                # skip ahead
        game.step(1 / 60, [{}, {}])
        self.assertLess(game.time_left, 65.)
        game.countdown = 0.
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 485.
        for _ in range(10):
            game.step(1 / 60, [{"punch": True}, {}])
        self.assertEqual(game.fighters[1]["hp"], 1000 - 9)

    def test_each_round_gets_its_own_countdown(self):
        game = Combat()
        game.start_round()
        self.assertEqual(game.countdown, ROUND_COUNTDOWN)
        game.countdown = 0.
        game.finish_round(0)
        for _ in range(200):
            game.step(1 / 60, [{}, {}])
            if game.phase == "game":
                break
        self.assertEqual(game.countdown, ROUND_COUNTDOWN)


class LoadoutAndCarryTests(unittest.TestCase):
    """Per-character stats, and energy that survives between rounds."""

    def next_round(self, game):
        game.finish_round(0)
        for _ in range(200):
            game.step(1 / 60, [{}, {}])
            if game.phase == "game":
                break

    def test_set_loadout_applies_health_and_skills(self):
        from fighter.characters import CHARACTERS
        game = Combat()
        game.set_loadout(0, CHARACTERS['red_scarf'])
        game.set_loadout(1, CHARACTERS['blue_headband'])
        self.assertEqual(game.fighters[0]["hp"], 1000)
        self.assertEqual(game.fighters[0]["hp_max"], 1000)
        self.assertEqual(game.fighters[1]["hp"], 800)
        self.assertEqual(game.fighters[0]["char_id"], "red_scarf")
        self.assertEqual(game.fighters[0]["super_spec"].name, "拿来吧你")
        self.assertEqual(game.fighters[1]["super_spec"].name, "霜影奔袭")
        self.assertEqual(game.fighters[0]["combo_spec"]["name"], "素质三连")
        self.assertEqual(game.fighters[0]["move_speed"], CHARACTERS['red_scarf']['move_speed'])
        self.assertEqual(game.fighters[1]["move_speed"], CHARACTERS['blue_headband']['move_speed'])
        self.assertGreater(game.fighters[1]["dash_speed"], game.fighters[0]["dash_speed"])

    def test_energy_carries_into_next_round_but_health_resets(self):
        from fighter.characters import CHARACTERS
        game = Combat()
        game.set_loadout(0, CHARACTERS['red_scarf'])
        game.set_loadout(1, CHARACTERS['blue_headband'])
        game.fighters[0]["energy"] = 60
        game.fighters[1]["energy"] = 30
        game.fighters[0]["hp"] = 120
        self.next_round(game)
        self.assertEqual(game.fighters[0]["energy"], 60)
        self.assertEqual(game.fighters[1]["energy"], 30)
        self.assertEqual(game.fighters[0]["hp"], 1000)
        self.assertEqual(game.fighters[1]["hp"], 800)
        self.assertEqual(game.fighters[0]["super_spec"].name, "拿来吧你")
        self.assertEqual(game.fighters[1]["move_speed"], 340)

    def test_each_character_super_uses_its_own_damage(self):
        from fighter.characters import CHARACTERS
        game = Combat()
        game.set_loadout(0, CHARACTERS['red_scarf'])
        game.set_loadout(1, CHARACTERS['blue_headband'])
        game.fighters[0]["energy"] = 100
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 490.
        # Red scarf needs the S S J K command.
        for keys in ({"down": True}, {}, {"down": True}, {},
                     {"punch": True, "kick": True}):
            game.step(1 / 60, [keys, {}])
        self.assertEqual(game.fighters[0]["attack_kind"], "super")
        for _ in range(120):
            game.step(1 / 60, [{}, {}])
        # At full caster health the grab super lands 4 punches of 40.
        self.assertEqual(game.fighters[1]["hp"], 800 - 160)


class NumericTuningTests(unittest.TestCase):
    """Normal attacks and projectiles keep the small damage scale."""

    def test_normal_attack_damage_values(self):
        values = {kind: ATTACKS[kind].damage for kind in
                  ('punch', 'kick', 'low_kick', 'jump_punch')}
        self.assertEqual(values, {'punch': 9, 'kick': 15, 'low_kick': 12,
                                  'jump_punch': 11})

    def test_character_health_skill_and_super_values(self):
        red, blue = CHARACTERS['red_scarf'], CHARACTERS['blue_headband']
        self.assertEqual((red['health'], blue['health']), (1000, 800))
        self.assertEqual((red['projectile']['damage'], blue['projectile']['damage']), (14, 11))
        self.assertEqual((red['super'].damage, blue['super'].damage), (400, 150))

    def test_blue_headband_is_faster_than_red_scarf(self):
        red, blue = CHARACTERS['red_scarf'], CHARACTERS['blue_headband']
        self.assertEqual((red['move_speed'], blue['move_speed']), (300, 340))
        self.assertGreater(blue['move_speed'], red['move_speed'])

    def test_speed_loadout_changes_walk_distance(self):
        def travelled(style, frames=30):
            game = Combat()
            game.set_loadout(0, style)
            game.fighters[0]['x'] = 200.
            start = game.fighters[0]['x']
            for _ in range(frames):
                game.step(1 / 60, [{"right": True}, {}])
            return game.fighters[0]['x'] - start

        red_move = travelled(CHARACTERS['red_scarf'])
        blue_move = travelled(CHARACTERS['blue_headband'])
        self.assertGreater(blue_move, red_move)
        self.assertAlmostEqual(blue_move / red_move, 340 / 300, delta=.05)

    def test_character_speed_uses_move_speed_field(self):
        for style in CHARACTERS.values():
            self.assertIn("move_speed", style)
            # The legacy ambiguous "speed" key must not linger (projectiles keep their own speed).
            self.assertNotIn("speed", style)
            self.assertGreater(style["move_speed"], 0)

    def test_walk_distance_matches_move_speed_per_second(self):
        def travelled(style, frames=30):
            game = Combat()
            game.set_loadout(0, style)
            game.fighters[0]['x'] = 200.
            start = game.fighters[0]['x']
            for _ in range(frames):
                game.step(1 / 60, [{"right": True}, {}])
            return game.fighters[0]['x'] - start

        half_second = 30 / 60
        self.assertAlmostEqual(travelled(CHARACTERS['red_scarf']), 300 * half_second, delta=.5)
        self.assertAlmostEqual(travelled(CHARACTERS['blue_headband']), 340 * half_second, delta=.5)

    def test_punch_deals_nine_against_character_health(self):
        game = Combat()
        game.set_loadout(0, CHARACTERS['red_scarf'])
        game.set_loadout(1, CHARACTERS['blue_headband'])
        game.fighters[0]['x'], game.fighters[1]['x'] = 400., 485.
        for _ in range(10):
            game.step(1 / 60, [{"punch": True}, {}])
        self.assertEqual(game.fighters[1]["hp"], 800 - 9)

    def test_projectile_uses_the_character_config(self):
        game = Combat()
        game.set_loadout(0, CHARACTERS['red_scarf'])
        game.set_loadout(1, CHARACTERS['blue_headband'])
        game.fighters[0]['x'], game.fighters[1]['x'] = 400., 700.
        game.step(1 / 60, [{}, {"projectile": True}])
        for _ in range(80):
            game.step(1 / 60, [{}, {}])
        self.assertEqual(game.fighters[0]["hp"], 1000 - 11)


class BasicInputTests(unittest.TestCase):
    """S-modifier moves, grabs and buffered attack inputs."""

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 470.

    def run_frames(self, own, cpu=None, frames=1):
        for _ in range(frames):
            self.game.step(1 / 60, [own, cpu or {}])

    def test_crouch_punch(self):
        self.run_frames({"down": True, "punch": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "crouch_punch")
        self.run_frames({"down": True}, frames=12)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - ATTACKS["crouch_punch"].damage)

    def test_crouch_kick_performs_low_kick(self):
        self.run_frames({"down": True, "kick": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "low_kick")
        self.run_frames({"down": True}, frames=24)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - ATTACKS["low_kick"].damage)

    def test_crouch_projectile_fires_from_a_low_height(self):
        self.game.fighters[1]["x"] = 900.
        self.run_frames({"down": True, "projectile": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "crouch_projectile")
        self.run_frames({"down": True}, frames=12)
        self.assertEqual(len(self.game.projectiles), 1)
        self.assertEqual(self.game.projectiles[0]["y"], CROUCH_PROJ_HEIGHT)
        self.assertLess(CROUCH_PROJ_HEIGHT, NECK_HEIGHT)

    def test_releasing_down_as_punch_arrives_still_crouches(self):
        # 同帧松开 S 的同时按 J：方向与攻击键几乎同时变化，仍应按蹲拳判定。
        self.run_frames({"down": True})
        self.run_frames({"punch": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "crouch_punch")

    def test_buffered_punch_remembers_the_direction_at_press_time(self):
        # 硬直中蹲着按下 J，随后松开 S；恢复行动后接上的应该仍是蹲拳。
        f = self.game.fighters[0]
        f["stun"] = 5 / 60
        self.run_frames({"down": True, "punch": True})
        self.run_frames({"punch": True}, frames=8)
        self.assertEqual(f["attack_kind"], "crouch_punch")

    def test_crouch_guard_blocks(self):
        self.run_frames({"down": True, "guard": True})
        self.assertEqual(self.game.fighters[0]["action"], "crouch_guard")
        # The attack punches into a crouching guard: chip damage only.
        self.run_frames({"punch": True}, {"down": True, "guard": True}, frames=14)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 1)

    def test_standing_guard_loses_to_crouching_attacks(self):
        self.run_frames({"down": True, "kick": True}, {"guard": True}, frames=26)
        self.assertEqual(self.game.fighters[1]["hp"],
                         1000 - ATTACKS["low_kick"].damage)

    def test_standing_guard_loses_to_crouch_punch(self):
        self.run_frames({"down": True, "punch": True}, {"guard": True}, frames=20)
        self.assertEqual(self.game.fighters[1]["hp"],
                         1000 - ATTACKS["crouch_punch"].damage)

    def test_crouch_guard_stops_low_attacks(self):
        self.run_frames({"down": True, "kick": True},
                        {"down": True, "guard": True}, frames=26)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 2)

    def test_grab_beats_crouch_guard_too(self):
        self.run_frames({"grab": True}, {"down": True, "guard": True}, frames=10)
        self.assertEqual(self.game.fighters[1]["hp"],
                         1000 - ATTACKS["grab"].damage)

    def test_grab_is_unblockable_and_stuns(self):
        # Guarding does not stop a grab and does not reduce its damage or stun.
        self.run_frames({"grab": True}, {"guard": True}, frames=10)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - ATTACKS["grab"].damage)
        self.assertGreater(self.game.fighters[1]["stun"], .8)
        # While stunned the victim cannot start an attack.
        self.run_frames({}, {"punch": True}, frames=6)
        self.assertEqual(self.game.fighters[1]["attack_kind"], "")

    def test_grab_cannot_loop_but_allows_a_follow_up(self):
        self.run_frames({"grab": True}, frames=8)
        grabbed_hp = self.game.fighters[1]["hp"]
        # A second grab on the long-stunned victim is buffered behind the first
        # grab, then whiffs once it finally starts.
        self.run_frames({}, frames=1)
        self.run_frames({"grab": True}, frames=1)
        self.run_frames({}, frames=ATTACKS["grab"].total + ATTACKS["grab"].total)
        self.assertEqual(self.game.fighters[1]["hp"], grabbed_hp)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "")

    def test_single_buttons_chain_after_a_hit(self):
        self.run_frames({"punch": True}, frames=8)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 9)
        # Kick is buffered during the punch recovery and starts when it ends.
        self.run_frames({"kick": True}, frames=1)
        self.run_frames({}, frames=ATTACKS["punch"].total)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "kick")
        self.run_frames({}, frames=ATTACKS["kick"].total)
        kick = max(1, int(ATTACKS["kick"].damage * COMBO_SCALING[1]))
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 9 - kick)

    def test_grab_then_punch_follow_up(self):
        self.run_frames({"grab": True}, frames=9)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 12)
        # The punch waits for the grab's full recovery, then fires.
        self.run_frames({"punch": True}, frames=1)
        self.run_frames({}, frames=ATTACKS["grab"].total)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "punch")
        self.run_frames({}, frames=8)
        punch = max(1, int(ATTACKS["punch"].damage * COMBO_SCALING[1]))
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 12 - punch)


class FullCommitmentTests(unittest.TestCase):
    """Every attack plays its full startup/active/recovery; presses are buffered."""

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 470.

    def run_frames(self, own, cpu=None, frames=1):
        for _ in range(frames):
            self.game.step(1 / 60, [own, cpu or {}])

    def test_second_button_waits_for_the_full_move(self):
        self.run_frames({"punch": True})
        self.run_frames({"kick": True})
        # The kick press is buffered, not a recovery cancel.
        self.assertEqual(self.game.fighters[0]["attack_kind"], "punch")
        self.assertEqual(self.game.fighters[0]["queued_attack"], "kick")
        self.run_frames({}, frames=ATTACKS["punch"].total - 2)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "punch")
        self.run_frames({}, frames=6)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "kick")

    def test_property_of_every_attack(self):
        for kind, spec in ATTACKS.items():
            self.assertGreater(spec.startup, 0, kind)
            self.assertGreater(spec.recovery, 0, kind)
            self.assertEqual(spec.total, spec.startup + spec.active + spec.recovery)
        for name, style in CHARACTERS.items():
            super_spec = style["super"]
            # 迪奥的砸瓦鲁多是零帧起手；其余角色的大招都有正前摇。
            if name == "dio":
                self.assertEqual(super_spec.startup, 0, name)
            else:
                self.assertGreater(super_spec.startup, 0, name)
            self.assertGreater(super_spec.recovery, 0, name)

    def test_super_command_does_not_cancel_a_punch(self):
        self.game.fighters[0]["energy"] = 100
        # Out of punch reach, so the setup punch cannot pay the attacker energy.
        self.game.fighters[1]["x"] = 520.
        self.run_frames({"punch": True})
        self.run_frames({"punch": True, "kick": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "punch")
        self.assertEqual(self.game.fighters[0]["queued_attack"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 100)
        self.run_frames({}, frames=ATTACKS["punch"].total + 10)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 0)

    def test_flame_buff_does_not_cancel_a_kick(self):
        self.game.set_loadout(0, CHARACTERS["red_scarf"])
        self.game.fighters[0]["energy"] = 100
        # Out of kick reach, so the buff cost is the only energy change.
        self.game.fighters[1]["x"] = 600.
        inputs = ({"kick": True}, {"down": True}, {}, {"down": True},
                  {"down": True, "projectile": True})
        for keys in inputs:
            self.run_frames(keys)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "kick")
        self.assertEqual(self.game.fighters[0]["queued_attack"], "flame_buff")
        self.assertEqual(self.game.fighters[0]["energy"], 100)
        self.run_frames({}, frames=ATTACKS["kick"].total + ATTACKS["flame_buff"].total)
        self.assertEqual(self.game.fighters[0]["buff_charges"], 3)
        self.assertEqual(self.game.fighters[0]["energy"], 75)

    def test_mashing_a_whiffed_key_cannot_skip_recovery(self):
        # Out of reach, so nothing connects and no cancel window can open.
        self.game.fighters[1]["x"] = 600.
        starts = []
        for i in range(150):
            keys = {"punch": True} if i % 2 == 0 else {}
            for event in self.game.step(1 / 60, [keys, {}]):
                if event["event"] == "punch":
                    starts.append(i)
        self.assertGreaterEqual(len(starts), 3)
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        # Every repeat waits out the full move; no frame can be shaved off.
        self.assertTrue(all(g >= ATTACKS["punch"].total - 1 for g in gaps), gaps)

    def test_queued_attacks_fire_in_input_order(self):
        # 收招期间连按的招按输入顺序排队，不再互相覆盖。
        self.run_frames({"punch": True})
        self.run_frames({"kick": True})
        self.run_frames({"grab": True})
        self.assertEqual(self.game.fighters[0]["queued_attack"], "kick")
        self.assertEqual(self.game.fighters[0]["queued_more"], ["grab"])
        self.run_frames({}, frames=ATTACKS["punch"].total + 4)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "kick")
        self.assertEqual(self.game.fighters[0]["queued_attack"], "grab")
        self.run_frames({}, frames=ATTACKS["kick"].total + 4)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "grab")

    def test_buffered_attack_is_dropped_when_hit(self):
        self.run_frames({"punch": True}, {"punch": True})
        self.run_frames({"kick": True})
        self.assertEqual(self.game.fighters[0]["queued_attack"], "kick")
        self.run_frames({}, frames=10)
        self.assertEqual(self.game.fighters[0]["queued_attack"], "")
        self.run_frames({}, frames=ATTACKS["punch"].total)
        self.assertNotEqual(self.game.fighters[0]["attack_kind"], "kick")


class HitEnergyTests(unittest.TestCase):
    """Energy only comes from landing or taking damage."""

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 470.

    def run_frames(self, own, cpu=None, frames=1):
        for _ in range(frames):
            self.game.step(1 / 60, [own, cpu or {}])

    def test_melee_hit_gives_attacker_full_and_victim_half(self):
        self.run_frames({"punch": True}, frames=8)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 9)
        self.assertEqual(self.game.fighters[0]["energy"], 10)
        self.assertEqual(self.game.fighters[1]["energy"], 5)

    def test_super_hit_refunds_no_energy_but_still_pays_the_victim(self):
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[1]["x"] = 490.
        self.game.step(1 / 60, [{"punch": True, "kick": True}, {}])
        self.run_frames({}, frames=40)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - ATTACKS["super"].damage)
        self.assertEqual(self.game.fighters[0]["energy"], 0)
        self.assertEqual(self.game.fighters[1]["energy"], 5)

    def test_energy_gain_is_capped(self):
        self.game.fighters[0]["energy"] = 145
        self.game.fighters[1]["energy"] = 148
        self.run_frames({"punch": True}, frames=8)
        self.assertEqual(self.game.fighters[0]["energy"], MAX_ENERGY)
        self.assertEqual(self.game.fighters[1]["energy"], MAX_ENERGY)

    def test_skill_costs_stay_at_100_with_the_larger_cap(self):
        self.game.fighters[0]["energy"] = MAX_ENERGY
        self.game.step(1 / 60, [{"punch": True, "kick": True}, {}])
        self.assertEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"],
                         MAX_ENERGY - ATTACKS["super"].energy)

    def test_multihit_super_refunds_no_energy(self):
        game = Combat()
        game.set_loadout(0, CHARACTERS["blue_headband"])
        game.set_loadout(1, CHARACTERS["red_scarf"])
        game.fighters[0]["energy"] = 100
        # Out of punch reach, so only the super's five cuts connect.
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 540.
        for keys in ({"right": True}, {}, {"right": True}, {}, {"punch": True}, {},
                     {"punch": True}):
            game.step(1 / 60, [keys, {}])
        for _ in range(ATTACKS["punch"].total + 100):
            game.step(1 / 60, [{}, {}])
        self.assertEqual(game.fighters[1]["hp"],
                         1000 - CHARACTERS["blue_headband"]["super"].damage)
        self.assertEqual(game.fighters[0]["energy"], 0)
        # Five shoved hits, each paying the victim half of the melee gain.
        self.assertEqual(game.fighters[1]["energy"], 5 * 5)

    def test_projectile_hit_splits_energy(self):
        self.game.set_loadout(0, CHARACTERS["red_scarf"])
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 800.
        self.game.step(1 / 60, [{"projectile": True}, {}])
        self.run_frames({}, frames=60)
        self.assertEqual(self.game.fighters[1]["hp"],
                         1000 - CHARACTERS["red_scarf"]["projectile"]["damage"])
        self.assertEqual(self.game.fighters[0]["energy"], 8)
        self.assertEqual(self.game.fighters[1]["energy"], 4)


class StaggerTests(unittest.TestCase):
    """Short hit-stun, stagger build-up, knockdown and downed immunity."""

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 485.

    def feed(self, own, cpu=None):
        self.game.step(1 / 60, [own, cpu or {}])

    def knock_victim_down(self):
        victim = self.game.fighters[1]
        for frame in range(200):
            self.feed({"punch": True} if frame % 2 == 0 else {})
            self.game.fighters[0]["x"] = 400.
            if victim["knocked"]:
                break
            victim["x"] = 485.
        self.assertTrue(victim["knocked"], "a long hit-stun combo should floor the victim")
        for _ in range(6):
            if victim["action"] == "downed":
                break
            self.feed({})
        self.assertEqual(victim["action"], "downed")
        return victim

    def test_hit_causes_a_short_stagger(self):
        for _ in range(8):
            self.feed({"punch": True})
        victim = self.game.fighters[1]
        self.assertGreater(victim["stun"], 0.)
        self.assertFalse(victim["knocked"])
        self.assertEqual(victim["action"], "hurt")
        # The stagger locks out attacks and movement for a moment.
        x_before = victim["x"]
        for _ in range(6):
            self.feed({}, {"right": True, "punch": True})
        self.assertEqual(victim["attack_kind"], "")
        self.assertLessEqual(victim["x"], x_before + .01)

    def test_long_combo_floors_the_victim_for_two_seconds(self):
        victim = self.knock_victim_down()
        self.assertGreaterEqual(victim["stun"], 2. - 1 / 60)

    def test_downed_fighter_is_immune_to_attacks(self):
        victim = self.knock_victim_down()
        hp_before = victim["hp"]
        for frame in range(50):
            self.feed({"punch": True} if frame % 2 == 0 else {})
            self.game.fighters[0]["x"] = 400.
        self.assertEqual(victim["hp"], hp_before)
        self.assertTrue(victim["knocked"])

    def test_downed_fighter_waits_for_a_command_before_getting_up(self):
        victim = self.knock_victim_down()
        # The 2 s timer alone does not stand them up.
        for _ in range(150):
            self.feed({})
        self.assertTrue(victim["knocked"])
        self.assertEqual(victim["action"], "downed")
        # A movement command gets them up and moving on the same frame.
        x_before = victim["x"]
        self.feed({}, {"right": True})
        self.assertFalse(victim["knocked"])
        self.assertGreater(victim["x"], x_before)


class FrameDataTests(unittest.TestCase):
    """Per-move block-stun and the frame advantage it produces."""

    def test_frame_advantage_matches_the_table(self):
        expected = {
            "punch": (8, -1),
            "kick": (6, -4),
            "low_kick": (3, -8),
            "jump_punch": (2, -6),
            "crouch_punch": (4, -4),
        }
        for kind, (hit, block) in expected.items():
            spec = ATTACKS[kind]
            self.assertEqual(spec.hit_advantage, hit, kind)
            self.assertEqual(spec.block_advantage, block, kind)

    def test_every_normal_move_has_its_own_block_stun(self):
        for kind in ("punch", "kick", "low_kick", "jump_punch", "crouch_punch"):
            self.assertGreater(ATTACKS[kind].block_stun, 0, kind)

    def test_only_normals_open_a_cancel_window(self):
        for kind in ("punch", "kick", "low_kick", "jump_punch", "crouch_punch"):
            self.assertGreater(ATTACKS[kind].cancel, 0, kind)
        for kind in ("grab", "projectile", "super", "flame_buff",
                     "lightning_strike"):
            self.assertEqual(ATTACKS[kind].cancel, 0, kind)

    def test_punch_advantage_matches_the_simulation(self):
        game = Combat()
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 470.
        for _ in range(5):
            game.step(1 / 60, [{"punch": True}, {}])
        attacker_ready = defender_ready = None
        for i in range(40):
            attacker, defender = game.fighters
            if (attacker_ready is None and not attacker["attack_kind"]
                    and attacker["cooldown"] <= 0):
                attacker_ready = i
            if defender_ready is None and defender["stun"] <= 0:
                defender_ready = i
            game.step(1 / 60, [{}, {}])
        # The attacker acts exactly ``hit_advantage`` frames before the victim.
        self.assertEqual(defender_ready - attacker_ready,
                         ATTACKS["punch"].hit_advantage)


class HitCancelTests(unittest.TestCase):
    """Whiffs commit; a move that connects may cancel its recovery."""

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 470.

    def run_frames(self, own, cpu=None, frames=1):
        for _ in range(frames):
            self.game.step(1 / 60, [own, cpu or {}])

    def test_whiffed_punch_cannot_be_cancelled(self):
        self.game.fighters[1]["x"] = 600.
        self.run_frames({"punch": True})
        self.run_frames({"kick": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "punch")
        self.assertEqual(self.game.fighters[0]["queued_attack"], "kick")
        self.assertEqual(self.game.fighters[0]["cancel_left"], 0)

    def test_hit_opens_the_cancel_window(self):
        self.run_frames({"punch": True}, frames=5)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 9)
        self.assertEqual(self.game.fighters[0]["cancel_left"], ATTACKS["punch"].cancel)
        self.run_frames({}, frames=2)  # 结算打击停顿
        self.run_frames({"kick": True}, frames=2)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "kick")

    def test_cancel_window_expires(self):
        self.run_frames({"punch": True}, frames=5)
        self.run_frames({}, frames=2)  # 结算打击停顿
        self.run_frames({}, frames=ATTACKS["punch"].cancel)
        self.assertEqual(self.game.fighters[0]["cancel_left"], 0)
        self.run_frames({"kick": True}, frames=2)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "punch")
        self.assertEqual(self.game.fighters[0]["queued_attack"], "kick")

    def test_blocked_hit_also_opens_the_cancel_window(self):
        self.run_frames({"punch": True}, {"guard": True}, frames=5)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 1)
        self.assertGreater(self.game.fighters[0]["cancel_left"], 0)
        self.run_frames({}, {"guard": True}, frames=2)  # 结算打击停顿
        self.run_frames({"kick": True}, {"guard": True}, frames=2)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "kick")

    def test_block_stun_uses_the_move_value(self):
        self.run_frames({"punch": True}, {"guard": True}, frames=5)
        self.assertAlmostEqual(self.game.fighters[1]["stun"],
                               ATTACKS["punch"].block_stun / 60)
        other = Combat()
        other.fighters[0]["x"], other.fighters[1]["x"] = 400., 470.
        for _ in range(9):
            other.step(1 / 60, [{"kick": True}, {"guard": True}])
        self.assertAlmostEqual(other.fighters[1]["stun"],
                               ATTACKS["kick"].block_stun / 60)

    def test_cancel_chain_is_limited(self):
        starts = []
        for i in range(200):
            keys = {"punch": True} if i % 2 == 0 else {}
            for event in self.game.step(1 / 60, [keys, {}]):
                if event["event"] == "punch":
                    starts.append(i)
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        # Early hits cancel; after the limit the full recovery must play out.
        self.assertLess(gaps[0], ATTACKS["punch"].total - 1)
        self.assertGreaterEqual(gaps[MAX_CANCEL_CHAIN], ATTACKS["punch"].total - 1)

    def test_mashing_punch_cannot_loop_cancel_chains(self):
        # Regression: mashing J used to farm fresh cancel windows because a
        # fresh attack reset the chain. Now only a whiff or getting hit does.
        game = Combat()
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 448.
        starts = []
        for i in range(160):
            keys = {"punch": True} if i % 2 == 0 else {}
            for event in game.step(1 / 60, [keys, {}]):
                if event["event"] == "punch":
                    starts.append(i)
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        self.assertGreaterEqual(len(gaps), 5)
        # The first MAX_CANCEL_CHAIN connects cancel quickly; every later
        # start -- fresh or queued -- must play the full recovery animation.
        self.assertLess(gaps[0], ATTACKS["punch"].total - 1)
        for gap in gaps[MAX_CANCEL_CHAIN:]:
            self.assertGreaterEqual(gap, ATTACKS["punch"].total - 1)

    def test_hit_stun_scales_down_from_the_third_hit(self):
        # Regression: constant hit-stun used to lock the victim in an endless
        # combo; from the 3rd clean hit onward the hold shrinks like damage.
        punch = ATTACKS["punch"]

        def land_punch(game):
            for _ in range(30):
                events = game.step(1 / 60, [{"punch": True}, {}])
                if any(e["event"] == "hit" and e.get("attack") == "punch"
                       for e in events):
                    return game.fighters[1]["stun"]
            self.fail("punch never connected")

        def recover(game):
            for _ in range(120):
                game.step(1 / 60, [{}, {}])
                a, b = game.fighters
                if (not a["attack_kind"] and a["cooldown"] <= 0
                        and a["stun"] <= 0 and b["stun"] <= 0):
                    return
            self.fail("fighters never recovered")

        game = Combat()
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 460.
        first = land_punch(game)
        recover(game)
        second = land_punch(game)
        recover(game)
        third = land_punch(game)
        self.assertAlmostEqual(first, punch.stun / 60)
        self.assertAlmostEqual(second, punch.stun / 60)
        self.assertAlmostEqual(third, punch.stun * COMBO_SCALING[2] / 60)

    def test_blocked_hit_pushes_the_attacker_back(self):
        # Regression: guarding used to leave the attacker glued in range, so a
        # guarding opponent just got ground down by standing spam.
        game = Combat()
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 460.
        before = game.fighters[0]["x"]
        hp = game.fighters[1]["hp"]
        events = []
        for _ in range(10):
            events += game.step(1 / 60, [{"punch": True}, {"guard": True}])
        hits = [e for e in events if e["event"] == "hit"]
        self.assertTrue(hits and hits[0].get("blocked"))
        self.assertAlmostEqual(game.fighters[0]["x"], before - GUARD_PUSHBACK)
        self.assertEqual(game.fighters[1]["hp"], hp - ATTACKS["punch"].damage // 5)

    def test_getup_grants_brief_invulnerability(self):
        # Regression: fighters used to rise straight into the opponent's next
        # punch, so knockdowns never reset the exchange.
        game = Combat()
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 460.
        game._knock_down(1, [])
        hp = game.fighters[1]["hp"]
        for _ in range(122):    # 2 s floor plus the wake-up command
            game.step(1 / 60, [{}, {"left": True}])
        risen = game.fighters[1]
        self.assertFalse(risen["knocked"])
        self.assertGreater(risen["invuln"], 0.)   # window still open (tick-decayed)
        self.assertLessEqual(risen["invuln"], GETUP_INVULN_FRAMES / 60)
        # A punch thrown immediately on wake-up whiffs completely...
        for _ in range(12):
            game.step(1 / 60, [{"punch": True}, {}])
        self.assertEqual(game.fighters[1]["hp"], hp)
        self.assertFalse(game.fighters[0]["attack_hit"])
        # ...and once the window closes the same attack connects.
        for _ in range(45):
            game.step(1 / 60, [{}, {}])
        for _ in range(14):
            events = game.step(1 / 60, [{"punch": True}, {}])
            if any(e["event"] == "hit" for e in events):
                break
        self.assertLess(game.fighters[1]["hp"], hp)

    def test_combo_fatigue_extends_recovery(self):
        # Regression: a maxed cancel chain used to reset instantly with a
        # fresh punch, so spam never paid recovery. Tired swings take longer.
        game = Combat()
        f1 = game.fighters[0]
        game.fighters[1]["x"] = 460.
        game._start_attack(0, "punch", [])
        self.assertAlmostEqual(f1["cooldown"], ATTACKS["punch"].total / 60)
        f1["cancel_chain"] = MAX_CANCEL_CHAIN
        f1["action"] = f1["attack_kind"] = None
        f1["action_frame"] = 0
        f1["cooldown"] = 0.
        game._start_attack(0, "punch", [])
        self.assertAlmostEqual(
            f1["cooldown"], (ATTACKS["punch"].total + FATIGUE_RECOVERY) / 60)
        # Grabs and supers never fatigue.
        f1["action"] = f1["attack_kind"] = None
        f1["action_frame"] = 0
        f1["cooldown"] = 0.
        game._start_attack(0, "grab", [])
        self.assertAlmostEqual(f1["cooldown"], ATTACKS["grab"].total / 60)

    def test_blocked_low_kick_leaves_a_punish_window(self):
        # Blocked low kick is -8: the defender recovers before the attacker.
        guard = {"down": True, "guard": True}
        for _ in range(11):
            self.game.step(1 / 60, [{"down": True, "kick": True}, guard])
        self.assertEqual(self.game.fighters[0]["attack_kind"], "low_kick")
        defender = self.game.fighters[1]
        hp = self.game.fighters[0]["hp"]
        while defender["stun"] > 0:
            self.game.step(1 / 60, [{}, guard])
        # The attacker is still stuck in recovery: this is the punish window.
        self.assertEqual(self.game.fighters[0]["attack_kind"], "low_kick")
        for i in range(8):
            self.game.step(1 / 60, [{}, {"punch": True} if i == 0 else {}])
        self.assertGreater(hp - self.game.fighters[0]["hp"], 0)


class AirWhiffCancelTests(unittest.TestCase):
    """跳跃普通技挥空后，收招开头会开一个短窗口可取消成空中特殊技。"""

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["x"] = 300.
        self.game.fighters[1]["x"] = 900.    # 远离，跳跃拳必定挥空
        self.spec = ATTACKS["jump_punch"]

    def lift_and_start(self, y=300.):
        f = self.game.fighters[0]
        f["y"], f["vy"], f["grounded"] = y, 0., False
        self.game._start_attack(0, "jump_punch", [])

    def step(self, keys=None, frames=1):
        for _ in range(frames):
            self.game.step(1 / 60, [keys or {}, {}])

    def test_air_whiff_cancels_into_a_projectile(self):
        self.lift_and_start()
        self.step(frames=self.spec.startup + self.spec.active - 1)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "jump_punch")
        self.step({"projectile": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "projectile")

    def test_window_expires_after_a_few_frames(self):
        self.lift_and_start()
        self.step(frames=(self.spec.startup + self.spec.active - 1
                          + AIR_WHIFF_CANCEL_FRAMES + 1))
        self.assertEqual(self.game.fighters[0]["air_cancel_left"], 0)
        self.step({"projectile": True})
        self.assertNotEqual(self.game.fighters[0]["attack_kind"], "projectile")

    def test_a_connecting_air_punch_never_opens_the_window(self):
        # 打中了就没有挥空窗口：整段动作里 air_cancel_left 始终为 0。
        self.game.fighters[0]["x"], self.game.fighters[1]["x"] = 400., 450.
        self.lift_and_start(y=60.)
        peak = 0
        for _ in range(40):
            self.game.step(1 / 60, [{"projectile": True}, {}])
            peak = max(peak, self.game.fighters[0]["air_cancel_left"])
            if not self.game.fighters[0]["attack_kind"]:
                break
        self.assertEqual(peak, 0)


class ComboScalingTests(unittest.TestCase):
    """Later hits in the same string deal less damage and push further."""

    def setUp(self):
        self.game = Combat()
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 470.

    def feed(self, keys, frames=1, guard=None):
        """Advance frames; return (damage, push) for every hit that landed."""
        landed = []
        for _ in range(frames):
            victim = self.game.fighters[1]
            x_before = victim["x"]
            for event in self.game.step(1 / 60, [keys, guard or {}]):
                if event["event"] == "hit":
                    landed.append((event["damage"], victim["x"] - x_before))
        return landed

    def test_second_hit_in_a_combo_is_scaled_down(self):
        first = self.feed({"punch": True}, 5)
        self.assertEqual([d for d, _ in first], [ATTACKS["punch"].damage])
        self.feed({}, 1)  # release so the next press reads as a new input
        second = self.feed({"punch": True}) + self.feed({}, 10)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0][0],
                         max(1, int(ATTACKS["punch"].damage * COMBO_SCALING[1])))

    def test_pushback_grows_with_combo_depth(self):
        first = self.feed({"punch": True}, 5)
        self.feed({}, 1)
        second = self.feed({"kick": True}) + self.feed({}, 10)
        self.assertEqual(len(first), len(second))
        self.assertAlmostEqual(first[0][1], ATTACKS["punch"].push, places=3)
        self.assertAlmostEqual(second[0][1],
                               ATTACKS["kick"].push * (1. + PUSH_GROWTH), places=3)

    def test_scaling_resets_after_the_combo_window(self):
        self.feed({"punch": True}, 5)
        self.feed({}, COMBO_WINDOW + 5)
        again = self.feed({"punch": True}, 5)
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0][0], ATTACKS["punch"].damage)

    def test_supers_ignore_combo_scaling(self):
        self.game.fighters[0]["energy"] = 100
        plus = self.feed({"punch": True}, 5)
        self.assertEqual(plus[0][0], ATTACKS["punch"].damage)
        self.feed({}, 6)
        super_hits = self.feed({"punch": True, "kick": True}) + self.feed({}, 50)
        self.assertEqual(len(super_hits), 1)
        self.assertEqual(super_hits[0][0], ATTACKS["super"].damage)

    def test_scaling_table_is_monotonic_and_positive(self):
        # Every step must lower the payout without ever reaching zero.
        self.assertEqual(list(COMBO_SCALING), sorted(COMBO_SCALING, reverse=True))
        self.assertTrue(all(0 < scale <= 1 for scale in COMBO_SCALING))

    def one_hit(self, combo_index):
        """Land one punch with the attacker already ``combo_index`` hits deep."""
        game = Combat()
        attacker, victim = game.fighters
        attacker["x"], victim["x"] = 400., 470.
        attacker["combo"] = combo_index
        attacker["last_hit_frame"] = game.frame
        for _ in range(6):
            x_before = victim["x"]
            for event in game.step(1 / 60, [{"punch": True}, {}]):
                if event["event"] == "hit":
                    return event["damage"], victim["x"] - x_before
        self.fail("punch never connected")

    def test_scaling_covers_every_combo_index_and_clamps(self):
        # Indexes past the table must keep the lowest multiplier, never hit zero.
        for index in range(len(COMBO_SCALING) + 4):
            scale = COMBO_SCALING[min(index, len(COMBO_SCALING) - 1)]
            damage, _ = self.one_hit(index)
            self.assertEqual(damage, max(1, int(ATTACKS["punch"].damage * scale)),
                             f"combo index {index}")

    def test_pushback_growth_covers_every_index_and_caps_at_double(self):
        for index in range(len(COMBO_SCALING) + 4):
            _, push = self.one_hit(index)
            expected = ATTACKS["punch"].push * (1. + PUSH_GROWTH * min(index, 4))
            self.assertAlmostEqual(push, expected, places=3, msg=f"combo index {index}")

    def ticks_until_punch_lands(self):
        probe = Combat()
        probe.fighters[0]["x"], probe.fighters[1]["x"] = 400., 470.
        for tick in range(1, 12):
            events = probe.step(1 / 60, [{"punch": True}, {}])
            if any(event["event"] == "hit" for event in events):
                return tick
        self.fail("punch never connected")

    def damage_after_gap(self, gap, ticks):
        """Land one punch whose distance from the previous hit is exactly ``gap``."""
        game = Combat()
        attacker, victim = game.fighters
        attacker["x"], victim["x"] = 400., 470.
        attacker["combo"] = 3
        attacker["last_hit_frame"] = game.frame + ticks - gap
        for _ in range(ticks):
            for event in game.step(1 / 60, [{"punch": True}, {}]):
                if event["event"] == "hit":
                    return event["damage"]
        self.fail("punch never connected")

    def test_combo_window_boundary(self):
        ticks = self.ticks_until_punch_lands()
        # One frame inside the window still scales; the boundary frame is fresh.
        self.assertEqual(self.damage_after_gap(COMBO_WINDOW - 1, ticks),
                         int(ATTACKS["punch"].damage * COMBO_SCALING[3]))
        self.assertEqual(self.damage_after_gap(COMBO_WINDOW, ticks),
                         ATTACKS["punch"].damage)

    def test_three_cancelled_hits_keep_the_scaling_curve(self):
        self.game.fighters[0]["x"] = 410.
        landed = []
        for frame in range(90):
            if len(landed) >= 3:
                break
            landed += self.feed({"punch": True} if frame % 3 == 0 else {})
        self.assertGreaterEqual(len(landed), 3)
        self.assertEqual([d for d, _ in landed[:3]],
                         [int(ATTACKS["punch"].damage * scale)
                          for scale in COMBO_SCALING[:3]])

    def test_a_new_attack_inside_the_window_is_still_scaled(self):
        # No cancel: the first jab finishes its full recovery, then a second one
        # connects inside COMBO_WINDOW, so the time-based scaling still applies.
        self.feed({"punch": True}, 5)
        self.feed({}, ATTACKS["punch"].total)
        landed = self.feed({"punch": True}, 5)
        self.assertEqual(len(landed), 1)
        self.assertEqual(landed[0][0], max(1, int(ATTACKS["punch"].damage
                                               * COMBO_SCALING[1])))

    def test_blocked_hits_keep_their_one_fifth_payout(self):
        # Guard damage is flat: combo depth must not shrink it further.
        attacker = self.game.fighters[0]
        attacker["combo"] = 4
        attacker["last_hit_frame"] = self.game.frame
        landed = self.feed({"kick": True}, 12, guard={"guard": True})
        self.assertEqual(len(landed), 1)
        self.assertEqual(landed[0][0], ATTACKS["kick"].damage // 5)

    def test_blocked_hit_ends_the_combo_instead_of_extending_it(self):
        attacker = self.game.fighters[0]
        self.feed({"punch": True}, 5)  # clean hit: the string is at 1
        self.assertEqual(attacker["combo"], 1)
        self.feed({}, 30, guard={"guard": True})  # victim recovers and guards
        self.feed({"punch": True}, 5, guard={"guard": True})
        self.assertEqual(attacker["combo"], 0)
        # The jab has to recover, then the next clean hit still lands inside
        # COMBO_WINDOW but must be treated as a fresh string.
        self.feed({}, 18)
        landed = self.feed({"punch": True}, 5)
        self.assertEqual(len(landed), 1)
        self.assertEqual(landed[0][0], ATTACKS["punch"].damage)

    def test_pushback_stops_at_the_arena_wall(self):
        attacker, victim = self.game.fighters
        attacker["x"], victim["x"] = 885., ARENA_RIGHT - 6
        self.feed({"punch": True}, 5)
        self.assertEqual(victim["x"], ARENA_RIGHT)

    def test_scaled_hit_still_pays_full_meter(self):
        attacker = self.game.fighters[0]
        attacker["combo"] = len(COMBO_SCALING) + 2
        attacker["last_hit_frame"] = self.game.frame
        attacker["energy"] = 0
        landed = self.feed({"punch": True}, 5)
        self.assertEqual(len(landed), 1)
        self.assertEqual(attacker["energy"], HIT_ENERGY_GAIN)

    def test_multi_hit_super_slices_ignore_combo_scaling(self):
        game = Combat()
        game.set_loadout(0, CHARACTERS["blue_headband"])
        game.fighters[0]["x"], game.fighters[1]["x"] = 400., 500.
        game.fighters[0]["energy"] = 100
        game._start_attack(0, "super", [])
        spec = CHARACTERS["blue_headband"]["super"]
        damages = []
        for _ in range(60):
            for event in game.step(1 / 60, [{}, {}]):
                if event["event"] == "hit":
                    damages.append(event["damage"])
        self.assertEqual(damages, [spec.damage // spec.hits] * spec.hits)


class BodySpanTests(unittest.TestCase):
    """Hit-box height must treat crouch_guard the same as crouch."""

    def span(self, action):
        return body_span({"y": 0., "action": action})

    def test_crouch_guard_uses_the_crouched_height(self):
        self.assertEqual(self.span("crouch_guard"), (BODY_BOTTOM, CROUCH_TOP))
        self.assertEqual(self.span("crouch"), (BODY_BOTTOM, CROUCH_TOP))

    def test_standing_and_guard_use_the_full_height(self):
        self.assertEqual(self.span("guard"), (BODY_BOTTOM, BODY_TOP))
        self.assertEqual(self.span("idle"), (BODY_BOTTOM, BODY_TOP))


class GoldenRegressionTests(unittest.TestCase):
    """Deterministic frame-by-frame snapshots of a canonical combo.

    固化黄金轨迹，防止后续数值 / 时序调整在无感知的情况下改变命中判定与伤害。
    """

    def test_punch_then_kick_combo_trajectory(self):
        game = Combat()
        game.fighters[0]["x"] = 400.
        game.fighters[1]["x"] = 485.
        script = [{"punch": True}] * 48 + [{"punch": False}] + [{"kick": True}] * 10
        hp_trace, combo_trace = [], []
        for keys in script:
            game.step(.02, [keys, {}])
            hp_trace.append(game.fighters[1]["hp"])
            combo_trace.append(game.fighters[0]["combo"])
        self.assertEqual(hp_trace, [1000] * 4 + [991] * 51 + [979] * 4)
        self.assertEqual(combo_trace, [0] * 4 + [1] * 51 + [2] * 4)
        self.assertEqual(game.fighters[0]["energy"], 20)


class GrayTieTests(unittest.TestCase):
    """上班的普通人：让开！/ 借过一下 / 晚高峰警告。"""

    def setUp(self):
        self.game = Combat()
        self.game.set_loadout(0, CHARACTERS["gray_tie"])
        self.game.set_loadout(1, CHARACTERS["red_scarf"])
        self.game.fighters[0]["x"] = 400.
        self.game.fighters[1]["x"] = 500.

    def step(self, keys0=None, keys1=None, frames=1):
        for _ in range(frames):
            self.game.step(1 / 60, [keys0 or {}, keys1 or {}])

    def test_character_loads_with_expected_stats(self):
        self.assertEqual(self.game.fighters[0]["hp"], 1100)
        self.assertEqual(self.game.fighters[0]["hp_max"], 1100)
        self.assertEqual(self.game.fighters[0]["move_speed"], 280)
        self.assertEqual(CHARACTERS[self.game.fighters[0]["char_id"]]["decor"], "tie")

    # ---- 晚高峰警告护盾 ----
    def test_shield_command_activates_shield(self):
        self.game.fighters[0]["energy"] = 40
        # S, release, S, release, then L.
        self.step({"down": True})
        self.step({})
        self.step({"down": True})
        self.step({})
        self.step({"guard": True})
        self.assertEqual(self.game.fighters[0]["attack_kind"], "shield_buff")
        self.step({}, frames=20)
        self.assertEqual(self.game.fighters[0]["shield"], 200)
        self.assertEqual(self.game.fighters[0]["shield_max"], 200)
        self.assertEqual(self.game.fighters[0]["energy"], 0)

    def test_shield_absorbs_damage_before_hp(self):
        f = self.game.fighters[0]
        f["shield"] = 200
        f["shield_max"] = 200
        hp_before = f["hp"]
        # 一发 9 伤害的拳头先打护盾。
        self.step({}, {"punch": True}, frames=12)
        self.assertEqual(f["hp"], hp_before)
        self.assertEqual(f["shield"], 200 - 9)

    def test_shield_overflow_only_damages_hp(self):
        f = self.game.fighters[0]
        f["shield"] = 5
        f["shield_max"] = 200
        hp_before = f["hp"]
        self.step({}, {"punch": True}, frames=12)
        # 9 伤害：护盾吸 5，溢出 4 扣血。
        self.assertEqual(f["shield"], 0)
        self.assertEqual(f["hp"], hp_before - 4)

    def test_shield_expires_after_seven_seconds(self):
        f = self.game.fighters[0]
        f["shield"] = 200
        f["shield_max"] = 200
        f["shield_timer"] = 7.0
        # 跑 7 秒（420 帧），护盾应到点消散。
        self.step({}, frames=420)
        self.assertEqual(f["shield"], 0)
        self.assertEqual(f["shield_timer"], 0.)

    # ---- 借过一下霸体冲锋 ----
    def _tackle_command(self):
        # S, release, S, release, toward, release, then I.
        self.step({"down": True})
        self.step({})
        self.step({"down": True})
        self.step({})
        self.step({"right": True})
        self.step({})
        self.step({"grab": True})

    def test_tackle_command_starts_super(self):
        self.game.fighters[0]["energy"] = 100
        self._tackle_command()
        self.assertEqual(self.game.fighters[0]["attack_kind"], "tackle")
        self.assertEqual(self.game.fighters[0]["energy"], 0)

    def test_tackle_deals_150_in_two_hits(self):
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[1]["x"] = 460.  # 近距保证命中
        self._tackle_command()
        for _ in range(120):
            self.game.step(1 / 60, [{}, {}])
            if self.game.fighters[1]["knocked"]:
                break
        # 撞击 40 + 摔地 110 = 150。
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - 150)
        self.assertTrue(self.game.fighters[1]["knocked"])

    def test_tackle_victim_stays_down_two_seconds(self):
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[1]["x"] = 460.
        self._tackle_command()
        for _ in range(120):
            self.game.step(1 / 60, [{}, {}])
            if self.game.fighters[1]["knocked"]:
                break
        self.assertGreaterEqual(self.game.fighters[1]["stun"], 2. - 1 / 60)

    def test_tackle_caster_recovers_not_knocked(self):
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[1]["x"] = 460.
        self._tackle_command()
        for _ in range(90):
            self.game.step(1 / 60, [{}, {}])
        # 施放者自己没有被判定为倒地（立即起身）。
        self.assertFalse(self.game.fighters[0]["knocked"])

    def test_tackle_rush_has_armor(self):
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[1]["x"] = 700.  # 超出射程，让冲锋完整跑完
        self._tackle_command()
        # 冲到第 15 帧左右仍处于 rush 霸体阶段。
        for _ in range(15):
            self.game.step(1 / 60, [{}, {"punch": True}])
        self.assertTrue(self.game.fighters[0].get("super_armor"))
        # 霸体期间被打不进受击硬直、不被打断出招。
        self.assertEqual(self.game.fighters[0]["attack_kind"], "tackle")

    # ---- 让开！推人波 ----
    def test_carrier_projectile_does_not_disappear_on_hit(self):
        self.game.fighters[1]["x"] = 500.
        self.step({"projectile": True})
        self.step({}, frames=12)
        self.assertEqual(len(self.game.projectiles), 1)
        self.assertEqual(self.game.projectiles[0]["style"], "carrier")
        hit_frame = None
        survived_after_hit = 0
        for f in range(120):
            self.game.step(1 / 60, [{}, {}])
            if hit_frame is None and self.game.fighters[1]["hp"] < 1000:
                hit_frame = f
            if hit_frame is not None and self.game.projectiles:
                survived_after_hit += 1
        self.assertIsNotNone(hit_frame)
        # 普通弹道命中即消失；推人波命中后还能存活多帧。
        self.assertGreater(survived_after_hit, 1)

    def test_carrier_projectile_pushes_enemy(self):
        self.game.fighters[1]["x"] = 500.
        self.step({"projectile": True})
        self.step({}, frames=12)
        x_before = self.game.fighters[1]["x"]
        for _ in range(80):
            self.game.step(1 / 60, [{}, {}])
        # 被推着远离施法者。
        self.assertGreater(self.game.fighters[1]["x"], x_before)


class DownedPoseTests(unittest.TestCase):
    """败者倒地姿势选择与 match_end 胜者自由行动。"""

    def setUp(self):
        self.game = Combat()

    # --- _downed_style_for 姿势映射 ---

    def test_low_attacks_map_to_prone(self):
        for kind in ("crouch_punch", "low_kick", "crouch_projectile"):
            self.assertEqual(Combat._downed_style_for(kind), "prone", kind)

    def test_big_hits_map_to_flat(self):
        for kind in ("super", "grab", "tackle", "projectile"):
            self.assertEqual(Combat._downed_style_for(kind), "flat", kind)

    def test_normals_map_to_curl(self):
        for kind in ("punch", "kick", "jump_punch", ""):
            self.assertEqual(Combat._downed_style_for(kind), "curl", kind)

    # --- finish_round 败者必须倒地 ---

    def test_finish_round_knocks_loser_down_with_pose(self):
        self.game.last_hit_kind = "low_kick"
        self.game.finish_round(0)
        loser = self.game.fighters[1]
        self.assertTrue(loser["knocked"])
        self.assertEqual(loser["downed_style"], "prone")
        winner = self.game.fighters[0]
        self.assertFalse(winner["knocked"])

    def test_finish_round_super_finisher_uses_flat(self):
        self.game.last_hit_kind = "super"
        self.game.finish_round(1)
        self.assertEqual(self.game.fighters[0]["downed_style"], "flat")
        self.assertTrue(self.game.fighters[0]["knocked"])

    def test_finish_round_draw_knocks_both_down(self):
        self.game.last_hit_kind = "punch"
        self.game.finish_round(None)
        self.assertTrue(self.game.fighters[0]["knocked"])
        self.assertTrue(self.game.fighters[1]["knocked"])

    def test_finish_round_does_not_reknock_already_down_fighter(self):
        # 若败者已因 stagger 倒地，姿势不应被覆盖。
        self.game.last_hit_kind = "low_kick"
        self.game.fighters[1]["knocked"] = True
        self.game.fighters[1]["downed_style"] = "curl"
        self.game.finish_round(0)
        self.assertEqual(self.game.fighters[1]["downed_style"], "curl")

    # --- match_end 胜者自由行动 / 败者冻结 ---

    def _set_match_end(self, winner=0, hit_kind="punch"):
        self.game.scores = [1, 0] if winner == 0 else [0, 1]
        self.game.last_hit_kind = hit_kind
        self.game.finish_round(winner)
        self.assertEqual(self.game.phase, "match_end")

    def test_match_end_winner_can_move(self):
        self._set_match_end(0)
        x_before = self.game.fighters[0]["x"]
        self.game.step(1 / 60, [{"right": True}, {}])
        self.assertGreater(self.game.fighters[0]["x"], x_before)

    def test_match_end_loser_stays_frozen(self):
        self._set_match_end(0)
        loser_x = self.game.fighters[1]["x"]
        for _ in range(30):
            self.game.step(1 / 60, [{"right": True}, {"left": True, "punch": True}])
        self.assertEqual(self.game.fighters[1]["x"], loser_x)
        self.assertTrue(self.game.fighters[1]["knocked"])
        self.assertEqual(self.game.fighters[1]["action"], "downed")

    def test_match_end_winner_can_whiff_attacks(self):
        self._set_match_end(0)
        self.game.step(1 / 60, [{"punch": True}, {}])
        self.assertEqual(self.game.fighters[0]["action"], "punch")
        # 松开按键，动画自然结束回到 idle。
        for _ in range(30):
            self.game.step(1 / 60, [{}, {}])
        self.assertEqual(self.game.fighters[0]["action"], "idle")

    def test_match_end_loser_takes_no_damage(self):
        self._set_match_end(0)
        hp_before = self.game.fighters[1]["hp"]
        for _ in range(60):
            self.game.step(1 / 60, [{"punch": True}, {}])
        self.assertEqual(self.game.fighters[1]["hp"], hp_before)

    def test_match_end_blocks_super_and_buff_actions(self):
        self._set_match_end(0)
        self.game.fighters[0]["energy"] = MAX_ENERGY
        for _ in range(20):
            self.game.step(1 / 60, [{"punch": True, "kick": True}, {}])
        self.assertNotIn(self.game.fighters[0]["action"],
                         ("super", "flame_buff", "lightning_strike",
                          "ice_shadow", "tackle", "shield_buff"))

    def test_round_end_does_not_allow_freeroam(self):
        # 单局结束（未到赛点）时双方冻结，不触发自由行动。
        self.game.scores = [0, 0]
        self.game.last_hit_kind = "punch"
        self.game.finish_round(0)
        self.assertEqual(self.game.phase, "round_end")
        x_before = self.game.fighters[0]["x"]
        self.game.step(1 / 60, [{"right": True}, {}])
        self.assertEqual(self.game.fighters[0]["x"], x_before)

    # --- 胜者自由行动边界用例 ---

    def test_winner_movement_clamped_to_arena_bounds(self):
        self._set_match_end(0)
        # 一直向左推，不应越过左边界。
        for _ in range(200):
            self.game.step(1 / 60, [{"left": True}, {}])
        self.assertGreaterEqual(self.game.fighters[0]["x"], ARENA_LEFT)
        # 一直向右推，不应越过右边界。
        for _ in range(200):
            self.game.step(1 / 60, [{"right": True}, {}])
        self.assertLessEqual(self.game.fighters[0]["x"], ARENA_RIGHT)

    def test_winner_jump_arc_and_landing(self):
        self._set_match_end(0)
        self.game.step(1 / 60, [{"jump": True}, {}])
        self.assertGreater(self.game.fighters[0]["y"], 0)
        self.assertFalse(self.game.fighters[0]["grounded"])
        # 落地后 grounded 恢复，vy 清零。
        for _ in range(120):
            self.game.step(1 / 60, [{}, {}])
            if self.game.fighters[0]["y"] <= 0:
                break
        self.assertEqual(self.game.fighters[0]["y"], 0.)
        self.assertTrue(self.game.fighters[0]["grounded"])

    def test_winner_attack_cooldown_gates_repeat(self):
        self._set_match_end(0)
        self.game.step(1 / 60, [{"punch": True}, {}])
        self.assertEqual(self.game.fighters[0]["attack_kind"], "punch")
        af = self.game.fighters[0]["action_frame"]
        # 连按不会在动画中途重启动画。
        for _ in range(10):
            self.game.step(1 / 60, [{"punch": True}, {}])
        self.assertGreater(self.game.fighters[0]["action_frame"], af)

    def test_winner_facing_follows_movement(self):
        self._set_match_end(0)
        self.game.step(1 / 60, [{"right": True}, {}])
        self.assertEqual(self.game.fighters[0]["face"], 1)
        self.game.step(1 / 60, [{"left": True}, {}])
        self.assertEqual(self.game.fighters[0]["face"], -1)

    def test_loser_cannot_get_up_via_input(self):
        # 败者即使收到输入也起不来——match_end 阶段忽略败者输入。
        self._set_match_end(0)
        for _ in range(60):
            self.game.step(1 / 60, [{}, {"right": True, "punch": True, "jump": True}])
        self.assertTrue(self.game.fighters[1]["knocked"])
        self.assertEqual(self.game.fighters[1]["action"], "downed")
        self.assertEqual(self.game.fighters[1]["y"], 0.)

    def test_winner_projectile_is_harmless(self):
        # 展示阶段允许发射远程，但不命中、不扣败者血。
        self._set_match_end(0)
        self.game.fighters[0]["energy"] = MAX_ENERGY
        hp_before = self.game.fighters[1]["hp"]
        for _ in range(120):
            self.game.step(1 / 60, [{"projectile": True}, {}])
        self.assertEqual(self.game.fighters[1]["hp"], hp_before)

    def test_winner_energy_unchanged_on_normal_attacks(self):
        self._set_match_end(0)
        self.game.fighters[0]["energy"] = MAX_ENERGY
        for _ in range(60):
            self.game.step(1 / 60, [{"punch": True, "kick": True}, {}])
        self.assertEqual(self.game.fighters[0]["energy"], MAX_ENERGY)

    def test_winner_can_crouch_in_freeroam(self):
        self._set_match_end(0)
        self.game.step(1 / 60, [{"down": True}, {}])
        self.assertEqual(self.game.fighters[0]["action"], "crouch")

    def test_match_end_freeroam_with_winner_slot_one(self):
        # 胜者是 P2 时同样可以自由行动，败者（P1）冻结。
        self._set_match_end(1)
        x_before = self.game.fighters[1]["x"]
        self.game.step(1 / 60, [{}, {"left": True}])
        self.assertLess(self.game.fighters[1]["x"], x_before)
        self.assertTrue(self.game.fighters[0]["knocked"])
        self.assertEqual(self.game.fighters[0]["action"], "downed")

    def test_loser_action_frame_keeps_advancing(self):
        # 败者虽然冻结，但动画帧仍推进（供渲染层播放倒地静止/微动）。
        self._set_match_end(0)
        af0 = self.game.fighters[1]["action_frame"]
        for _ in range(10):
            self.game.step(1 / 60, [{}, {}])
        self.assertGreater(self.game.fighters[1]["action_frame"], af0)


class TrainingModeTests(unittest.TestCase):
    """技能训练模式：hp 归零即重生，不结算回合、不改变比分。"""

    def setUp(self):
        self.game = Combat()
        self.game.training_mode = True
        # 把 dummy 移到近处，确保 punch 能命中。
        self.game.fighters[1]["x"] = 260.
        self.game.fighters[0]["face"] = 1

    def test_dummy_respawns_at_initial_position(self):
        self.game.fighters[1]["hp"] = 1
        self.game.step(1 / 60, [{"punch": True}, {}])
        for _ in range(40):
            self.game.step(1 / 60, [{}, {}])
        dummy = self.game.fighters[1]
        self.assertEqual(dummy["hp"], dummy["hp_max"])
        self.assertEqual(dummy["x"], 810.)
        self.assertEqual(dummy["y"], 0.)
        self.assertFalse(dummy["knocked"])

    def test_training_does_not_change_scores(self):
        self.game.fighters[1]["hp"] = 1
        self.game.step(1 / 60, [{"punch": True}, {}])
        for _ in range(40):
            self.game.step(1 / 60, [{}, {}])
        self.assertEqual(self.game.scores, [0, 0])

    def test_training_phase_stays_game(self):
        self.game.fighters[1]["hp"] = 1
        self.game.step(1 / 60, [{"punch": True}, {}])
        for _ in range(40):
            self.game.step(1 / 60, [{}, {}])
        self.assertEqual(self.game.phase, "game")

    def test_training_does_not_fire_round_end_event(self):
        self.game.fighters[1]["hp"] = 1
        events = []
        for _ in range(40):
            events += self.game.step(1 / 60, [{"punch": True}, {}])
        self.assertFalse(any(e["event"] == "round_end" for e in events))
        self.assertTrue(any(e["event"] == "training_respawn" for e in events))

    def test_respawn_clears_attack_and_stagger_state(self):
        self.game.fighters[1]["hp"] = 1
        self.game.fighters[1]["stagger"] = 200
        self.game.step(1 / 60, [{"punch": True}, {}])
        for _ in range(40):
            self.game.step(1 / 60, [{}, {}])
        dummy = self.game.fighters[1]
        self.assertEqual(dummy["stagger"], 0.)
        self.assertEqual(dummy["attack_kind"], "")
        self.assertEqual(dummy["stun"], 0.)

    def test_non_training_mode_still_finishes_round(self):
        self.game.training_mode = False
        self.game.fighters[1]["x"] = 260.
        self.game.fighters[1]["hp"] = 1
        self.game.step(1 / 60, [{"punch": True}, {}])
        for _ in range(40):
            self.game.step(1 / 60, [{}, {}])
        self.assertNotEqual(self.game.phase, "game")
        self.assertEqual(self.game.scores, [1, 0])


class DioTimeStopTests(unittest.TestCase):
    """Dio's 砸瓦鲁多: S S + L L freezes everyone but the caster for 7 seconds."""

    def setUp(self):
        self.game = Combat()
        self.game.set_loadout(0, CHARACTERS["dio"])
        self.game.set_loadout(1, CHARACTERS["red_scarf"])
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[0]["x"] = 330.
        self.game.fighters[1]["x"] = 620.

    def feed(self, own, cpu=None):
        return self.game.step(1 / 60, [own, cpu or {}])

    def command(self):
        for keys in ({"down": True}, {}, {"down": True}, {}, {"guard": True}, {},
                     {"guard": True}):
            self.feed(keys)

    def cast(self):
        self.command()
        self.assertEqual(self.game.fighters[0]["attack_kind"], "super")
        for _ in range(60):
            self.feed({})
            if self.game.time_stop > 0:
                return
        self.fail("time stop never began")

    def test_ssll_command_starts_the_super(self):
        self.command()
        self.assertEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 0)

    def test_ssll_needs_full_energy(self):
        self.game.fighters[0]["energy"] = 99
        self.command()
        self.assertNotEqual(self.game.fighters[0]["attack_kind"], "super")
        self.assertEqual(self.game.fighters[0]["energy"], 99)

    def test_zero_frame_startup_time_stops_immediately(self):
        self.command()
        self.assertEqual(self.game.fighters[0]["action"], "super")
        self.assertEqual(self.game.time_stop, 0.)
        # 零帧起手：只走一帧就进入时停，没有 40 帧前摇。
        self.feed({})
        self.assertGreater(self.game.time_stop, 0.)
        self.assertEqual(self.game.time_stop_owner, 0)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "")

    def test_shout_event_fires_on_super_start(self):
        # 音效从时停生效提前到起手：起手帧发 time_stop_cast，生效时才发 time_stop。
        events = []
        for keys in ({"down": True}, {}, {"down": True}, {}, {"guard": True}, {},
                     {"guard": True}):
            events += self.feed(keys)
        casts = [e for e in events if e["event"] == "time_stop_cast"]
        self.assertEqual(len(casts), 1, casts)
        self.assertEqual(self.game.time_stop, 0., "起手帧还不应进入时停")
        for _ in range(44):
            events += self.feed({})
        self.assertGreater(self.game.time_stop, 0.)
        self.assertEqual([e for e in events if e["event"] == "time_stop_cast"],
                         casts, "时停生效后不应重复发起手事件")

    def test_zero_startup_cannot_be_interrupted(self):
        # 零帧起手后没有前摇可打：对手的拳来不及落下，时停照常生效，
        # 也不会补发取消喊招音效的事件。
        self.game.fighters[1]["x"] = 400.
        events = []
        for keys in ({"down": True}, {}, {"down": True}, {}, {"guard": True}, {},
                     {"guard": True}):
            events += self.feed(keys)
        self.assertEqual(self.game.fighters[0]["attack_kind"], "super")
        for _ in range(12):
            events += self.feed({}, {"punch": True})
        self.assertGreater(self.game.time_stop, 0.)
        self.assertEqual(self.game.time_stop_owner, 0)
        self.assertFalse([e for e in events if e["event"] == "time_stop_cancel"])

    def test_clock_and_the_opponent_freeze(self):
        self.cast()
        clock = self.game.time_left
        foe = self.game.fighters[1]
        af, kind, x = foe["action_frame"], foe["attack_kind"], foe["x"]
        for _ in range(120):
            self.feed({"right": True})
        self.assertEqual(self.game.time_left, clock)
        self.assertEqual(foe["action_frame"], af)
        self.assertEqual(foe["attack_kind"], kind)
        self.assertEqual(foe["x"], x)

    def test_caster_moves_at_double_speed(self):
        self.cast()
        x0 = self.game.fighters[0]["x"]
        for _ in range(15):
            self.feed({"right": True})
        speed = (self.game.fighters[0]["x"] - x0) / .25
        self.assertAlmostEqual(speed, 600., delta=30.)

    def test_punch_deals_damage_without_energy_gain(self):
        self.cast()
        self.game.fighters[1]["x"] = self.game.fighters[0]["x"] + 60.
        hp0 = self.game.fighters[1]["hp"]
        energy0 = self.game.fighters[0]["energy"]
        self.feed({"punch": True})
        self.assertEqual(self.game.fighters[1]["hp"], hp0 - 8)
        self.assertEqual(self.game.fighters[0]["energy"], energy0)
        # 时停里不结算硬直，受击方也不会被打断定格。
        self.assertEqual(self.game.fighters[1]["stagger"], 0.)
        # 出拳有动画（纯视觉、不进攻击状态机），且不占用 attack_kind。
        self.assertEqual(self.game.fighters[0]["action"], "punch")
        self.assertEqual(self.game.fighters[0]["attack_kind"], "")

    def test_repeated_punches_restart_the_animation(self):
        self.cast()
        self.game.fighters[1]["x"] = self.game.fighters[0]["x"] + 60.
        self.feed({"punch": True})
        first = self.game.fighters[0]["time_punch_anim"]
        self.assertGreater(first, 0)
        # 第一拳由前手打出。
        self.assertEqual(self.game.fighters[0]["time_punch_side"], 0)
        for _ in range(4):
            self.feed({})
        self.feed({"punch": True})
        self.assertGreater(self.game.fighters[0]["time_punch_anim"], 0)
        # 第二拳换后手：连按时前后手交替出拳。
        self.assertEqual(self.game.fighters[0]["time_punch_side"], 1)
        # 手速不设限：动画不会把 free / cooldown 卡住。
        self.assertEqual(self.game.fighters[0]["cooldown"], 0.)

    def test_time_stop_expires_after_seven_seconds(self):
        self.cast()
        events = []
        for _ in range(60 * 8):
            events += self.feed({})
        self.assertEqual(self.game.time_stop, 0.)
        self.assertEqual(self.game.time_stop_owner, -1)
        self.assertTrue(any(e["event"] == "time_resume" for e in events))

    def test_ko_ends_time_stop_and_wins_the_round(self):
        self.cast()
        self.game.fighters[1]["x"] = self.game.fighters[0]["x"] + 60.
        self.game.fighters[1]["hp"] = 4
        events = self.feed({"punch": True})
        self.assertEqual(self.game.fighters[1]["hp"], 0)
        self.assertEqual(self.game.time_stop, 0.)
        self.assertNotEqual(self.game.phase, "game")
        self.assertEqual(self.game.scores, [1, 0])
        self.assertTrue(any(e["event"] == "time_resume" for e in events))


class DioVaporFreezeTests(unittest.TestCase):
    """气化冷冻法：A/D + L L 向前射出冰束，命中冻结 1.5 秒，冻结中挨打会碎冰。"""

    def setUp(self):
        self.game = Combat()
        self.game.set_loadout(0, CHARACTERS["dio"])
        self.game.set_loadout(1, CHARACTERS["red_scarf"])
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[0]["x"] = 330.
        # 冰束射程约 378 像素（900 × 0.42），60 像素轻松命中。
        self.game.fighters[1]["x"] = 390.

    def feed(self, own, cpu=None):
        return self.game.step(1 / 60, [own, cpu or {}])

    def command(self):
        events = []
        for keys in ({"right": True}, {}, {"guard": True}, {}, {"guard": True}):
            events += self.feed(keys)
        return events

    def cast(self, cpu=None):
        """搓 A/D + L L 并推进到冰束命中为止。"""
        events = []
        for keys in ({"right": True}, {}, {"guard": True}, {},
                     {"guard": True}):
            events += self.feed(keys, cpu)
        for _ in range(40):
            events += self.feed({}, cpu)
            if [e for e in events if e["event"] == "hit"
                    and e.get("attack") == "ice_beam"]:
                break
        return events

    def settle(self, frames=24):
        for _ in range(frames):
            self.feed({})

    def landed(self, events):
        return [e for e in events if e["event"] == "hit"
                and e.get("attack") == "ice_beam"]

    def test_combo_costs_energy_and_freezes(self):
        events = self.cast()
        self.assertEqual(len(self.landed(events)), 1, events)
        # 100 - 30 能耗 + 15 命中返还（一半能耗）= 85。
        self.assertEqual(self.game.fighters[0]["energy"], 85)
        # 冻伤 12 点，并进入 1.5 秒冻结（命中这一帧已经走掉了 1 帧）。
        self.assertEqual(self.game.fighters[1]["hp"], 988)
        self.assertGreater(self.game.fighters[1]["frozen"], 1.4)
        self.assertEqual(self.game.fighters[1]["frozen_kind"], "vapor")

    def test_beam_is_fired_as_a_projectile(self):
        # 冰束是飞行道具：起手帧之后场上会出现一段 ice_beam。
        self.game.fighters[1]["x"] = 620.
        events = self.command()
        for _ in range(20):
            events += self.feed({})
            if [p for p in self.game.projectiles if p.get("attack") == "ice_beam"]:
                break
        beams = [p for p in self.game.projectiles if p.get("attack") == "ice_beam"]
        self.assertTrue(beams, events)
        self.assertEqual(beams[0]["style"], "beam")

    def test_combo_fires_once_per_input(self):
        # double_press 会在双按后的几帧内一直为真，不能按住 L 连发。
        self.cast()
        self.settle(40)
        self.assertEqual(self.game.fighters[1]["hp"], 988)

    def test_frozen_opponent_cannot_move(self):
        self.cast()
        for _ in range(20):
            self.feed({}, {"left": True})
        self.assertAlmostEqual(self.game.fighters[1]["x"], 390., places=2)

    def test_freeze_lasts_one_and_a_half_seconds(self):
        self.cast()
        for _ in range(96):
            self.feed({})
        self.assertEqual(self.game.fighters[1]["frozen"], 0.)

    def test_first_hit_shatters_the_ice_for_bonus_damage(self):
        self.cast()
        self.settle(24)
        events = []
        for i in range(34):
            events += self.feed({"punch": True} if i < 3 else {})
        # 普通拳 9 + 碎裂 30 = 39。
        self.assertEqual(self.game.fighters[1]["hp"], 988 - 39)
        self.assertEqual(self.game.fighters[1]["frozen"], 0.)
        self.assertTrue([e for e in events if e["event"] == "vapor_shatter"])

    def test_beam_falls_short_at_max_range(self):
        # 冰束飞行 375 像素（900 × 0.42），从身前 62 像素处射出，加上身体宽度，
        # 实际起手距离约 480 像素；站在 830 处就够不着了。
        self.game.fighters[1]["x"] = 830.
        events = self.cast()
        self.assertEqual(self.landed(events), [])
        self.assertEqual(self.game.fighters[1]["hp"], 1000)
        self.assertEqual(self.game.fighters[1]["frozen"], 0.)
        # 打空不返还能量：30 点照扣。
        self.assertEqual(self.game.fighters[0]["energy"], 70)

    def test_hit_refunds_only_half_the_cost(self):
        # 命中返还一半能耗：85 点，离大招还差 15 点。
        self.cast()
        self.assertEqual(self.game.fighters[0]["energy"], 85)
        for keys in ({"down": True}, {}, {"down": True}, {}, {"guard": True}, {},
                     {"guard": True}, {}):
            self.feed(keys)
        self.assertEqual(self.game.time_stop, 0.)

    def test_cannot_refreeze_an_already_frozen_opponent(self):
        # 已经冻住的对手不会被续冻，否则冰束可以把冻结一直续下去。
        first = self.cast()
        self.assertEqual(len(self.landed(first)), 1)
        self.settle(24)
        second = self.cast()
        self.assertEqual(len(self.landed(second)), 1)
        self.assertLessEqual(self.game.fighters[1]["frozen"], 1.5)

    def test_standing_guard_blocks_the_beam(self):
        # 冰束是投射物：站着防御能挡下，只吃 1/5 擦伤，也不会被冻住。
        events = self.cast(cpu={"guard": True})
        self.assertEqual(len(self.landed(events)), 1, events)
        self.assertEqual(self.game.fighters[1]["frozen"], 0.)
        self.assertEqual(self.game.fighters[1]["hp"], 1000 - max(1, 12 // 5))

    def test_crouching_ducks_under_the_beam(self):
        # 冰束走胸口高度，蹲下可以从下方让过去。
        events = self.cast(cpu={"down": True})
        self.assertEqual(self.landed(events), [])
        self.assertEqual(self.game.fighters[1]["frozen"], 0.)

    def test_combo_needs_thirty_energy(self):
        # 能量不足 30 时连招不成立，也不会扣能量。
        self.game.fighters[0]["energy"] = 29
        events = self.command()
        self.assertNotEqual(self.game.fighters[0]["attack_kind"], "vapor_freeze")
        self.assertFalse([e for e in events if e["event"] == "vapor_freeze"])
        self.assertEqual(self.game.fighters[0]["energy"], 29)


class DioKnifeAndRollerTests(unittest.TestCase):
    """时停飞刀齐射（U）与 ROAD ROLLER DA!! 终结（K）。"""

    def setUp(self):
        self.game = Combat()
        self.game.set_loadout(0, CHARACTERS["dio"])
        self.game.set_loadout(1, CHARACTERS["red_scarf"])
        self.game.fighters[0]["energy"] = 100
        self.game.fighters[0]["x"] = 330.
        self.game.fighters[1]["x"] = 620.

    def feed(self, own, cpu=None):
        return self.game.step(1 / 60, [own, cpu or {}])

    def command(self):
        for keys in ({"down": True}, {}, {"down": True}, {}, {"guard": True}, {},
                     {"guard": True}):
            self.feed(keys)

    def cast(self):
        self.command()
        for _ in range(60):
            self.feed({})
            if self.game.time_stop > 0:
                return
        self.fail("time stop never began")

    def knives(self):
        return [p for p in self.game.projectiles if p.get("knife")]

    def throw_knife(self):
        # 掏刀只认按下沿，所以必须松开再按。
        events = self.feed({"projectile": True})
        self.feed({})
        return events

    def test_knife_hangs_frozen_in_the_air(self):
        self.cast()
        events = self.throw_knife()
        knives = self.knives()
        self.assertEqual(len(knives), 1)
        self.assertTrue(knives[0]["frozen"])
        self.assertEqual(knives[0]["vx"], 0.)
        self.assertEqual(self.game.fighters[1]["hp"], 1000, "悬停的刀不结算伤害")
        self.assertTrue(any(e["event"] == "knife_throw" for e in events))
        x, y = knives[0]["x"], knives[0]["y"]
        for _ in range(30):
            self.feed({})
        self.assertEqual(self.knives()[0]["x"], x, "时停中飞刀绝不能移动")
        self.assertEqual(self.knives()[0]["y"], y)

    def test_knife_has_a_cooldown(self):
        self.cast()
        self.feed({"projectile": True})
        self.assertEqual(len(self.knives()), 1)
        # 按住不放只会掏出一把：没有新的按下沿。
        for _ in range(12):
            self.feed({"projectile": True})
        self.assertEqual(len(self.knives()), 1)
        # 冷却结束后松开再按，可以掏出第二把。
        self.feed({})
        for _ in range(3):
            self.feed({"projectile": True})
        self.assertEqual(len(self.knives()), 2)

    def test_knife_count_is_capped(self):
        self.cast()
        for _ in range(KNIFE_MAX + 4):
            self.feed({"projectile": True})
            for _ in range(14):
                self.feed({})
        self.assertEqual(len(self.knives()), KNIFE_MAX)

    def test_knives_launch_when_time_resumes(self):
        self.cast()
        self.feed({"projectile": True})
        self.feed({})
        self.game.time_stop = .01
        events = []
        for _ in range(4):
            events += self.feed({})
        knives = self.knives()
        self.assertTrue(knives)
        self.assertFalse(knives[0]["frozen"])
        self.assertNotEqual(knives[0]["vx"], 0.)
        self.assertTrue(any(e["event"] == "knife_rush" for e in events))

    def test_launched_knife_damages_the_opponent(self):
        self.cast()
        self.game.fighters[1]["x"] = self.game.fighters[0]["x"] + 160.
        self.feed({"projectile": True})
        self.feed({})
        self.game.time_stop = .01
        hp0 = self.game.fighters[1]["hp"]
        for _ in range(40):
            self.feed({})
        self.assertEqual(self.game.fighters[1]["hp"], hp0 - KNIFE_DAMAGE)

    def test_crouching_cannot_dodge_the_knife(self):
        # 飞刀不是普通发波：蹲下没有豁免，低位的刀照样命中。
        self.cast()
        foe = self.game.fighters[1]
        foe["x"] = self.game.fighters[0]["x"] + 120.
        self.feed({"projectile": True})
        self.feed({})
        self.game.time_stop = .01
        hp0 = foe["hp"]
        for _ in range(30):
            self.feed({}, {"down": True})
        self.assertLess(foe["hp"], hp0)

    def test_standing_guard_blocks_the_knife(self):
        self.cast()
        foe = self.game.fighters[1]
        foe["x"] = self.game.fighters[0]["x"] + 120.
        self.feed({"projectile": True})
        self.feed({})
        self.game.time_stop = .01
        hp0 = foe["hp"]
        for _ in range(30):
            self.feed({}, {"guard": True})
        # 格挡只吃擦伤（伤害 // 5）。
        self.assertEqual(foe["hp"], hp0 - KNIFE_DAMAGE // 5)

    def five_punches(self):
        self.cast()
        self.game.fighters[1]["x"] = self.game.fighters[0]["x"] + 60.
        for _ in range(ROLLER_REQUIRED_HITS):
            self.feed({"punch": True})
            self.feed({})

    def test_road_roller_needs_five_hits(self):
        self.cast()
        foe = self.game.fighters[1]
        foe["x"] = self.game.fighters[0]["x"] + 60.
        for _ in range(3):
            self.feed({"punch": True})
            self.feed({})
        self.assertEqual(self.game.fighters[0]["time_punch_count"], 3)
        self.feed({"kick": True})
        self.assertGreater(self.game.time_stop, 0., "不足 5 拳不应触发压路机")
        self.assertEqual(foe["hp"], 1000 - 3 * 8)

    def test_road_roller_ends_time_stop_and_knocks_down(self):
        self.five_punches()
        foe = self.game.fighters[1]
        hp0 = foe["hp"]
        events = self.feed({"kick": True})
        self.assertEqual(self.game.time_stop, 0.)
        self.assertEqual(foe["hp"], hp0 - ROLLER_DAMAGE)
        self.assertTrue(foe["knocked"])
        self.assertTrue(any(e["event"] == "road_roller" for e in events))
        self.assertTrue(any(e["event"] == "time_resume" for e in events))

    def test_road_roller_ko_wins_the_round(self):
        self.five_punches()
        foe = self.game.fighters[1]
        foe["hp"] = 30
        self.feed({"kick": True})
        self.assertEqual(foe["hp"], 0)
        self.assertNotEqual(self.game.phase, "game")
        self.assertEqual(self.game.scores, [1, 0])

    def test_shoulder_check_does_not_trigger_roller(self):
        # 时停中没打满 5 拳时，K 既不触发压路机也不应有伤害。
        self.cast()
        foe = self.game.fighters[1]
        foe["x"] = self.game.fighters[0]["x"] + 60.
        hp0 = foe["hp"]
        events = self.feed({"kick": True})
        self.assertFalse([e for e in events if e["event"] == "road_roller"])
        self.assertEqual(foe["hp"], hp0)
        self.assertGreater(self.game.time_stop, 0.)


if __name__ == "__main__":
    unittest.main()
