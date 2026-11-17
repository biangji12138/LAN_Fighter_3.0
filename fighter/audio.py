"""Self-generated original sound effects; no music files or external assets required."""
import array
import math
import random
import pygame
from pathlib import Path

# Per-map background music: assets/music/<map_id>.ogg loops on the music
# channel while its arena is active. Files are optional -- a map without
# an asset simply plays no BGM.
MUSIC_DIR = Path(__file__).resolve().parent.parent / "assets" / "music"
# OGG preferred; plain WAV accepted so procedurally generated ambience can be
# dropped in without an external audio encoder.
MUSIC_EXTENSIONS = (".ogg", ".wav")

# 音效文件目录：把与音效同名的文件（如 time_stop.ogg）放进来，就会覆盖程序
# 合成的占位音；没有文件时自动回退到合成音，不影响游戏运行。
SFX_DIR = Path(__file__).resolve().parent.parent / "assets" / "sfx"
SFX_EXTENSIONS = (".ogg", ".wav")


def play_map_music(map_id, enabled):
    """Switch the BGM to ``map_id``'s track; ``None`` stops the music.

    Safe to call every frame: the wanted track is cached, so the file is
    only (re)loaded when the map, or the enabled flag, actually changes.
    """
    want = None
    if enabled and map_id:
        for ext in MUSIC_EXTENSIONS:
            candidate = MUSIC_DIR / f"{map_id}{ext}"
            if candidate.is_file():
                want = str(candidate)
                break
    if getattr(play_map_music, "_want", object()) == want:
        return
    play_map_music._want = want
    if not pygame.mixer.get_init():
        return
    try:
        if want is None:
            pygame.mixer.music.stop()
        else:
            pygame.mixer.music.load(want)
            pygame.mixer.music.set_volume(0.55)
            pygame.mixer.music.play(-1)
    except (pygame.error, FileNotFoundError, OSError):
        pass  # no BGM asset for this map yet; stay silent


class Audio:
    def __init__(self):
        self.ready = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.ready = True
            external = set()
            for name, hz, duration, noise in (
                ("punch", 230, .11, .62), ("crouch_punch", 255, .10, .55),
                ("kick", 135, .19, .57), ("grab", 185, .16, .45),
                ("low_kick", 150, .17, .60), ("jump_punch", 260, .10, .55),
                ("projectile", 640, .20, .15), ("dash", 320, .10, .30),
                ("super", 520, .45, .25),
                # Grab super (red scarf): suction, rapid punches, heavy throw.
                ("grab_pull", 340, .28, .42),
                ("pummel", 210, .075, .78),
                ("pummel_finish", 115, .20, .72),
                ("throw", 92, .36, .85),
                # Bright metallic cut for each slash of the rushing super.
                ("slash_hit", 880, .14, .45),
                ("hit", 90, .20, .85), ("jump", 560, .09, .13),
                ("land", 110, .10, .8), ("round_end", 690, .33, .08),
                ("match_end", 920, .50, .05), ("round_start", 760, .20, .05),
                # Lava field: a hiss while the warning ring glows, then the
                # erupting pillar.
                ("lava_warn", 720, .85, .45),
                # Ice cavern: the shard slicing down, the freeze impact and
                # the shatter on the floor.
                ("ice_fall", 1500, .18, .78), ("ice_hit", 1900, .30, .50),
                ("ice_shatter", 2600, .32, .92),
                # 角色专属：火焰弹、素质三连点火、结冰系技能起手、时停瞬发拳。
                ("projectile_fire", 540, .18, .28),
                ("flame_buff", 470, .32, .35),
                ("ice_freeze", 1500, .30, .30),
                ("time_punch", 300, .10, .65),
                # 砸瓦鲁多：恢复时的清脆碎裂声（时停钟声单独合成，见下方）。
                ("time_resume", 620, .32, .18)):
                sound = self._load_sfx(name)
                if sound is None:
                    sound = self._tone(hz, duration, noise)
                else:
                    external.add(name)
                self.sounds[name] = sound
            self.sounds["lava_erupt"] = (self._load_sfx("lava_erupt")
                                         or self._boom(.62))
            self.sounds["time_stop"] = (self._load_sfx("time_stop")
                                        or self._time_stop_sound())
            # 时停里可以连打到十几拳，瞬发拳音效压低，避免盖过时停本体。
            self.sounds["time_punch"].set_volume(.55)
            # 通用大招与发波只剩合成的“叮”占位音，不像打击音：没有外部素材时
            # 直接静音；把 super.ogg / projectile.ogg 放进 assets/sfx/ 会自动恢复。
            for name in ("super", "projectile"):
                if name not in external:
                    del self.sounds[name]
        except pygame.error:
            self.ready = False

    def _load_sfx(self, name):
        """外部音效优先：assets/sfx/<name>.ogg（或 .wav）；没有文件返回 None。"""
        for ext in SFX_EXTENSIONS:
            candidate = SFX_DIR / f"{name}{ext}"
            if candidate.is_file():
                try:
                    return pygame.mixer.Sound(str(candidate))
                except (pygame.error, FileNotFoundError, OSError):
                    return None
        return None

    def _time_stop_sound(self, duration=1.7):
        """砸瓦鲁多的占位音：钟摆被掐停的滴答 + 时间变慢的下坠扫频 + 低钟长鸣。"""
        rate = pygame.mixer.get_init()[0]
        rnd = random.Random(77)
        data = array.array("h")
        for i in range(int(rate * duration)):
            t = i / rate
            p = t / duration
            # 钟体：基音加两个非谐波泛音，各自指数衰减，像一口大钟被敲响。
            bell = (math.sin(2 * math.pi * 88 * t) * math.exp(-t * 2.2) * .9
                    + math.sin(2 * math.pi * 143 * t) * math.exp(-t * 3.6) * .42
                    + math.sin(2 * math.pi * 229 * t) * math.exp(-t * 5.5) * .26)
            # 下坠扫频：前 0.5 秒从 780Hz 滑到 80Hz，把"时间流速被拧慢"听出来。
            sweep = 0.
            if t < .5:
                f = 780 - 700 * (t / .5)
                sweep = math.sin(2 * math.pi * f * t) * (1 - t / .5) ** 1.3 * .55
            # 起手：极短的高频噪音 + 高音点，像钟摆被一把按停。
            tick = (rnd.random() * 2 - 1) * max(0., 1 - t / .04) * .7
            ping = math.sin(2 * math.pi * 1560 * t) * max(0., 1 - t / .07) * .45
            # 停止后的低频空气噪，世界停摆的余韵。
            hush = (rnd.random() * 2 - 1) * .07 * math.exp(-p * 2.5)
            value = (bell + sweep + tick + ping + hush) * (1 - p) ** .5
            data.append(int(max(-1., min(1., value)) * 10800))
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _tone(self, hz, duration, noise):
        rate = pygame.mixer.get_init()[0]
        rnd = random.Random(int(hz))
        data = array.array("h")
        for i in range(int(rate * duration)):
            t = i / rate
            envelope = (1 - i / (rate * duration)) ** 1.9
            wave = math.sin(2 * math.pi * (hz * t + 90 * t * t))
            value = (wave * (1 - noise) + (rnd.random() * 2 - 1) * noise) * envelope
            data.append(int(value * 9800))
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _boom(self, duration):
        """Eruption of a lava pillar: sub-bass thump, blast and a sharp crack."""
        rate = pygame.mixer.get_init()[0]
        rnd = random.Random(4242)
        data = array.array("h")
        for i in range(int(rate * duration)):
            t = i / rate
            p = t / duration
            sub = math.sin(2 * math.pi * t * (60 - 26 * p)) * (1 - p) ** 1.6
            blast = (rnd.random() * 2 - 1) * (1 - p) ** 2.4
            crack = (rnd.random() * 2 - 1) * max(0., 1 - t / .08) * .55
            value = sub * .75 + blast * .55 + crack
            data.append(int(max(-1., min(1., value)) * 11500))
        return pygame.mixer.Sound(buffer=data.tobytes())

    def play(self, name, enabled=True):
        if enabled and self.ready and name in self.sounds:
            # 返回播放该音效的 Channel，便于调用方中途掐断（如大招前摇被打断）。
            return self.sounds[name].play()
        return None
