"""一次性脚本：合成一段激昂的熔岩地貌战斗主题（有旋律、有鼓点）。

输出 assets/music/lava.wav，152 BPM / D 小调 / 8 小节（约 12.6 秒）无缝循环，
16bit 单声道 22050Hz，仅用标准库。
"""
import array
import math
import random
import wave
from pathlib import Path

SR = 22050
BPM = 152
BEAT = 60 / BPM
BAR = BEAT * 4
BARS = 8
N = int(round(BAR * BARS * SR))
TAIL = int(SR * .6)
buf = array.array("d", bytes(8 * (N + TAIL)))

rnd = random.Random(2024)


def add(idx, value):
    if 0 <= idx < N + TAIL:
        buf[idx] += value


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def at(bar, beat):
    return int((bar * BAR + beat * BEAT) * SR)


def kick(pos):
    dur = .26
    for k in range(int(SR * dur)):
        t = k / SR
        f = 118 * math.exp(-t * 26) + 44
        add(pos + k, .62 * math.exp(-t * 11) * math.sin(2 * math.pi * f * t))
    for k in range(int(SR * .006)):
        add(pos + k, .18 * (rnd.random() * 2 - 1) * (1 - k / (SR * .006)))


def snare(pos):
    dur, prev = .18, 0.
    for k in range(int(SR * dur)):
        t = k / SR
        n = rnd.random() * 2 - 1
        hp = n - prev
        prev = n
        env = math.exp(-t * 22)
        add(pos + k, .32 * env * hp + .13 * env * math.sin(2 * math.pi * 190 * t))


def hat(pos, amp=.10):
    dur, prev = .05, 0.
    for k in range(int(SR * dur)):
        t = k / SR
        n = rnd.random() * 2 - 1
        hp = n - prev
        prev = n
        add(pos + k, amp * math.exp(-t * 70) * hp)


def crash(pos, amp=.18):
    dur, prev = 1.1, 0.
    for k in range(int(SR * dur)):
        t = k / SR
        n = rnd.random() * 2 - 1
        hp = n - prev
        prev = n
        add(pos + k, amp * math.exp(-t * 3.2) * hp)


def tom(pos, f0, amp=.26):
    dur = .22
    for k in range(int(SR * dur)):
        t = k / SR
        f = f0 * (1 - .35 * t / dur)
        add(pos + k, amp * math.exp(-t * 14) * math.sin(2 * math.pi * f * t))


def lead(pos, midi, beats):
    dur = beats * BEAT
    total = int(SR * (dur + .12))
    f0 = hz(midi)
    p1 = p2 = lp = 0.
    for k in range(total):
        t = k / SR
        vib = 0. if t < .12 else .007 * math.sin(2 * math.pi * 5.4 * (t - .12))
        f = f0 * (1 + vib)
        p1 += f / SR
        p2 += f * 1.004 / SR
        s = (2 * (p1 % 1) - 1) * .6 + (2 * (p2 % 1) - 1) * .4
        lp += (s - lp) * .45
        if t < .01:
            env = t / .01
        elif t < dur:
            env = 1 - .25 * (t / dur)
        else:
            env = .75 * max(0., 1 - (t - dur) / .12)
        add(pos + k, .27 * env * lp)


def bass(pos, midi, beats, amp=.34):
    dur = beats * BEAT
    total = int(SR * (dur + .05))
    f = hz(midi)
    p = lp = 0.
    for k in range(total):
        t = k / SR
        p += f / SR
        s = (2 * (p % 1) - 1) * .55 + math.sin(2 * math.pi * p) * .45
        lp += (s - lp) * .18
        if t < .006:
            env = t / .006
        elif t < dur:
            env = 1 - .35 * (t / dur)
        else:
            env = .65 * max(0., 1 - (t - dur) / .05)
        add(pos + k, amp * env * lp)


def pad(pos, midis, beats, amp=.10):
    dur = beats * BEAT
    total = int(SR * dur)
    voices = [hz(m) for m in midis]
    for k in range(total):
        t = k / SR
        s = 0.
        for f in voices:
            s += math.sin(2 * math.pi * f * t) + .3 * math.sin(4 * math.pi * f * t)
        env = min(1., t / .2) * min(1., max(0., (dur - t) / .3))
        add(pos + k, amp * env * s / len(voices))


CHORDS = [
    [50, 57, 62, 65], [46, 53, 58, 62], [41, 48, 53, 57], [36, 43, 48, 52],
    [50, 57, 62, 65], [46, 53, 58, 62], [36, 43, 48, 52], [45, 52, 57, 61],
]
ROOTS = [38, 34, 41, 36, 38, 34, 36, 45]

MELODY = [
    (0, 0, 69, .5), (0, .5, 74, .5), (0, 1, 77, .5), (0, 1.5, 76, .5),
    (0, 2, 74, .5), (0, 2.5, 69, .5), (0, 3, 72, .5), (0, 3.5, 74, .5),
    (1, 0, 70, .5), (1, .5, 74, .5), (1, 1, 77, .5), (1, 1.5, 79, .5),
    (1, 2, 77, .5), (1, 2.5, 74, .5), (1, 3, 70, .5), (1, 3.5, 72, .5),
    (2, 0, 69, .5), (2, .5, 72, .5), (2, 1, 77, .5), (2, 1.5, 76, .5),
    (2, 2, 74, .5), (2, 2.5, 72, .5), (2, 3, 69, .5), (2, 3.5, 65, .5),
    (3, 0, 67, .5), (3, .5, 72, .5), (3, 1, 76, .5), (3, 1.5, 79, .5),
    (3, 2, 77, 1.), (3, 3, 76, .5), (3, 3.5, 74, .5),
    (4, 0, 74, .5), (4, .5, 77, .5), (4, 1, 81, .5), (4, 1.5, 79, .5),
    (4, 2, 77, .5), (4, 2.5, 76, .5), (4, 3, 74, .5), (4, 3.5, 77, .5),
    (5, 0, 82, 1.), (5, 1, 81, .5), (5, 1.5, 77, .5),
    (5, 2, 74, .5), (5, 2.5, 77, .5), (5, 3, 82, 1.),
    (6, 0, 84, 1.), (6, 1, 82, .5), (6, 1.5, 81, .5),
    (6, 2, 79, .5), (6, 2.5, 76, .5), (6, 3, 84, 1.),
    (7, 0, 81, 1.), (7, 1, 79, .5), (7, 1.5, 76, .5),
    (7, 2, 73, .5), (7, 2.5, 76, .5), (7, 3, 81, 1.),
]

BASS_PATTERN = [0, 0, 12, 0, 0, 12, 0, 7]

for bar in range(BARS):
    pad(at(bar, 0), CHORDS[bar], 4)
    root = ROOTS[bar]
    for i, step in enumerate(BASS_PATTERN):
        bass(at(bar, i * .5), root + step, .5)
    for b in (0, 1, 2, 3):
        kick(at(bar, b))
    for b in (1, 3):
        snare(at(bar, b))
    for i in range(8):
        hat(at(bar, i * .5), .10 if i % 2 == 0 else .065)
    if bar in (0, 4):
        crash(at(bar, 0))
    if bar in (3, 7):
        for i, f in enumerate((300, 250, 200, 160)):
            tom(at(bar, 3 + i * .25), f)

for bar, beat, midi, beats in MELODY:
    lead(at(bar, beat), midi, beats)

brown = low = 0.
for i in range(N + TAIL):
    brown += (rnd.random() * 2 - 1) * .02
    brown *= .996
    low += (brown - low) * .02
    buf[i] += low * .55

for i in range(TAIL):
    buf[i] += buf[N + i]

peak = max(abs(v) for v in buf[:N]) or 1.
scale = .92 / peak
out = array.array("h", bytes(2 * N))
for i in range(N):
    v = math.tanh(buf[i] * scale * 1.1) * 1.25
    out[i] = int(max(-1., min(1., v)) * 32767)

target = Path(__file__).resolve().parent / "assets" / "music" / "lava.wav"
with wave.open(str(target), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(out.tobytes())

rms = math.sqrt(sum(v * v for v in out) / N) / 32767
final_peak = max(abs(v) for v in out) / 32767
print(f"OK: {target} ({target.stat().st_size / 1024:.0f} KB, {N / SR:.2f}s, "
      f"peak {final_peak:.2f}, rms {rms:.2f})")