# main_menu.py
import pygame, math, random, time

from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, rounded_rect, gradient_rect,
    glow_circle, draw_text_centered, draw_stars_bg,
    hold_ring, particle_burst, draw_hand_skeleton,
    draw_hold_loading_screen,
)
from modules.gesture_engine import GestureEngine, GestureState, HoldDetector

FPS    = 60
HOLD_S = 2.0

CARDS = [
    {"id": "letters",  "label": "Letters",  "emoji": "🔤",
     "color_a": (130, 80, 255),  "color_b": (80, 40, 180)},
    {"id": "numbers",  "label": "Numbers",  "emoji": "🔢",
     "color_a": (60, 180, 255),  "color_b": (20, 100, 200)},
    {"id": "shapes",   "label": "Shapes",   "emoji": "🔷",
     "color_a": (255, 120, 60),  "color_b": (180, 60, 20)},
    {"id": "drawing",  "label": "Drawing",  "emoji": "🎨",
     "color_a": (255, 80, 160),  "color_b": (180, 30, 100)},
    {"id": "progress", "label": "Progress", "emoji": "⭐",
     "color_a": (60, 220, 120),  "color_b": (20, 140, 70)},
    {"id": "quit",     "label": "Quit",     "emoji": "👋",
     "color_a": (90, 80, 110),   "color_b": (50, 44, 70)},
]


def _card_rects() -> list[pygame.Rect]:
    """Compute card rects from current Layout — called each frame so resizes work."""
    return L.card_grid(len(CARDS), cols=3)


def _emit_particles(cx, cy, color, n=22):
    return [{"x": cx, "y": cy,
             "vx": math.cos(a) * s, "vy": math.sin(a) * s - 120,
             "life": random.uniform(0.6, 1.0),
             "color": color, "size": random.randint(L.s(4), L.s(10))}
            for a, s in [(random.uniform(0, math.pi*2),
                          random.uniform(80, 280)) for _ in range(n)]]


def _gen_stars():
    return [(random.randint(0, L.sw), random.randint(0, L.sh),
             random.randint(1, 3), random.uniform(0, math.pi * 2))
            for _ in range(140)]


def _draw_mascot(surface, t):
    """Procedural robot mascot — scales with L."""
    r      = L.s(44)
    cx     = L.ui_x + r + L.s(10)
    cy_base= L.ui_bottom - r - L.s(10)
    bob    = int(L.s(6) * math.sin(t * 2.0))
    cy     = cy_base + bob

    # Shadow
    sh_s = pygame.Surface((r*2+4, L.s(20)), pygame.SRCALPHA)
    pygame.draw.ellipse(sh_s, (0,0,0,60), sh_s.get_rect())
    surface.blit(sh_s, (cx - r - 2, cy_base + r - L.s(4)))

    pygame.draw.circle(surface, (60, 50, 90), (cx, cy), r)
    pygame.draw.circle(surface, Colors.PURPLE, (cx, cy), r, max(2, L.s(3)))

    # Face
    fw, fh = int(r*1.2), int(r*0.85)
    pygame.draw.ellipse(surface, (28,24,50), (cx-fw//2, cy-fh//2, fw, fh))

    blink = math.sin(t * 0.4) > 0.96
    ey    = cy - L.s(8)
    ew    = max(4, L.s(6))
    eh    = max(2, L.s(4)) if blink else max(4, L.s(12))
    for ex in [cx - L.s(10), cx + L.s(10)]:
        pygame.draw.ellipse(surface, Colors.CYAN, (ex-ew//2, ey-eh//2, ew, eh))

    pygame.draw.arc(surface, Colors.YELLOW,
                    (cx-L.s(12), cy+L.s(5), L.s(24), L.s(14)),
                    math.pi, 2*math.pi, max(2, L.s(3)))

    pygame.draw.line(surface, Colors.PURPLE_LIGHT,
                     (cx, cy-r), (cx, cy-r-L.s(16)), max(2, L.s(3)))
    glow_circle(surface, (cx, cy-r-L.s(20)), L.s(6), Colors.CYAN, layers=3)

    aa = 0.3 * math.sin(t * 1.5)
    for sign in [-1, 1]:
        ax = int(cx + sign*(r + L.s(18)*math.cos(aa)))
        ay = int(cy + L.s(8)*math.sin(aa))
        pygame.draw.line(surface, Colors.PURPLE,
                         (cx + sign*int(r*0.86), cy+L.s(5)), (ax, ay), max(4, L.s(8)))
        pygame.draw.circle(surface, Colors.PURPLE_LIGHT, (ax, ay), max(4, L.s(8)))


def _draw_safe_zone(surface):
    """Visual indicator: full screen is gesture zone, inner rect is UI zone."""
    overlay = pygame.Surface((L.sw, L.sh), pygame.SRCALPHA)
    # Full screen very faint tint — shows gesture area
    pygame.draw.rect(overlay, (100, 80, 200, 6), (0, 0, L.sw, L.sh))
    # UI zone brighter fill
    pygame.draw.rect(overlay, (255, 255, 255, 12),
                     (L.ui_x, L.ui_y, L.ui_w, L.ui_h),
                     border_radius=L.s(20))
    # UI zone border
    pygame.draw.rect(overlay, (255, 255, 255, 28),
                     (L.ui_x, L.ui_y, L.ui_w, L.ui_h),
                     width=1, border_radius=L.s(20))
    # Corner hints showing gesture margin
    for x, y in [(0,0),(L.sw-L.s(40),0),(0,L.sh-L.s(40)),(L.sw-L.s(40),L.sh-L.s(40))]:
        pygame.draw.rect(overlay, (120,100,220,25),
                         (x, y, L.s(40), L.s(40)), border_radius=L.s(6))
    surface.blit(overlay, (0, 0))


class MainMenu:
    def __init__(self, ge: GestureEngine):
        self.ge          = ge
        self.hold        = HoldDetector(hold_seconds=HOLD_S)
        self.stars       = _gen_stars()
        self.particles   = []
        self.hover_idx   = -1
        self.card_scales = [1.0] * len(CARDS)
        self.t           = 0.0
        self.result      = None
        self._clock      = pygame.time.Clock()
        self._emoji_font = pygame.font.SysFont("Segoe UI Emoji", L.font_size(52))

    def run(self, screen: pygame.Surface) -> str:
        self.result = None
        while self.result is None:
            dt = self._clock.tick(FPS) / 1000.0
            self.t += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT:           return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:    return "quit"
                    if event.key == pygame.K_f:         self._toggle_fullscreen(screen)
            gf = self.ge.get()
            self._update(gf, dt)
            self._draw(screen, gf)
            pygame.display.flip()
        return self.result

    def _toggle_fullscreen(self, screen):
        pygame.display.toggle_fullscreen()

    def _update(self, gf, dt):
        self.particles = particle_burst(pygame.display.get_surface(),
                                        self.particles, dt)
        cx, cy   = gf.cursor
        pinching = gf.is_pinching
        rects    = _card_rects()

        new_hover = -1
        for i, rect in enumerate(rects):
            if rect.collidepoint(cx, cy):
                new_hover = i
                break

        for i in range(len(CARDS)):
            target = 1.06 if i == new_hover else 1.0
            self.card_scales[i] += (target - self.card_scales[i]) * 0.18

        self.hover_idx = new_hover

        for i, card in enumerate(CARDS):
            active = (new_hover == i) and pinching
            prog, fired = self.hold.update(card["id"], active)
            if fired:
                r = rects[i]
                self.particles += _emit_particles(r.centerx, r.centery,
                                                  card["color_a"])
                self.result = card["id"]

    def _draw(self, screen: pygame.Surface, gf):
        screen.fill(Colors.BG_DEEP)

        # Drifting nebula blobs
        for i, (bx, by, br, bc) in enumerate([
            (int(L.sw*0.2), int(L.sh*0.25), L.s(180), (80,30,160)),
            (int(L.sw*0.8), int(L.sh*0.65), L.s(220), (30,80,180)),
            (int(L.sw*0.5), int(L.sh*0.80), L.s(150), (160,30,100)),
        ]):
            ox = int(L.s(15) * math.sin(self.t * 0.3 + i))
            oy = int(L.s(10) * math.cos(self.t * 0.25 + i))
            blob = pygame.Surface((br*2, br*2), pygame.SRCALPHA)
            pygame.draw.circle(blob, (*bc, 35), (br, br), br)
            screen.blit(blob, (bx-br+ox, by-br+oy))

        draw_stars_bg(screen, self.stars, self.t)
        _draw_safe_zone(screen)

        # Title
        title_font = Fonts.title(L.font_size(62))
        y_title    = L.ui_y + L.s(36) + int(L.s(4) * math.sin(self.t * 1.2))
        draw_text_centered(screen, "Touchless Tutor", title_font,
                           Colors.TEXT_WHITE, (L.cx, y_title),
                           shadow=True, shadow_color=(60,30,120))

        draw_text_centered(screen, "Point  ✦  Hold  ✦  Learn",
                           Fonts.body(L.font_size(24)), Colors.TEXT_MUTED,
                           (L.cx, y_title + L.s(46)))

        # Cards
        rects = _card_rects()
        for i, card in enumerate(CARDS):
            self._draw_card(screen, i, card, rects[i])

        _draw_mascot(screen, self.t)
        self._draw_debug(screen, gf)
        self._draw_cursor(screen, gf)
        self.particles = particle_burst(screen, self.particles, 0)

    def _draw_card(self, screen, i, card, base_rect):
        scale = self.card_scales[i]
        w = int(base_rect.w * scale)
        h = int(base_rect.h * scale)
        rect = pygame.Rect(base_rect.centerx - w//2,
                           base_rect.centery - h//2, w, h)
        is_hover = (i == self.hover_idx)

        # Shadow
        sh_s = pygame.Surface((w+L.s(16), h+L.s(16)), pygame.SRCALPHA)
        pygame.draw.rect(sh_s, (0,0,0,80), sh_s.get_rect(), border_radius=L.s(28))
        screen.blit(sh_s, (rect.x-L.s(8), rect.y+L.s(8)))

        gradient_rect(screen, rect, card["color_a"], card["color_b"],
                      radius=L.s(24))

        if is_hover:
            pygame.draw.rect(screen, (255,255,255),
                             rect, width=3, border_radius=L.s(24))

        em = self._emoji_font.render(card["emoji"], True, (255,255,255))
        screen.blit(em, em.get_rect(center=(rect.centerx, rect.centery - L.s(18))))

        draw_text_centered(screen, card["label"],
                           Fonts.body(L.font_size(28)), Colors.TEXT_WHITE,
                           (rect.centerx, rect.centery + L.s(28)),
                           shadow=True, shadow_color=(0,0,0))

        if is_hover and self.ge.get().is_pinching:
            start = self.hold._start.get(card["id"])
            if start:
                prog = min((time.time()-start)/HOLD_S, 1.0)
                hold_ring(screen, rect.center, L.s(36), prog)

    def _draw_debug(self, screen, gf):
        lines = [f"state: {gf.state}",
                 f"hand:  {'YES' if gf.hand_visible else 'NO'}",
                 f"res:   {L.sw}×{L.sh}",
                 f"ui:    {L.ui_w}×{L.ui_h}"]
        if gf.landmarks and len(gf.landmarks) >= 10:
            lm = gf.landmarks
            hs = math.hypot(lm[0][0]-lm[9][0], lm[0][1]-lm[9][1])
            pd = math.hypot(lm[4][0]-lm[8][0], lm[4][1]-lm[8][1])
            lines.append(f"pinch: {pd/max(hs,1):.3f}  (<0.28)")
        f   = pygame.font.Font(None, L.font_size(22))
        x,y = L.sw - L.s(240), L.s(8)
        bg  = pygame.Surface((L.s(234), len(lines)*L.s(22)+L.s(8)), pygame.SRCALPHA)
        bg.fill((0,0,0,140))
        screen.blit(bg, (x-4, y-4))
        for i, line in enumerate(lines):
            c = (0,255,180) if gf.is_pinching and "pinch" in line else (200,200,200)
            screen.blit(f.render(line, True, c), (x, y + i*L.s(22)))

    def _draw_cursor(self, screen, gf):
        if not gf.hand_visible:
            return
        draw_hand_skeleton(screen, gf.landmarks, gf.is_pinching)
        cx, cy = gf.cursor
        if gf.is_pinching:
            glow_circle(screen, (cx,cy), L.s(14), Colors.CYAN, layers=3)
        else:
            pygame.draw.circle(screen, Colors.TEXT_WHITE, (cx,cy), L.s(10), 2)
            pygame.draw.circle(screen, Colors.CYAN, (cx,cy), L.s(4))

        if gf.is_pinching and self.hover_idx >= 0:
            card  = CARDS[self.hover_idx]
            start = self.hold._start.get(card["id"])
            if start:
                prog = min((time.time()-start)/HOLD_S, 1.0)
                if prog > 0:
                    draw_hold_loading_screen(screen, card["label"],
                                             prog, card["color_a"], self.t)


def run_main_menu(screen: pygame.Surface, ge: GestureEngine) -> str:
    return MainMenu(ge).run(screen)
