"""手柄翻译层：SDL2 手柄状态 → 战斗核心的九键输入 / 菜单导航。"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame

from fighter.gamepad import (DEADZONE, KEYS, Gamepad, map_menu, map_state,
                             merge_state)

A = pygame.CONTROLLER_BUTTON_A
B = pygame.CONTROLLER_BUTTON_B
X = pygame.CONTROLLER_BUTTON_X
Y = pygame.CONTROLLER_BUTTON_Y
LB = pygame.CONTROLLER_BUTTON_LEFTSHOULDER
RB = pygame.CONTROLLER_BUTTON_RIGHTSHOULDER
START = pygame.CONTROLLER_BUTTON_START
DPAD_UP = pygame.CONTROLLER_BUTTON_DPAD_UP
DPAD_DOWN = pygame.CONTROLLER_BUTTON_DPAD_DOWN
DPAD_LEFT = pygame.CONTROLLER_BUTTON_DPAD_LEFT
DPAD_RIGHT = pygame.CONTROLLER_BUTTON_DPAD_RIGHT


class TranslateTests(unittest.TestCase):
    def test_idle_pad_is_all_released(self):
        state = map_state((0., 0., 0.), frozenset())
        self.assertEqual(set(state), set(KEYS))
        self.assertFalse(any(state.values()))

    def test_left_stick_outside_deadzone_moves_and_jumps(self):
        self.assertTrue(map_state((-0.8, 0., 0.), frozenset())["left"])
        self.assertTrue(map_state((0.8, 0., 0.), frozenset())["right"])
        # SDL 左摇杆向上为负值：向上 = 跳跃，向下 = 下蹲
        self.assertTrue(map_state((0., -0.8, 0.), frozenset())["jump"])
        self.assertTrue(map_state((0., 0.8, 0.), frozenset())["down"])

    def test_stick_inside_deadzone_does_not_trigger(self):
        state = map_state((DEADZONE - .01, DEADZONE - .01, 0.), frozenset())
        self.assertFalse(state["left"] or state["right"] or state["jump"] or state["down"])

    def test_face_buttons_and_shoulders(self):
        state = map_state((0., 0., 0.), frozenset({X, Y, B, RB, LB}))
        self.assertTrue(state["punch"] and state["kick"] and state["projectile"])
        self.assertTrue(state["grab"] and state["guard"])

    def test_a_button_jumps_and_right_trigger_guards(self):
        self.assertTrue(map_state((0., 0., 0.), frozenset({A}))["jump"])
        self.assertTrue(map_state((0., 0., .9), frozenset())["guard"])
        self.assertFalse(map_state((0., 0., .3), frozenset())["guard"])

    def test_dpad_mirrors_the_stick(self):
        state = map_state((0., 0., 0.), frozenset({DPAD_LEFT, DPAD_DOWN}))
        self.assertTrue(state["left"] and state["down"])
        state = map_state((0., 0., 0.), frozenset({DPAD_RIGHT, DPAD_UP}))
        self.assertTrue(state["right"] and state["jump"])

    def test_merge_state_is_a_union(self):
        keyboard = {"left": True, "right": False, "jump": False, "punch": False,
                    "kick": False, "projectile": False, "grab": False,
                    "down": False, "guard": False}
        pad = {"left": False, "right": True, "jump": False, "punch": True,
               "kick": False, "projectile": False, "grab": False,
               "down": False, "guard": False}
        merged = merge_state(keyboard, pad)
        self.assertTrue(merged["left"] and merged["right"] and merged["punch"])
        self.assertEqual(set(merged), set(KEYS))


class MenuNavigationTests(unittest.TestCase):
    def test_confirm_and_back_only_fire_on_the_press_edge(self):
        dx, dy, confirm, back = map_menu((0., 0., 0.), frozenset({A}), frozenset())
        self.assertTrue(confirm)
        self.assertFalse(back)
        # 按住不放的第二帧不再触发
        dx, dy, confirm, back = map_menu((0., 0., 0.), frozenset({A}), frozenset({A}))
        self.assertFalse(confirm)
        dx, dy, confirm, back = map_menu((0., 0., 0.), frozenset({B}), frozenset())
        self.assertTrue(back)

    def test_stick_and_dpad_supply_cursor_velocity(self):
        dx, dy, _, _ = map_menu((0.6, -0.4, 0.), frozenset(), frozenset())
        self.assertAlmostEqual(dx, 0.6)
        self.assertAlmostEqual(dy, -0.4)
        dx, dy, _, _ = map_menu((0., 0., 0.), frozenset({DPAD_RIGHT, DPAD_DOWN}), frozenset())
        self.assertEqual((dx, dy), (1.0, 1.0))


class DeviceTests(unittest.TestCase):
    def test_no_controller_degrades_silently(self):
        pad = Gamepad()
        pad.update()
        self.assertFalse(any(pad.poll().values()))
        self.assertFalse(pad.escape_edge())
        self.assertEqual(pad.menu_state(), (0.0, 0.0, False, False))

    def test_start_is_an_escape_edge(self):
        pad = Gamepad()
        pad._prev_held = frozenset()
        pad.held = frozenset({START})
        self.assertTrue(pad.escape_edge())
        # 按住 Start 不会每帧重复触发
        pad._prev_held = frozenset({START})
        self.assertFalse(pad.escape_edge())


if __name__ == "__main__":
    unittest.main()
