"""Visual theme: colour palette, colour helpers and font loading.

This module has no GameApp state and no drawing side effects beyond pygame.font.
"""
import os

import pygame

from . import assets

# Logical resolution the whole game is authored against. 1210x680 matches a
# 16:9 desktop, so fullscreen letterboxing stays under a pixel on 1080p.
W, H = 1210, 680

# Colour palette.
BG = (12, 19, 35)
PANEL = (24, 36, 59)
PANEL_HI = (34, 49, 76)
WHITE = (237, 242, 255)
MUTED = (151, 166, 194)
BLUE = (56, 117, 245)
CYAN = (68, 211, 225)
RED = (239, 85, 99)
GREEN = (83, 206, 149)
GOLD = (255, 200, 89)


def shade(color, factor):
    """Darken / brighten a colour tuple by a multiplier."""
    return tuple(max(0, min(255, int(v * factor))) for v in color)


def mix(a, b, t):
    """Blend two RGB tuples; t=0 gives a, t=1 gives b."""
    t = max(0., min(1., t))
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


# Fonts are looked up in the asset folder first, then the Windows Fonts
# directory; pygame's default face is the final fallback.
_FONT_FILES = ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc", "Deng.ttf",
               "NotoSansSC-Regular.otf", "SourceHanSansSC-Regular.otf")


def _font_file():
    folder = os.path.join(assets.ASSET_DIR, "fonts")
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".ttf", ".ttc", ".otf")):
                return os.path.join(folder, name)
    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in _FONT_FILES:
        candidate = os.path.join(fonts_dir, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def font(size, bold=False):
    """Return a pygame Font for the requested size, bold optional."""
    path = _font_file()
    if path:
        try:
            face = pygame.font.Font(path, size)
            if bold:
                face.set_bold(True)
            return face
        except Exception:
            pass
    try:
        return pygame.font.Font(None, size)
    except Exception:
        return pygame.font.Font(None, 24)
