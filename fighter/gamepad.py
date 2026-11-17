"""手柄输入：把 SDL2 手柄状态翻译成战斗核心使用的 9 键布尔字典。

战斗模拟从不直接读设备，只消费 ``left/right/down/jump/punch/kick/projectile/
grab/guard`` 这九个键。键盘与手柄都在同一层做翻译，因此 InputBuffer 的边沿
检测、连招指令与联机协议无需任何改动即可复用。
"""
from __future__ import annotations

import pygame

try:  # pygame 2.x 自带 SDL2 Game Controller API；精简包可能裁掉该子模块
    from pygame._sdl2 import controller
except (ImportError, AttributeError):  # pragma: no cover - 依赖发行方式
    controller = None

KEYS = ("left", "right", "down", "jump", "punch", "kick", "projectile", "grab", "guard")
# 摇杆死区：太小会让下蹲抖动并误触发 S S 指令，实测 0.28 较稳妥。
DEADZONE = 0.28
# 扳机与摇杆同量级：按下一半即视为防御。
TRIGGER_POINT = 0.5
# 菜单虚拟光标速度（逻辑像素 / 秒）。
CURSOR_SPEED = 430.0

TRACKED = (
    pygame.CONTROLLER_BUTTON_A,
    pygame.CONTROLLER_BUTTON_B,
    pygame.CONTROLLER_BUTTON_X,
    pygame.CONTROLLER_BUTTON_Y,
    pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
    pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
    pygame.CONTROLLER_BUTTON_START,
    pygame.CONTROLLER_BUTTON_BACK,
    pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
    pygame.CONTROLLER_BUTTON_DPAD_UP,
    pygame.CONTROLLER_BUTTON_DPAD_DOWN,
)


def map_state(axes, held, deadzone=DEADZONE):
    """把（左摇杆 x、左摇杆 y、右扳机）与按住的按钮集合翻译成 9 键字典。

    SDL 的左摇杆 y 轴向上为负值；十字键与左摇杆并列生效，方便习惯十字键的玩家。
    """
    lx, ly, trigger = axes
    dpad_left = pygame.CONTROLLER_BUTTON_DPAD_LEFT in held
    dpad_right = pygame.CONTROLLER_BUTTON_DPAD_RIGHT in held
    dpad_up = pygame.CONTROLLER_BUTTON_DPAD_UP in held
    dpad_down = pygame.CONTROLLER_BUTTON_DPAD_DOWN in held
    return {
        "left": dpad_left or lx <= -deadzone,
        "right": dpad_right or lx >= deadzone,
        "down": dpad_down or ly >= deadzone,
        "jump": dpad_up or ly <= -deadzone or pygame.CONTROLLER_BUTTON_A in held,
        "punch": pygame.CONTROLLER_BUTTON_X in held,
        "kick": pygame.CONTROLLER_BUTTON_Y in held,
        "projectile": pygame.CONTROLLER_BUTTON_B in held,
        "grab": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER in held,
        "guard": pygame.CONTROLLER_BUTTON_LEFTSHOULDER in held or trigger >= TRIGGER_POINT,
    }


def map_menu(axes, held, previous, deadzone=DEADZONE):
    """菜单导航：返回（横向速度、纵向速度、确认边沿、返回边沿）。

    摇杆给出连续速度，十字键给出 ±1；确认（A）与返回（B）只认“刚按下”的一帧，
    避免按住不放时连续触发点击或弹回上一页。
    """
    lx, ly, _ = axes
    if abs(lx) >= deadzone:
        dx = lx
    elif pygame.CONTROLLER_BUTTON_DPAD_RIGHT in held:
        dx = 1.0
    elif pygame.CONTROLLER_BUTTON_DPAD_LEFT in held:
        dx = -1.0
    else:
        dx = 0.0
    if abs(ly) >= deadzone:
        dy = ly
    elif pygame.CONTROLLER_BUTTON_DPAD_DOWN in held:
        dy = 1.0
    elif pygame.CONTROLLER_BUTTON_DPAD_UP in held:
        dy = -1.0
    else:
        dy = 0.0
    confirm = (pygame.CONTROLLER_BUTTON_A in held and
               pygame.CONTROLLER_BUTTON_A not in previous)
    back = (pygame.CONTROLLER_BUTTON_B in held and
            pygame.CONTROLLER_BUTTON_B not in previous)
    return dx, dy, confirm, back


def merge_state(base, extra):
    """把键盘字典与手柄字典按位或合并，保持九键结构不变。"""
    return {key: bool(base.get(key)) or bool(extra.get(key)) for key in KEYS}


class Gamepad:
    """持有一个 SDL2 手柄（优先第一个），每帧采样一次。

    没有手柄、驱动不支持或中途拔掉时全部静默降级为“无输入”，不影响键盘游玩。
    """

    def __init__(self):
        self.controller = None
        self.axes = (0., 0., 0.)
        self.held = frozenset()
        self._prev_held = frozenset()
        if controller is not None:
            try:
                controller.init()
            except pygame.error:  # 驱动缺失时仍可继续用键盘
                pass
        self.refresh()

    def _attach(self):
        try:
            if controller.get_count() < 1:
                return None
            return controller.Controller(0)
        except (pygame.error, ValueError):
            return None

    def refresh(self):
        """热插拔：启动后用插入的手柄也会在下一帧被接管。"""
        if self.controller is None:
            self.controller = self._attach()

    def update(self):
        """每帧采样一次；后续 poll / menu_state / escape_edge 都读这份缓存。"""
        self.refresh()
        self._prev_held = self.held
        self.axes = (0., 0., 0.)
        self.held = frozenset()
        if self.controller is None:
            return
        try:
            self.axes = (
                max(-1., min(1., self.controller.get_axis(
                    pygame.CONTROLLER_AXIS_LEFTX) / 32767)),
                max(-1., min(1., self.controller.get_axis(
                    pygame.CONTROLLER_AXIS_LEFTY) / 32767)),
                max(0., min(1., self.controller.get_axis(
                    pygame.CONTROLLER_AXIS_TRIGGERRIGHT) / 32767)),
            )
            self.held = frozenset(button for button in TRACKED
                                  if self.controller.get_button(button))
        except pygame.error:  # 设备被拔掉：丢弃句柄，下一帧尝试重新接管
            self.controller = None
            self.axes = (0., 0., 0.)
            self.held = frozenset()

    def poll(self):
        """战斗输入：与键盘同构的九键字典。"""
        return map_state(self.axes, self.held)

    def menu_state(self):
        """菜单导航输入（速度 / 确认 / 返回），只在菜单页使用。"""
        return map_menu(self.axes, self.held, self._prev_held)

    def escape_edge(self):
        """Start 或 Back 刚按下：交给现有 ESC 逻辑处理暂停与返回。"""
        return (pygame.CONTROLLER_BUTTON_START in self.held and
                pygame.CONTROLLER_BUTTON_START not in self._prev_held) or (
                pygame.CONTROLLER_BUTTON_BACK in self.held and
                pygame.CONTROLLER_BUTTON_BACK not in self._prev_held)
