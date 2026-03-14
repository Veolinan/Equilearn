# lessons/progress/screen.py
"""
Progress screen — visual reward map for kids and caregivers.

Layout
──────
  Top:    title + overall stats bar
  Middle: three panels side-by-side — Letters, Numbers, Shapes
  Bottom: streak flame + total stars earned

Data
────
  Reads from  data/progress.json  written by ProgressTracker.
  If no data exists yet, all circles show as grey (not started).
"""
import pygame, math, random, time, json, os
from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, gradient_rect, glow_circle,
    draw_text_centered, draw_stars_bg, hold_ring,
    rounded_rect, particle_burst, draw_hand_skeleton,
)
from modules.gesture_engine import GestureEngine, HoldDetector

FPS        = 60
DATA_PATH  = "data/progress.json"

# ── Colour scheme ─────────────────────────────────────────────────────────────
C_MASTERED   = ( 50, 220, 100)   # green  – all stages done
C_STARTED    = ( 50, 180, 255)   # blue   – some progress
C_UNTOUCHED  = ( 60,  55,  90)   # dark   – never tried
C_GOLD       = (255, 210,  40)   # star / streak
C_PANEL_BG   = ( 28,  24,  50)

# ── Data helpers ──────────────────────────────────────────────────────────────
def _load_progress() -> dict:
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _letter_status(data: dict) -> dict[str, str]:
    """Returns {letter: 'mastered'|'started'|'untouched'} for A-Z."""
    import string
    result = {}
    for letter in string.ascii_uppercase:
        entry = data.get(letter, {})
        hist  = entry.get("history", [])
        stage = entry.get("stage", 1)
        if not hist:
            result[letter] = "untouched"
        elif stage >= 5 and any(h.get("accuracy",0) >= 0.8
                                for h in hist if h.get("stage",0) == 5):
            result[letter] = "mastered"
        else:
            result[letter] = "started"
    return result


def _lesson_status(data: dict, lessons: list[str]) -> dict[str, str]:
    """Returns {lesson: 'mastered'|'started'|'untouched'} for numeric lessons."""
    result = {}
    for lesson in lessons:
        entry = data.get(f"lesson_{lesson}", {})
        hist  = entry.get("history", [])
        if not hist:
            result[lesson] = "untouched"
        elif entry.get("correct_streak", 0) >= 5:
            result[lesson] = "mastered"
        else:
            result[lesson] = "started"
    return result


def _status_color(status: str) -> tuple:
    return {"mastered": C_MASTERED, "started": C_STARTED,
            "untouched": C_UNTOUCHED}.get(status, C_UNTOUCHED)


# ── Star drawing ──────────────────────────────────────────────────────────────
def _draw_star(surface, cx, cy, r, color, alpha=255):
    pts = []
    for k in range(10):
        angle  = math.radians(-90 + k * 36)
        radius = r if k % 2 == 0 else r * 0.42
        pts.append((int(cx + radius * math.cos(angle)),
                    int(cy + radius * math.sin(angle))))
    if alpha < 255:
        surf = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
        shifted = [(x - cx + r + 2, y - cy + r + 2) for x, y in pts]
        pygame.draw.polygon(surf, (*color, alpha), shifted)
        surface.blit(surf, (cx - r - 2, cy - r - 2))
    else:
        pygame.draw.polygon(surface, color, pts)


# ── Streak flame ──────────────────────────────────────────────────────────────
def _draw_flame(surface, cx, cy, size, t):
    """Animated flame for streak indicator."""
    for layer, (col, scale, speed, phase) in enumerate([
        ((255, 80,  20), 1.0, 3.0, 0.0),
        ((255, 160, 20), 0.7, 4.0, 0.5),
        ((255, 240, 80), 0.4, 5.0, 1.0),
    ]):
        flicker = 0.85 + 0.15 * math.sin(t * speed + phase)
        w = int(size * scale * 0.6 * flicker)
        h = int(size * scale * flicker)
        pts = [
            (cx,          cy - h),
            (cx - w,      cy),
            (cx - w//2,   cy - h//3),
            (cx,          cy - h//2),
            (cx + w//2,   cy - h//3),
            (cx + w,      cy),
        ]
        surf = pygame.Surface((size*3, size*3), pygame.SRCALPHA)
        shifted = [(x - cx + size, y - cy + size) for x, y in pts]
        pygame.draw.polygon(surf, (*col, 200 - layer*40), shifted)
        surface.blit(surf, (cx - size, cy - size))


# ── Panel drawing ─────────────────────────────────────────────────────────────
def _draw_panel(surface, rect, title, items: list[dict], t: float):
    """
    Draw one subject panel.
    items = [{"label": str, "status": str, "is_circle": bool}]
    """
    # Panel background
    rounded_rect(surface, rect, C_PANEL_BG, radius=L.s(18),
                 border_color=(80, 70, 120), border_width=1)

    # Panel title
    draw_text_centered(surface, title,
                       Fonts.body(L.font_size(26)), Colors.TEXT_WHITE,
                       (rect.centerx, rect.y + L.s(28)))

    # Count mastered
    n_mastered = sum(1 for it in items if it["status"] == "mastered")
    n_total    = len(items)
    pct_text   = f"{n_mastered}/{n_total}"
    draw_text_centered(surface, pct_text,
                       Fonts.label(L.font_size(18)), Colors.TEXT_MUTED,
                       (rect.centerx, rect.y + L.s(50)))

    # Mini progress bar
    bar_rect = pygame.Rect(rect.x + L.s(16), rect.y + L.s(60),
                           rect.w - L.s(32), L.s(8))
    pygame.draw.rect(surface, (50, 44, 80), bar_rect, border_radius=L.s(4))
    if n_total > 0:
        fill_w = int(bar_rect.w * n_mastered / n_total)
        if fill_w > 0:
            fill = pygame.Rect(bar_rect.x, bar_rect.y, fill_w, bar_rect.h)
            pygame.draw.rect(surface, C_MASTERED, fill, border_radius=L.s(4))

    # Items grid
    n      = len(items)
    cols   = min(n, 9)
    rows   = math.ceil(n / cols)
    gap    = L.s(6)
    item_w = (rect.w - L.s(20) - gap*(cols-1)) // cols
    item_h = item_w
    grid_h = rows * item_h + (rows-1) * gap
    gy     = rect.centery - grid_h//2 + L.s(20)
    gx     = rect.x + L.s(10)

    for i, item in enumerate(items):
        col  = i % cols
        row  = i // cols
        ix   = gx + col * (item_w + gap)
        iy   = gy + row * (item_h + gap)
        icx  = ix + item_w//2
        icy  = iy + item_h//2
        r    = item_w // 2 - L.s(2)
        col_ = _status_color(item["status"])

        if item.get("is_circle", True):
            # Circle bubble
            if item["status"] == "mastered":
                glow_circle(surface, (icx, icy), r, col_, layers=2)
            pygame.draw.circle(surface, col_, (icx, icy), r)
            pygame.draw.circle(surface, (255,255,255),
                               (icx, icy), r, max(1, L.s(1)))

            # Star badge for mastered
            if item["status"] == "mastered":
                _draw_star(surface, icx + r - L.s(4), icy - r + L.s(4),
                           L.s(7), C_GOLD)

            # Label inside circle
            if item_w >= L.s(28):
                lf = Fonts.label(L.font_size(14))
                tc = (20, 20, 20) if item["status"] != "untouched" else (140, 130, 180)
                draw_text_centered(surface, item["label"], lf, tc, (icx, icy))
        else:
            # Rectangle pill for longer labels
            pill = pygame.Rect(ix, iy, item_w, item_h)
            rounded_rect(surface, pill, col_, radius=L.s(8))
            if item["status"] == "mastered":
                _draw_star(surface, pill.right - L.s(6), pill.y + L.s(6),
                           L.s(6), C_GOLD)
            lf = Fonts.label(L.font_size(13))
            tc = (20, 20, 20) if item["status"] != "untouched" else (140, 130, 180)
            draw_text_centered(surface, item["label"], lf, tc,
                               (icx, icy))


# ── Main progress screen ──────────────────────────────────────────────────────
class ProgressScreen:

    NUMBER_LESSONS = ["addition", "subtraction", "multiplication",
                      "division", "counting", "odd_even", "fill_missing"]
    SHAPE_LESSONS  = ["shapes", "colors"]

    def __init__(self, ge: GestureEngine):
        self.ge         = ge
        self.back_hold  = HoldDetector(1.5)
        self._clock     = pygame.time.Clock()
        self.t          = 0.0
        self.particles  = []
        self.stars      = [(random.randint(0, L.sw), random.randint(0, L.sh),
                            random.randint(1, 2), random.uniform(0, 6.28))
                           for _ in range(80)]
        # Load once; could reload on each entry for live updates
        self._data      = _load_progress()
        self._letter_st = _letter_status(self._data)
        self._num_st    = _lesson_status(self._data, self.NUMBER_LESSONS)
        self._shape_st  = _lesson_status(self._data, self.SHAPE_LESSONS)

        # Compute overall stats
        self._total_mastered = (
            sum(1 for s in self._letter_st.values()  if s == "mastered") +
            sum(1 for s in self._num_st.values()     if s == "mastered") +
            sum(1 for s in self._shape_st.values()   if s == "mastered")
        )
        self._total_items = (
            len(self._letter_st) + len(self._num_st) + len(self._shape_st)
        )
        self._streak = self._data.get("_streak", 0)

        # Celebration particles on entry if anything mastered
        if self._total_mastered > 0:
            for _ in range(3):
                self.particles += self._emit_celebrate()

    def _emit_celebrate(self):
        cx = random.randint(L.ui_x, L.ui_right)
        cy = random.randint(L.ui_y, L.ui_bottom // 2)
        color = random.choice([C_MASTERED, C_GOLD, Colors.CYAN, Colors.PURPLE])
        return [{"x": cx, "y": cy,
                 "vx": math.cos(a)*s, "vy": math.sin(a)*s - 100,
                 "life": random.uniform(0.8, 1.4),
                 "color": color,
                 "size": random.randint(L.s(4), L.s(10))}
                for a, s in [(random.uniform(0, math.pi*2),
                               random.uniform(60, 200))
                              for _ in range(12)]]

    def run(self, screen) -> str:
        while True:
            dt = self._clock.tick(FPS) / 1000.0
            self.t += dt

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:  return "back"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "back"

            gf    = self.ge.get()
            cx,cy = gf.cursor

            br = pygame.Rect(L.ui_x, L.ui_y, L.s(130), L.s(54))
            _, fired = self.back_hold.update(
                "back", br.collidepoint(cx,cy) and gf.is_pinching)
            if fired:
                return "back"

            self.particles = particle_burst(
                pygame.display.get_surface(), self.particles, dt)

            self._draw(screen, gf)
            pygame.display.flip()

    def _draw(self, screen, gf):
        screen.fill(Colors.BG_DEEP)

        # Nebula background
        for i, (bx, by, br, bc) in enumerate([
            (int(L.sw*.2), int(L.sh*.3), L.s(200), (60,20,140)),
            (int(L.sw*.8), int(L.sh*.7), L.s(180), (20,60,160)),
            (int(L.sw*.5), int(L.sh*.5), L.s(160), (80,20,80)),
        ]):
            ox = int(L.s(12)*math.sin(self.t*.3+i))
            oy = int(L.s(8)*math.cos(self.t*.25+i))
            bl = pygame.Surface((br*2, br*2), pygame.SRCALPHA)
            pygame.draw.circle(bl, (*bc, 28), (br, br), br)
            screen.blit(bl, (bx-br+ox, by-br+oy))

        draw_stars_bg(screen, self.stars, self.t)

        # Safe zone
        ov = pygame.Surface((L.sw, L.sh), pygame.SRCALPHA)
        pygame.draw.rect(ov, (255,255,255,12),
                         (L.ui_x, L.ui_y, L.ui_w, L.ui_h),
                         border_radius=L.s(20))
        pygame.draw.rect(ov, (255,255,255,28),
                         (L.ui_x, L.ui_y, L.ui_w, L.ui_h),
                         width=1, border_radius=L.s(20))
        screen.blit(ov, (0,0))

        # Back button
        br   = pygame.Rect(L.ui_x, L.ui_y, L.s(130), L.s(54))
        ba   = br.collidepoint(*gf.cursor) and gf.is_pinching
        rounded_rect(screen, br,
                     Colors.BG_CARD_HOVER if ba else Colors.BG_CARD,
                     radius=L.s(14),
                     border_color=Colors.PURPLE_LIGHT if ba else None)
        draw_text_centered(screen, "← Back",
                           Fonts.body(L.font_size(24)), Colors.TEXT_LIGHT,
                           br.center)
        bst = self.back_hold._start.get("back")
        if bst:
            hold_ring(screen, br.center, L.s(28),
                      min((time.time()-bst)/1.5, 1.0), Colors.PURPLE_LIGHT)

        # Title
        y_title = L.ui_y + L.s(36)
        draw_text_centered(screen, "My Progress",
                           Fonts.title(L.font_size(52)), Colors.TEXT_WHITE,
                           (L.cx, y_title),
                           shadow=True, shadow_color=(60,30,120))

        # Overall progress bar
        bar_y  = y_title + L.s(42)
        bar_w  = int(L.ui_w * 0.6)
        bar_h  = L.s(16)
        bar_x  = L.cx - bar_w // 2
        bar_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(screen, (50,44,80), bar_rect, border_radius=L.s(8))
        if self._total_items > 0 and self._total_mastered > 0:
            fw = int(bar_w * self._total_mastered / self._total_items)
            pygame.draw.rect(screen, C_MASTERED,
                             pygame.Rect(bar_x, bar_y, fw, bar_h),
                             border_radius=L.s(8))
        draw_text_centered(
            screen,
            f"{self._total_mastered} of {self._total_items} topics mastered",
            Fonts.label(L.font_size(20)), Colors.TEXT_MUTED,
            (L.cx, bar_y + bar_h + L.s(14)))

        # Streak
        if self._streak > 0:
            sx = L.ui_right - L.s(80)
            sy = y_title
            _draw_flame(screen, sx, sy, L.s(32), self.t)
            draw_text_centered(screen, f"{self._streak}",
                               Fonts.title(L.font_size(32)), C_GOLD,
                               (sx, sy + L.s(36)))
            draw_text_centered(screen, "day streak",
                               Fonts.label(L.font_size(16)), Colors.TEXT_MUTED,
                               (sx, sy + L.s(52)))

        # ── Three subject panels ───────────────────────────────────────────
        panel_y  = bar_y + bar_h + L.s(46)
        panel_h  = L.ui_bottom - panel_y - L.s(10)
        gap      = L.s(16)
        panel_w  = (L.ui_w - gap * 2) // 3

        panels = [
            {
                "title": "Letters  🔤",
                "rect":  pygame.Rect(L.ui_x, panel_y, panel_w, panel_h),
                "items": [{"label": lt, "status": self._letter_st[lt],
                           "is_circle": True}
                          for lt in sorted(self._letter_st)],
            },
            {
                "title": "Numbers  🔢",
                "rect":  pygame.Rect(L.ui_x + panel_w + gap, panel_y,
                                     panel_w, panel_h),
                "items": [{"label": n.replace("_"," ").title(),
                           "status": self._num_st[n], "is_circle": False}
                          for n in self.NUMBER_LESSONS],
            },
            {
                "title": "Shapes & Colors  🔷",
                "rect":  pygame.Rect(L.ui_x + (panel_w + gap)*2, panel_y,
                                     panel_w, panel_h),
                "items": [{"label": s.title(),
                           "status": self._shape_st[s], "is_circle": False}
                          for s in self.SHAPE_LESSONS],
            },
        ]

        for panel in panels:
            _draw_panel(screen, panel["rect"], panel["title"],
                        panel["items"], self.t)

        # Legend
        leg_y = L.ui_bottom - L.s(6)
        for color, label, lx in [
            (C_MASTERED,  "Mastered", L.ui_x),
            (C_STARTED,   "Started",  L.ui_x + L.s(130)),
            (C_UNTOUCHED, "Not yet",  L.ui_x + L.s(250)),
        ]:
            pygame.draw.circle(screen, color,
                               (lx + L.s(8), leg_y), L.s(7))
            draw_text_centered(screen, label,
                               Fonts.label(L.font_size(16)),
                               Colors.TEXT_MUTED,
                               (lx + L.s(46), leg_y))

        # Particles
        self.particles = particle_burst(screen, self.particles, 0)

        # Cursor + skeleton
        if gf.hand_visible:
            draw_hand_skeleton(screen, gf.landmarks, gf.is_pinching)
            pcx, pcy = gf.cursor
            if gf.is_pinching:
                glow_circle(screen, (pcx,pcy), L.s(14), Colors.CYAN, layers=3)
            else:
                pygame.draw.circle(screen, Colors.TEXT_WHITE,
                                   (pcx,pcy), L.s(10), 2)
                pygame.draw.circle(screen, Colors.CYAN, (pcx,pcy), L.s(4))


# ── Public entry ──────────────────────────────────────────────────────────────
def run_progress(screen, ge: GestureEngine) -> str:
    return ProgressScreen(ge).run(screen)
