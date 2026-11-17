"""一次性脚本：合成冰雪溶洞主题（冷冽、通透、有旋律的循环 BGM）。

输出 assets/music/ice.wav，132 BPM / A 小调 / 8 小节（约 14.5 秒）无缝循环，
16bit 单声道 22050Hz，仅用标准库。
"""
import array
import math
import random
import wave
from pathlib import Path

SR = 22050
BPM = 132
BEAT = 60 / BPM
BAR = BEAT * 4
BARS = 8
N = int(round(BAR * BARS * SR))
TAIL = int(SR * .6)
buf = array.array("d", bytes(8 * (N + TAIL)))
bell = array.array("d", bytes(8 * (N + TAIL)))
rnd = random.Random(808)


def add(b, i, v):
    if 0 <= i < N + TAIL:
        b[i] += v


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def at(bar, beat):
    return int((bar * BAR + beat * BEAT) * SR)


def chime(pos, midi, amp=.11, dur=.42):
    f = hz(midi)
    for k in range(int(SR * dur)):
        t = k / SR
        env = math.exp(-t * 9.) * min(1., t / .004)
        s = (math.sin(2 * math.pi * f * t) + .35 * math.sin(4 * math.pi * f * t)
             + .12 * math.sin(6 * math.pi * f * t))
        add(bell, pos + k, amp * env * s)


def lead(pos, midi, beats, amp=.16):
    dur = beats * BEAT
    total = int(SR * (dur + .22))
    f = hz(midi)
    p = 0.
    for k in range(total):
        t = k / SR
        p += f * (1 + .004 * math.sin(2 * math.pi * 4.6 * t)) / SR
        s = math.sin(2 * math.pi * p) + .25 * math.sin(4 * math.pi * p)
        if t < .05:
            env = t / .05
        elif t < dur:
            env = 1.
        else:
            env = max(0., 1 - (t - dur) / .22)
        add(buf, pos + k, amp * env * s)


def pad(pos, midis, beats, amp=.085):
    dur = beats * BEAT
    total = int(SR * dur)
    voices = [hz(m) for m in midis]
    for k in range(total):
        t = k / SR
        s = 0.
        for f in voices:
            s += math.sin(2 * math.pi * f * t) + .18 * math.sin(4 * math.pi * f * t)
        env = min(1., t / .35) * min(1., max(0., (dur - t) / .4))
        add(buf, pos + k, amp * env * s / len(voices))


def bass(pos, midi, beats, amp=.30):
    dur = beats * BEAT
    total = int(SR * (dur + .04))
    f = hz(midi)
    p = 0.
    for k in range(total):
        t = k / SR
        p += f / SR
        s = math.sin(2 * math.pi * p) + .3 * math.sin(4 * math.pi * p)
        if t < .008:
            env = t / .008
        elif t < dur:
            env = 1 - .2 * (t / dur)
        else:
            env = .8 * max(0., 1 - (t - dur) / .04)
        add(buf, pos + k, amp * env * s)


def kick(pos, amp=.45):
    dur = .24
    for k in range(int(SR * dur)):
        t = k / SR
        f = 92 * math.exp(-t * 30) + 48
        add(buf, pos + k, amp * math.exp(-t * 13) * math.sin(2 * math.pi * f * t))


def snare(pos, amp=.16):
    dur, prev = .16, 0.
    for k in range(int(SR * dur)):
        t = k / SR
        n = rnd.random() * 2 - 1
        hp = n - prev
        prev = n
        add(buf, pos + k, amp * math.exp(-t * 26) * hp)


def shaker(pos, amp=.038):
    dur, prev = .035, 0.
    for k in range(int(SR * dur)):
        t = k / SR
        n = rnd.random() * 2 - 1
        hp = n - prev
        prev = n
        add(buf, pos + k, amp * math.exp(-t * 110) * hp)


CHORDS = [
    [57, 60, 64], [53, 57, 60], [60, 64, 67], [55, 59, 62],
    [57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 55, 59],
]
ROOTS = [45, 41, 36, 43, 45, 41, 43, 40]
ARP = [0, 1, 2, 1, 0, 2, 1, 3]

MELODY = [
    (0, 0, 76, 1.5), (0, 1.5, 72, .5), (0, 2, 69, 1.), (0, 3, 72, 1.),
    (1, 0, 77, 1.5), (1, 1.5, 72, .5), (1, 2, 69, 2.),
    (2, 0, 79, 1.), (2, 1, 76, 1.), (2, 2, 72, 1.), (2, 3, 74, 1.),
    (3, 0, 74, 2.), (3, 2, 71, 1.), (3, 3, 74, 1.),
    (4, 0, 76, 1.5), (4, 1.5, 79, .5), (4, 2, 81, 1.), (4, 3, 79, 1.),
    (5, 0, 77, 2.), (5, 2, 76, 1.), (5, 3, 72, 1.),
    (6, 0, 74, 1.), (6, 1, 76, 1.), (6, 2, 79, 2.),
    (7, 0, 76, 1.), (7, 1, 74, 1.), (7, 2, 71, 2.),
]

for bar in range(BARS):
    chord = CHORDS[bar]
    pad(at(bar, 0), chord, 4)
    for b in range(4):
        bass(at(bar, b), ROOTS[bar] + (12 if b % 2 else 0), 1.)
    for s in range(16):
        chime(at(bar, s * .25), chord[min(ARP[s % len(ARP)], 2)] + 24 + (12 if ARP[s % len(ARP)] == 3 else 0),
              amp=.11 if s % 4 == 0 else .075)
        shaker(at(bar, s * .25), .038 if s % 2 else .022)
    kick(at(bar, 0))
    kick(at(bar, 2), .38)
    snare(at(bar, 1))
    snare(at(bar, 3))

for bar, beat, midi, beats in MELODY:
    lead(at(bar, beat), midi, beats)

# 洞窟风声：极低频的布朗噪声。
brown = low = 0.
for i in range(N + TAIL):
    brown += (rnd.random() * 2 - 1) * .02
    brown *= .996
    low += (brown - low) * .012
    buf[i] += low * .9

# 冰晶回声：单抽头反馈延迟，环形处理让尾巴接回开头。
delay = int(SR * .26)
echo = array.array("d", bell)
for i in range(N + TAIL):
    bell[i] += echo[(i - delay) % (N + TAIL)] * .34

for i in range(N + TAIL):
    buf[i] += bell[i]

for i in range(TAIL):
    buf[i] += buf[N + i]

peak = max(abs(v) for v in buf[:N]) or 1.
scale = .92 / peak
out = array.array("h", bytes(2 * N))
for i in range(N):
    v = math.tanh(buf[i] * scale * 1.1) * .86
    out[i] = int(max(-1., min(1., v)) * 32767)

target = Path(__file__).resolve().parent / "assets" / "music" / "ice.wav"
with wave.open(str(target), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(out.tobytes())

rms = math.sqrt(sum(v * v for v in out) / N) / 32767
final_peak = max(abs(v) for v in out) / 32767
print(f"OK: {target} ({target.stat().st_size / 1024:.0f} KB, {N / SR:.2f}s, "
      f"peak {final_peak:.2f}, rms {rms:.2f})")