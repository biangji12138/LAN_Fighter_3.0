"""Frame-addressable input history and motion-command parser (no pygame dependency).
Direction notation is relative to current facing, like classic fighting games.
"""
from collections import deque

BUTTONS = ('punch', 'kick', 'projectile', 'grab', 'jump', 'guard')

# 真人快打式 negative edge：松开按键也算一次输入。
# 只放开攻击键；跳跃 / 防御是方向与姿态，松手不应出招。
NEGATIVE_EDGE_BUTTONS = ('punch', 'kick', 'projectile', 'grab')

class InputBuffer:
    def __init__(self, max_frames=45):
        self.history = deque(maxlen=max_frames)
        self.previous = {}
        self.frame = 0
        self.taps = {'forward': deque(maxlen=3), 'back': deque(maxlen=3), 'down': deque(maxlen=3),
                     'up': deque(maxlen=3)}
        self.presses = {button: deque(maxlen=4) for button in BUTTONS}
        # 未消费的按键按下沿（帧号, 按键），供“输入缓冲”跨帧取用。
        self.buffer = deque(maxlen=12)
        # 本次按下是否已经出过招：消费过的按键松开时不再算输入，
        # 否则一次点按会变成“按下一下 + 松开一下”两次出招。
        self.consumed = {button: False for button in BUTTONS}
        # 本帧可作为输入使用的松开沿（未被消费的松键），供特殊技 / 指令识别。
        self.releases = frozenset()
        self.release_stamps = {button: deque(maxlen=4)
                               for button in NEGATIVE_EDGE_BUTTONS}
        self.previous_forward = False
        self.previous_back = False
        self.previous_down = False
        self.previous_up = False
        self.last_face = 1

    @staticmethod
    def direction(keys, face):
        forward = bool(keys.get('right' if face > 0 else 'left'))
        back = bool(keys.get('left' if face > 0 else 'right'))
        down = bool(keys.get('down'))
        up = bool(keys.get('jump'))
        horizontal = 1 if forward and not back else -1 if back and not forward else 0
        vertical = -1 if down else 1 if up else 0
        return {(0, 0): '5', (1, 0): '6', (-1, 0): '4', (0, -1): '2',
                (1, -1): '3', (-1, -1): '1', (0, 1): '8',
                (1, 1): '9', (-1, 1): '7'}[(horizontal, vertical)]

    def push(self, keys, face=1):
        self.frame += 1
        keys = {k: bool(v) for k, v in keys.items()}
        if face != self.last_face:
            self.taps['forward'].clear()
            self.taps['back'].clear()
            self.last_face = face
        direction = self.direction(keys, face)
        forward = bool(keys.get('right' if face > 0 else 'left'))
        back = bool(keys.get('left' if face > 0 else 'right'))
        if forward and not self.previous_forward:
            self.taps['forward'].append(self.frame)
        if back and not self.previous_back:
            self.taps['back'].append(self.frame)
        self.previous_forward, self.previous_back = forward, back
        down = bool(keys.get('down'))
        if down and not self.previous_down:
            self.taps['down'].append(self.frame)
        self.previous_down = down
        up = bool(keys.get('jump'))
        if up and not self.previous_up:
            self.taps['up'].append(self.frame)
        self.previous_up = up
        pressed = frozenset(b for b in BUTTONS if keys.get(b) and not self.previous.get(b))
        for button in pressed:
            self.presses[button].append(self.frame)
            # 方向随按键一起缓存：按下那一刻是否蹲着，决定之后出蹲招还是站招。
            self.buffer.append((self.frame, button, down))
        # negative edge：记录本帧的松键沿。已经出过招的那次按下被消费后，
        # 对应的松开不再算输入，避免“按下 + 松开”打出两招。
        released = set()
        for button in NEGATIVE_EDGE_BUTTONS:
            if self.previous.get(button) and not keys.get(button):
                if self.consumed[button]:
                    self.consumed[button] = False
                else:
                    released.add(button)
                    self.release_stamps[button].append(self.frame)
        self.releases = frozenset(released)
        self.history.append((self.frame, direction, pressed))
        self.previous = keys
        return pressed

    def pressed_within(self, button, window=6):
        """True if the newest press edge of a button happened within the last `window` frames."""
        stamps = self.presses.get(button)
        return bool(stamps and self.frame - stamps[-1] <= window)

    def released_within(self, button, window=6):
        """True if the newest negative-edge release happened within `window` frames."""
        stamps = self.release_stamps.get(button)
        return bool(stamps and self.frame - stamps[-1] <= window)

    def buffered_buttons(self, window=8,
                         buttons=('punch', 'kick', 'projectile', 'grab')):
        """最近 `window` 帧内尚未消费的攻击按键。

        真人快打式输入缓冲：在收招 / 硬直结束前按下的键仍然有效，
        下一帧能行动时会自动接上，不会因为按早了几帧而丢掉。
        """
        return frozenset(b for frame, b, _down in self.buffer
                         if self.frame - frame <= window and b in buttons)

    def buffered_down(self, window=8,
                      buttons=('punch', 'kick', 'projectile', 'grab')):
        """最近一次有效缓冲按键按下时是否按着下蹲键（方向随按键缓存）。"""
        for frame, button, down in reversed(self.buffer):
            if self.frame - frame <= window and button in buttons:
                return down
        return False

    def down_recent(self, window=4):
        """下蹲键刚刚点过（用于同帧松开 S 时仍判定为蹲招）。"""
        taps = self.taps['down']
        return bool(taps and self.frame - taps[-1] <= window)

    def consume_buttons(self, buttons):
        """作废指定按键的缓冲记录（用后即消费，避免同一按键重复出招）。"""
        if not buttons:
            return
        for button in buttons:
            # 只有还按着的键才需要在松开时屏蔽：已经出过招，松手不该再来一次。
            if self.previous.get(button):
                self.consumed[button] = True
        self.buffer = deque(((frame, b, down) for frame, b, down in self.buffer
                             if b not in buttons), maxlen=self.buffer.maxlen)

    def double_tap(self, name, window=14):
        """True when the newest press edge of 'forward'/'back' is a double tap."""
        taps = self.taps[name]
        return (len(taps) >= 2 and taps[-1] == self.frame and
                taps[-1] - taps[-2] <= window)

    def double_down(self, window=18, recent=30):
        """True when the player tapped S twice recently (S, S prefix of a command)."""
        taps = self.taps['down']
        return (len(taps) >= 2 and self.frame - taps[-1] <= recent and
                taps[-1] - taps[-2] <= window)

    def double_up(self, window=18, recent=30):
        """True when the player tapped W (jump) twice recently (W, W prefix)."""
        taps = self.taps['up']
        return (len(taps) >= 2 and self.frame - taps[-1] <= recent and
                taps[-1] - taps[-2] <= window)

    def direction_tap(self, window=30):
        """True when the player tapped forward or back (移动键) recently."""
        f = self.taps['forward']
        b = self.taps['back']
        return bool((f and self.frame - f[-1] <= window) or
                    (b and self.frame - b[-1] <= window))

    def double_tap_recent(self, name, window=14, recent=20):
        """Like double_tap, but stays true for a few frames so a follow-up
        button press can still read the completed direction command."""
        taps = self.taps[name]
        return (len(taps) >= 2 and self.frame - taps[-1] <= recent and
                taps[-1] - taps[-2] <= window)

    def double_press(self, button, window=12, recent=6):
        """True when the button was just pressed twice in quick succession."""
        stamps = self.presses.get(button)
        return (bool(stamps) and len(stamps) >= 2 and
                self.frame - stamps[-1] <= recent and
                stamps[-1] - stamps[-2] <= window)

    def motion(self, sequence, button, window=20):
        """Return True if recent directional changes contain the command in order.
        Uses press edges; consumes only by caller's action state, not by this parser.
        """
        if not self.history or button not in self.history[-1][2]:
            return False
        recent = [d for frame, d, _ in self.history if frame >= self.frame-window]
        collapsed = []
        for d in recent:
            if not collapsed or collapsed[-1] != d:
                collapsed.append(d)
        position = len(collapsed)-1
        for required in reversed(sequence):
            while position >= 0 and collapsed[position] != required:
                position -= 1
            if position < 0:
                return False
            position -= 1
        return True

    def consume(self):
        if self.history:
            frame, direction, _ = self.history[-1]
            self.history[-1] = (frame, direction, frozenset())
