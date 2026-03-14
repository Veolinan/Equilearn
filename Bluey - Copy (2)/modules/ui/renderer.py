# modules/ui/renderer.py
"""
Low-level Pygame drawing primitives.
Everything visual in the app goes through here so styles stay consistent.
"""
import pygame
import math


# ── Design tokens ─────────────────────────────────────────────────────────
class Colors:
    # Background layers
    BG_DEEP       = (15,  12,  30)    # deep navy — main background
    BG_CARD       = (28,  24,  50)    # slightly lighter — cards
    BG_CARD_HOVER = (40,  35,  70)    # hovered card

    # Brand
    PURPLE        = (130,  80, 255)
    PURPLE_LIGHT  = (170, 130, 255)
    PINK          = (255,  80, 160)
    CYAN          = ( 60, 220, 255)
    CYAN_DARK     = ( 20, 160, 200)
    YELLOW        = (255, 220,  50)
    YELLOW_DARK   = (200, 160,  10)
    GREEN         = ( 60, 220, 120)
    GREEN_DARK    = ( 20, 160,  70)
    RED           = (255,  80,  80)
    ORANGE        = (255, 160,  40)

    # Text
    TEXT_WHITE    = (255, 255, 255)
    TEXT_LIGHT    = (200, 195, 230)
    TEXT_MUTED    = (130, 120, 160)
    TEXT_DARK     = ( 20,  15,  35)

    # Semantic
    CORRECT       = ( 60, 220, 120)
    WRONG         = (255,  80,  80)
    HOLD_RING     = ( 60, 220, 255)

    # Stars / rewards
    STAR_GOLD     = (255, 210,  40)
    STAR_GRAY     = ( 80,  75, 100)


class Fonts:
    _loaded: dict = {}

    @classmethod
    def get(cls, name: str, size: int) -> pygame.font.Font:
        key = (name, size)
        if key not in cls._loaded:
            try:
                cls._loaded[key] = pygame.font.Font(f"assets/fonts/{name}.ttf", size)
            except Exception:
                cls._loaded[key] = pygame.font.Font(None, size)
        return cls._loaded[key]

    @classmethod
    def title(cls, size: int = 72):
        return cls.get("Nunito-ExtraBold", size)

    @classmethod
    def body(cls, size: int = 36):
        return cls.get("Nunito-SemiBold", size)

    @classmethod
    def label(cls, size: int = 28):
        return cls.get("Nunito-Regular", size)


# ── Drawing helpers ────────────────────────────────────────────────────────

def rounded_rect(surface: pygame.Surface,
                 rect: pygame.Rect,
                 color: tuple,
                 radius: int = 24,
                 border_color: tuple | None = None,
                 border_width: int = 3):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border_color:
        pygame.draw.rect(surface, border_color, rect,
                         width=border_width, border_radius=radius)


def gradient_rect(surface: pygame.Surface,
                  rect: pygame.Rect,
                  color_top: tuple,
                  color_bot: tuple,
                  radius: int = 24):
    """Vertical gradient drawn as thin horizontal lines, clipped to a rounded rect."""
    clip_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    h = rect.height
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(color_top[0] + t * (color_bot[0] - color_top[0]))
        g = int(color_top[1] + t * (color_bot[1] - color_top[1]))
        b = int(color_top[2] + t * (color_bot[2] - color_top[2]))
        pygame.draw.line(clip_surf, (r, g, b), (0, y), (rect.width, y))
    # Mask to rounded rect
    mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 0))
    pygame.draw.rect(mask, (255, 255, 255, 255),
                     mask.get_rect(), border_radius=radius)
    clip_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(clip_surf, rect.topleft)


def glow_circle(surface: pygame.Surface,
                center: tuple,
                radius: int,
                color: tuple,
                layers: int = 4):
    """Soft glow by drawing concentric transparent circles."""
    glow = pygame.Surface((radius * 2 + layers * 8,
                           radius * 2 + layers * 8), pygame.SRCALPHA)
    cx = cy = radius + layers * 4
    for i in range(layers, 0, -1):
        alpha = int(60 / i)
        r = radius + i * 4
        pygame.draw.circle(glow, (*color, alpha), (cx, cy), r)
    pygame.draw.circle(glow, color, (cx, cy), radius)
    surface.blit(glow, (center[0] - cx, center[1] - cy))


def draw_text_centered(surface: pygame.Surface,
                       text: str,
                       font: pygame.font.Font,
                       color: tuple,
                       center: tuple,
                       shadow: bool = False,
                       shadow_color: tuple = (0, 0, 0)):
    if shadow:
        s = font.render(text, True, shadow_color)
        sr = s.get_rect(center=(center[0] + 3, center[1] + 3))
        surface.blit(s, sr)
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=center)
    surface.blit(rendered, rect)
    return rect


def draw_stars_bg(surface: pygame.Surface,
                  stars: list,
                  t: float):
    """Animated twinkle star field. stars = list of (x, y, size, phase)."""
    for x, y, size, phase in stars:
        alpha = int(128 + 100 * math.sin(t * 1.5 + phase))
        alpha = max(30, min(255, alpha))
        star_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(star_surf, (255, 255, 255, alpha), (size, size), size)
        surface.blit(star_surf, (x - size, y - size))


def hold_ring(surface: pygame.Surface,
              center: tuple,
              radius: int,
              progress: float,
              color: tuple = Colors.HOLD_RING,
              thickness: int = 6):
    """Arc ring showing hold-to-select progress (0.0–1.0)."""
    if progress <= 0:
        return
    # Background ring
    pygame.draw.circle(surface, Colors.BG_CARD, center, radius, thickness)
    # Progress arc  — use small line segments
    start_angle = -math.pi / 2
    end_angle   = start_angle + 2 * math.pi * progress
    steps       = max(3, int(60 * progress))
    pts = []
    for i in range(steps + 1):
        a = start_angle + (end_angle - start_angle) * i / steps
        px = int(center[0] + radius * math.cos(a))
        py = int(center[1] + radius * math.sin(a))
        pts.append((px, py))
    if len(pts) >= 2:
        pygame.draw.lines(surface, color, False, pts, thickness)


def draw_hand_skeleton(surface: pygame.Surface,
                       landmarks: list,
                       pinching: bool = False):
    """
    Draw a clean hand skeleton overlay on a Pygame surface.
    landmarks = list of 21 (x, y) screen-pixel tuples.
    Knuckle joints glow cyan when pinching.
    """
    if not landmarks or len(landmarks) < 21:
        return

    CONNECTIONS = [
        (0,1),(1,2),(2,3),(3,4),           # thumb
        (0,5),(5,6),(6,7),(7,8),           # index
        (0,9),(9,10),(10,11),(11,12),      # middle
        (0,13),(13,14),(14,15),(15,16),    # ring
        (0,17),(17,18),(18,19),(19,20),    # pinky
        (5,9),(9,13),(13,17),(0,17),       # palm
    ]

    bone_color  = (80, 220, 255) if pinching else (120, 100, 200)
    joint_color = (0, 240, 200)  if pinching else (160, 140, 240)
    tip_color   = (255, 255, 255)
    tips        = {4, 8, 12, 16, 20}

    # Bones
    bone_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for a, b in CONNECTIONS:
        ax, ay = landmarks[a]
        bx, by = landmarks[b]
        pygame.draw.line(bone_surf, (*bone_color, 160), (ax, ay), (bx, by), 2)
    surface.blit(bone_surf, (0, 0))

    # Joints
    for i, (x, y) in enumerate(landmarks):
        if i in tips:
            # Fingertip — white dot with coloured ring
            pygame.draw.circle(surface, (*joint_color, 200), (x, y), 7)
            pygame.draw.circle(surface, tip_color, (x, y), 4)
        elif i == 0:
            # Wrist — slightly larger
            pygame.draw.circle(surface, (*joint_color, 180), (x, y), 6)
        else:
            pygame.draw.circle(surface, (*joint_color, 160), (x, y), 4)

    # Pinch highlight — bright ring connecting thumb tip + index tip
    if pinching:
        tx, ty = landmarks[4]
        ix, iy = landmarks[8]
        mid    = ((tx + ix) // 2, (ty + iy) // 2)
        pygame.draw.line(surface, (0, 255, 200), (tx, ty), (ix, iy), 3)
        glow_circle(surface, mid, 10, (0, 255, 200), layers=3)


def draw_hold_loading_screen(surface: pygame.Surface,
                              label: str,
                              progress: float,
                              color: tuple,
                              t: float):
    """
    Full-screen hold-to-open loading overlay.
    progress = 0.0 → 1.0
    Draws a semi-transparent overlay with an arc ring + label + countdown.
    """
    # Dim overlay
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((10, 8, 20, int(200 * min(progress * 3, 1.0))))
    surface.blit(overlay, (0, 0))

    if progress <= 0:
        return

    w, h   = surface.get_size()
    cx, cy = w // 2, h // 2
    radius = 90

    # Outer static ring
    pygame.draw.circle(surface, (50, 44, 80), (cx, cy), radius, 8)

    # Animated fill arc
    start_angle = -math.pi / 2
    end_angle   = start_angle + 2 * math.pi * progress
    steps       = max(4, int(80 * progress))
    pts = [(cx, cy)]
    for i in range(steps + 1):
        a  = start_angle + (end_angle - start_angle) * i / steps
        px = int(cx + radius * math.cos(a))
        py = int(cy + radius * math.sin(a))
        pts.append((px, py))
    if len(pts) >= 3:
        arc_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(arc_surf, (*color, 60), pts)
        surface.blit(arc_surf, (0, 0))

    # Arc stroke on top
    arc_pts = []
    for i in range(steps + 1):
        a  = start_angle + (end_angle - start_angle) * i / steps
        arc_pts.append((int(cx + radius * math.cos(a)),
                        int(cy + radius * math.sin(a))))
    if len(arc_pts) >= 2:
        pygame.draw.lines(surface, color, False, arc_pts, 8)

    # Pulsing centre circle
    pulse = 0.7 + 0.3 * math.sin(t * 8)
    inner_r = int(radius * 0.55 * pulse)
    inner_surf = pygame.Surface((inner_r * 2 + 20, inner_r * 2 + 20), pygame.SRCALPHA)
    pygame.draw.circle(inner_surf, (*color, 80),
                       (inner_r + 10, inner_r + 10), inner_r)
    surface.blit(inner_surf, (cx - inner_r - 10, cy - inner_r - 10))

    # Percentage
    try:
        from modules.ui.renderer import Fonts
        pct_font = Fonts.title(52)
    except Exception:
        pct_font = pygame.font.Font(None, 52)
    pct_text = f"{int(progress * 100)}%"
    rendered = pct_font.render(pct_text, True, (255, 255, 255))
    surface.blit(rendered, rendered.get_rect(center=(cx, cy)))

    # Label below ring
    try:
        lbl_font = Fonts.body(30)
    except Exception:
        lbl_font = pygame.font.Font(None, 30)
    lbl = lbl_font.render(f"Opening  {label}…", True, color)
    surface.blit(lbl, lbl.get_rect(center=(cx, cy + radius + 36)))

    # "Hold still" hint — fades in after 0.3s
    if progress > 0.15:
        try:
            hint_font = Fonts.label(22)
        except Exception:
            hint_font = pygame.font.Font(None, 22)
        alpha = int(255 * min((progress - 0.15) / 0.2, 1.0))
        hint  = hint_font.render("Keep pinching…", True,
                                  (180, 170, 220))
        hint.set_alpha(alpha)
        surface.blit(hint, hint.get_rect(center=(cx, cy + radius + 72)))


def particle_burst(surface: pygame.Surface,
                   particles: list,
                   dt: float) -> list:
    """
    Animate + draw celebration particles.
    particles = list of dicts with keys: x, y, vx, vy, life, color, size
    Returns updated (alive) particles list.
    """
    alive = []
    for p in particles:
        p["life"] -= dt
        if p["life"] <= 0:
            continue
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["vy"] += 400 * dt   # gravity
        alpha = int(255 * p["life"])
        s = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*p["color"], alpha),
                           (p["size"], p["size"]), p["size"])
        surface.blit(s, (int(p["x"]) - p["size"], int(p["y"]) - p["size"]))
        alive.append(p)
    return alive
