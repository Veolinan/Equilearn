# lessons/numbers/menu.py
import pygame, math, random, time

from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, gradient_rect, glow_circle,
    draw_text_centered, draw_stars_bg, hold_ring,
    particle_burst, draw_hand_skeleton,
    draw_hold_loading_screen, rounded_rect,
)
from modules.gesture_engine import GestureEngine, HoldDetector

FPS    = 60
HOLD_S = 2.0

ITEMS = [
    {"id": "addition",      "label": "Addition",      "emoji": "➕",
     "color_a": (130, 80,255), "color_b": ( 80, 40,180)},
    {"id": "subtraction",   "label": "Subtraction",   "emoji": "➖",
     "color_a": ( 60,180,255), "color_b": ( 20,100,200)},
    {"id": "multiplication","label": "Multiply",      "emoji": "✖️",
     "color_a": (255,120, 60), "color_b": (180, 60, 20)},
    {"id": "division",      "label": "Division",      "emoji": "➗",
     "color_a": (255, 80,160), "color_b": (180, 30,100)},
    {"id": "counting",      "label": "Counting",      "emoji": "🔢",
     "color_a": ( 60,220,120), "color_b": ( 20,140, 70)},
    {"id": "odd_even",      "label": "Odd / Even",    "emoji": "⚖️",
     "color_a": (255,200, 40), "color_b": (180,130, 10)},
    {"id": "fill_missing",  "label": "Fill Missing",  "emoji": "❓",
     "color_a": (160, 60,220), "color_b": ( 90, 20,160)},
    {"id": "back",          "label": "Back",          "emoji": "👈",
     "color_a": ( 70, 65, 90), "color_b": ( 40, 38, 60)},
]


def _emit(cx, cy, color, n=18):
    return [{"x":cx,"y":cy,
             "vx":math.cos(a)*s,"vy":math.sin(a)*s-100,
             "life":random.uniform(0.5,0.9),
             "color":color,"size":random.randint(L.s(4),L.s(9))}
            for a,s in [(random.uniform(0,math.pi*2),
                         random.uniform(60,220)) for _ in range(n)]]


class NumbersMenu:
    def __init__(self, ge: GestureEngine):
        self.ge          = ge
        self.hold        = HoldDetector(HOLD_S)
        self.stars       = [(random.randint(0,L.sw), random.randint(0,L.sh),
                             random.randint(1,2), random.uniform(0,6.28))
                            for _ in range(100)]
        self.particles   = []
        self.hover_idx   = -1
        self.scales      = [1.0]*len(ITEMS)
        self.t           = 0.0
        self.result      = None
        self._clock      = pygame.time.Clock()
        self._efont      = pygame.font.SysFont("Segoe UI Emoji", L.font_size(44))
        from modules.ui.scroll import ScrollHandler
        self._scroll     = ScrollHandler()
        L.reset_scroll()

    def run(self, screen) -> str:
        self.result = None
        while self.result is None:
            dt = self._clock.tick(FPS) / 1000.0
            self.t += dt
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:           return "back"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "back"
            gf = self.ge.get()
            self._update(gf, dt)
            self._draw(screen, gf)
            pygame.display.flip()
        return self.result

    def _update(self, gf, dt):
        self.particles = particle_burst(pygame.display.get_surface(),
                                        self.particles, dt)
        self._scroll.update(gf)
        cx, cy   = gf.cursor
        pinching = gf.is_pinching
        rects    = L.card_grid(len(ITEMS), cols=4)

        new_hover = next((i for i,r in enumerate(rects)
                          if r.collidepoint(cx,cy)), -1)
        self.hover_idx = new_hover

        for i in range(len(ITEMS)):
            t_ = 1.06 if i == new_hover else 1.0
            self.scales[i] += (t_ - self.scales[i]) * 0.18

        for i, item in enumerate(ITEMS):
            _, fired = self.hold.update(item["id"], (new_hover==i) and pinching)
            if fired:
                r = rects[i]
                self.particles += _emit(r.centerx, r.centery, item["color_a"])
                self.result = item["id"]

    def _draw(self, screen, gf):
        screen.fill(Colors.BG_DEEP)

        # Nebula
        for i,(bx,by,br,bc) in enumerate([
            (int(L.sw*.25),int(L.sh*.3),L.s(160),(60,20,140)),
            (int(L.sw*.75),int(L.sh*.7),L.s(180),(20,60,160)),
        ]):
            ox=int(L.s(12)*math.sin(self.t*.4+i))
            oy=int(L.s(8)*math.cos(self.t*.3+i))
            bl=pygame.Surface((br*2,br*2),pygame.SRCALPHA)
            pygame.draw.circle(bl,(*bc,30),(br,br),br)
            screen.blit(bl,(bx-br+ox,by-br+oy))

        draw_stars_bg(screen, self.stars, self.t)

        # Safe zone
        ov=pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
        pygame.draw.rect(ov,(255,255,255,12),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         border_radius=L.s(20))
        pygame.draw.rect(ov,(255,255,255,28),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         width=1,border_radius=L.s(20))
        screen.blit(ov,(0,0))

        # Title
        y_title = L.ui_y + L.s(36) + int(L.s(3)*math.sin(self.t*1.2))
        draw_text_centered(screen, "Numbers",
                           Fonts.title(L.font_size(56)), Colors.TEXT_WHITE,
                           (L.cx, y_title), shadow=True,
                           shadow_color=(60,30,120))
        draw_text_centered(screen, "Choose a topic  🔢",
                           Fonts.body(L.font_size(24)), Colors.TEXT_MUTED,
                           (L.cx, y_title + L.s(42)))

        # Cards
        rects = L.card_grid(len(ITEMS), cols=4)
        for i, (item, rect) in enumerate(zip(ITEMS, rects)):
            self._draw_card(screen, i, item, rect)

        self._draw_cursor(screen, gf)
        self._scroll.draw(screen)
        self.particles = particle_burst(screen, self.particles, 0)

    def _draw_card(self, screen, i, item, base_rect):
        sc   = self.scales[i]
        w, h = int(base_rect.w*sc), int(base_rect.h*sc)
        rect = pygame.Rect(base_rect.centerx-w//2,
                           base_rect.centery-h//2, w, h)

        # Shadow
        sh=pygame.Surface((w+L.s(14),h+L.s(14)),pygame.SRCALPHA)
        pygame.draw.rect(sh,(0,0,0,70),sh.get_rect(),border_radius=L.s(24))
        screen.blit(sh,(rect.x-L.s(7),rect.y+L.s(7)))

        gradient_rect(screen, rect, item["color_a"], item["color_b"],
                      radius=L.s(20))

        if i == self.hover_idx:
            pygame.draw.rect(screen,(255,255,255),rect,width=3,
                             border_radius=L.s(20))

        em=self._efont.render(item["emoji"],True,(255,255,255))
        screen.blit(em, em.get_rect(center=(rect.centerx,rect.centery-L.s(16))))

        draw_text_centered(screen, item["label"],
                           Fonts.body(L.font_size(24)), Colors.TEXT_WHITE,
                           (rect.centerx, rect.centery+L.s(26)),
                           shadow=True, shadow_color=(0,0,0))

        if i==self.hover_idx and self.ge.get().is_pinching:
            st=self.hold._start.get(item["id"])
            if st:
                p=min((time.time()-st)/HOLD_S,1.0)
                hold_ring(screen,rect.center,L.s(32),p)
                if p>0:
                    draw_hold_loading_screen(screen,item["label"],
                                             p,item["color_a"],self.t)

    def _draw_cursor(self, screen, gf):
        if not gf.hand_visible: return
        draw_hand_skeleton(screen, gf.landmarks, gf.is_pinching)
        cx,cy=gf.cursor
        if gf.is_pinching:
            glow_circle(screen,(cx,cy),L.s(14),Colors.CYAN,layers=3)
        else:
            pygame.draw.circle(screen,Colors.TEXT_WHITE,(cx,cy),L.s(10),2)
            pygame.draw.circle(screen,Colors.CYAN,(cx,cy),L.s(4))


def run_numbers_menu(screen, ge: GestureEngine) -> str:
    return NumbersMenu(ge).run(screen)
