"""Optional art loader with a silent procedural fallback.

Drop images into these folders (all optional):

    assets/backgrounds/menu.png       menu / select / settings backdrop
    assets/backgrounds/arena.png      fight arena backdrop
    assets/backgrounds/lava.jpg       lava field stage backdrop
    assets/backgrounds/ice.jpg        ice cavern stage backdrop
    assets/portraits/<char_id>.png    square avatar on menu & select cards
    assets/characters/<char_id>.png   full-body art on the showcase page

PNG / JPG / WEBP / BMP are accepted. Missing files return ``None`` so every
caller keeps using the drawn-in-code visuals instead of crashing.
"""
from __future__ import annotations

import os
import sys

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(ROOT, "assets")
_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
_cache = {}


def path_for(folder, name):
    """Return the first existing file for ``folder/name`` or None."""
    for ext in _EXTENSIONS:
        candidate = os.path.join(ASSET_DIR, folder, name + ext)
        if os.path.isfile(candidate):
            return candidate
    return None


def load(folder, name, size=None):
    """Load an image and optionally scale it. Cached; None when absent."""
    key = (folder, name, size)
    if key in _cache:
        return _cache[key]
    surface = None
    filename = path_for(folder, name)
    if filename:
        try:
            image = pygame.image.load(filename)
        except (pygame.error, OSError):
            image = None
            print(f"LANFighter: 图片资源损坏或无法解码，已忽略：{filename}", file=sys.stderr)
        if image is not None:
            try:
                image = image.convert_alpha()
            except pygame.error:
                pass
            if size:
                image = pygame.transform.smoothscale(image, size)
            surface = image
    _cache[key] = surface
    return surface


def _crop_to_cover(image, size, anchor):
    target_w, target_h = size
    w, h = image.get_size()
    if w <= 0 or h <= 0:
        return None
    scale = max(target_w / float(w), target_h / float(h))
    scaled = pygame.transform.smoothscale(
        image, (max(1, int(w * scale)), max(1, int(h * scale))))
    sw, sh = scaled.get_size()
    x = (sw - target_w) // 2
    if anchor == "bottom":
        y = sh - target_h
    elif anchor == "top":
        y = 0
    else:
        y = (sh - target_h) // 2
    out = pygame.Surface(size, pygame.SRCALPHA)
    out.blit(scaled, (0, 0), pygame.Rect(x, y, target_w, target_h))
    return out


def cover(folder, name, size, anchor="center"):
    """Scale-and-crop so the image fills ``size`` without distortion."""
    key = ("cover", folder, name, size, anchor)
    if key in _cache:
        return _cache[key]
    image = load(folder, name)
    out = _crop_to_cover(image, size, anchor) if image is not None else None
    _cache[key] = out
    return out


def fit(folder, name, box):
    """Scale an image to fit inside ``box`` keeping its aspect ratio."""
    key = ("fit", folder, name, box)
    if key in _cache:
        return _cache[key]
    image = load(folder, name)
    out = None
    if image is not None:
        w, h = image.get_size()
        if w > 0 and h > 0:
            scale = min(box[0] / float(w), box[1] / float(h))
            out = pygame.transform.smoothscale(
                image, (max(1, int(w * scale)), max(1, int(h * scale))))
    _cache[key] = out
    return out


def portrait(char_id, size=None):
    return cover("portraits", char_id, size) if size else load("portraits", char_id)


def full_body(char_id):
    return load("characters", char_id)


def clear_cache():
    """Forget loaded art (useful after dropping new files while testing)."""
    _cache.clear()
