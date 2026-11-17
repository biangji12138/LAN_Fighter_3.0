"""Stateless drawing primitives.

Each function takes the target surface and the font cache explicitly so it can
be used from GameApp without touching its internal state. Interactive widgets
(button, input) still live on GameApp because they own hover / focus state.
"""
import pygame

from .theme import MUTED, PANEL_HI, WHITE, shade


def text(screen, fonts, value, x, y, size=22, color=WHITE, center=False, shadow=False):
    """Render ``value`` at (x, y); returns the blitted rect."""
    surface = fonts[size].render(str(value), True, color)
    rect = surface.get_rect(center=(x, y)) if center else surface.get_rect(topleft=(x, y))
    if shadow:
        dark = fonts[size].render(str(value), True, shade(color, .22))
        screen.blit(dark, rect.move(2, 2))
    screen.blit(surface, rect)
    return rect


def rect(screen, x, y, w, h, color, radius=16, border=None):
    """Draw a rounded rectangle; returns the pygame Rect used."""
    r = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, color, r, border_radius=radius)
    if border:
        pygame.draw.rect(screen, border, r, 2, border_radius=radius)
    return r


def key_pills(screen, fonts, keys, x, y, color, size=18, sep="\u2192"):
    """Draw a row of key caps joined by arrows; returns the right edge."""
    typed = fonts[size]
    for index, key in enumerate(keys):
        if index:
            mark_w = typed.size(str(sep))[0]
            text(screen, fonts, sep, x + mark_w // 2, y, size, MUTED, True)
            x += mark_w + 10
        width = typed.size(str(key))[0] + 24
        rect(screen, x, y - 13, width, 26, PANEL_HI, 9, color)
        text(screen, fonts, key, x + width // 2, y, size, WHITE, True)
        x += width
    return x


def panel(screen, x, y, w, h, color, radius=18, border=(45, 62, 92), accent=None,
          shadow=True):
    """Layered panel: soft drop shadow, lighter top face, crisp rim."""
    r = pygame.Rect(x, y, w, h)
    if shadow:
        pygame.draw.rect(screen, (5, 9, 17), r.move(0, 6), border_radius=radius)
    pygame.draw.rect(screen, shade(color, .78), r, border_radius=radius)
    face = pygame.Rect(x + 2, y + 2, w - 4, h - 4)
    pygame.draw.rect(screen, color, face, border_radius=max(3, radius - 2))
    sheen = pygame.Rect(x + 4, y + 3, w - 8, max(8, int(h * .22)))
    pygame.draw.rect(screen, shade(color, 1.13), sheen, border_radius=max(3, radius - 4))
    pygame.draw.rect(screen, border, r, 2, border_radius=radius)
    pygame.draw.line(screen, shade(color, 1.35),
                     (x + 18, y + 3), (x + w - 18, y + 3), 1)
    if accent:
        pygame.draw.line(screen, accent, (x + 20, y + 1), (x + w - 20, y + 1), 2)
        pygame.draw.circle(screen, accent, (x + 12, y + 1), 3)
        pygame.draw.circle(screen, accent, (x + w - 12, y + 1), 3)
    return r
