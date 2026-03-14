# lessons/shapes_colors/lesson.py
import pygame, math, random, time

from lessons.base_quiz import BaseQuiz, BUBBLE_PALETTES, _bubble_rects
from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, draw_text_centered, glow_circle,
    gradient_rect, rounded_rect, hold_ring,
    draw_hand_skeleton, draw_hold_loading_screen,
    draw_stars_bg, particle_burst,
)
from modules.gesture_engine import GestureEngine

# ── Shape definitions ─────────────────────────────────────────────────────────
SHAPES = [
    {"name": "Circle",    "color": (100,180,255), "sides": 0},
    {"name": "Square",    "color": (255,180, 60), "sides": 4},
    {"name": "Triangle",  "color": ( 80,220,120), "sides": 3},
    {"name": "Rectangle", "color": (255,100,160), "sides": 4, "rect":True},
    {"name": "Pentagon",  "color": (180,100,255), "sides": 5},
    {"name": "Hexagon",   "color": ( 60,220,220), "sides": 6},
    {"name": "Star",      "color": (255,220, 40), "sides": 5, "star":True},
    {"name": "Diamond",   "color": (255,140, 40), "sides": 4, "diamond":True},
]

COLORS = [
    {"name": "Red",    "rgb": (230,  60,  60)},
    {"name": "Blue",   "rgb": ( 60, 120, 230)},
    {"name": "Green",  "rgb": ( 60, 200,  80)},
    {"name": "Yellow", "rgb": (240, 220,  40)},
    {"name": "Purple", "rgb": (160,  60, 220)},
    {"name": "Orange", "rgb": (240, 140,  40)},
    {"name": "Pink",   "rgb": (240, 100, 180)},
    {"name": "White",  "rgb": (230, 230, 230)},
]

MODE_SHAPE = "shape"   # "What shape is this?"
MODE_COLOR = "color"   # "What color is this?"


def _draw_shape(surface, name, color, cx, cy, size):
    """Draw a named shape centred at (cx,cy) with given size and color."""
    s = size

    if name == "Circle":
        pygame.draw.circle(surface, color, (cx,cy), s)
        pygame.draw.circle(surface, (255,255,255), (cx,cy), s, max(2,s//12))

    elif name == "Star":
        pts = []
        for k in range(10):
            a = math.radians(-90 + k*36)
            r = s if k%2==0 else s*0.42
            pts.append((int(cx+r*math.cos(a)), int(cy+r*math.sin(a))))
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (255,255,255), pts, max(2,s//12))

    elif name == "Diamond":
        pts = [(cx,cy-s),(cx+s,cy),(cx,cy+s),(cx-s,cy)]
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (255,255,255), pts, max(2,s//12))

    elif name == "Rectangle":
        r = pygame.Rect(cx-int(s*1.5), cy-s//2, int(s*3), s)
        pygame.draw.rect(surface, color, r, border_radius=max(2,s//8))
        pygame.draw.rect(surface, (255,255,255), r, max(2,s//12),
                         border_radius=max(2,s//8))

    else:
        # Regular polygon with `sides` sides
        sides = {"Square":4,"Triangle":3,"Pentagon":5,"Hexagon":6}.get(name,4)
        offset = -math.pi/2 if sides%2==1 else -math.pi/sides
        pts = [(int(cx+s*math.cos(offset+2*math.pi*k/sides)),
                int(cy+s*math.sin(offset+2*math.pi*k/sides)))
               for k in range(sides)]
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (255,255,255), pts, max(2,s//12))


# ── Shape identification lesson ───────────────────────────────────────────────
class ShapeLesson(BaseQuiz):
    def __init__(self, ge): super().__init__(ge, "Shapes")

    def gen_question(self):
        self._shape   = random.choice(SHAPES)
        self._color   = random.choice(COLORS)
        self.correct  = self._shape["name"]
        self.question_text = "What shape is this?"
        names = [s["name"] for s in SHAPES]
        opts  = {self.correct}
        while len(opts) < 4:
            opts.add(random.choice(names))
        self.options = list(opts)
        random.shuffle(self.options)

    def draw_question(self, screen):
        sz = L.s(90)
        _draw_shape(screen, self._shape["name"],
                    self._color["rgb"], L.cx, L.ui_y + L.s(90), sz)
        draw_text_centered(screen, "What shape is this?",
                           Fonts.body(L.font_size(28)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_y + L.s(145)))

    def _draw_bubble_label(self, screen, i, rect):
        # Draw the shape name AND a small shape preview
        name   = self.options[i]
        shape  = next((s for s in SHAPES if s["name"]==name), SHAPES[0])
        mini_sz= min(rect.w, rect.h)//4
        _draw_shape(screen, name, shape["color"],
                    rect.centerx, rect.centery - L.s(18), mini_sz)
        draw_text_centered(screen, name,
                           Fonts.body(L.font_size(22)), Colors.TEXT_WHITE,
                           (rect.centerx, rect.centery + L.s(24)))


# ── Color identification lesson ────────────────────────────────────────────────
class ColorLesson(BaseQuiz):
    def __init__(self, ge): super().__init__(ge, "Colors")

    def gen_question(self):
        self._target  = random.choice(COLORS)
        self._shape   = random.choice(SHAPES)
        self.correct  = self._target["name"]
        self.question_text = "What color is this?"
        names = [c["name"] for c in COLORS]
        opts  = {self.correct}
        while len(opts) < 4:
            opts.add(random.choice(names))
        self.options = list(opts)
        random.shuffle(self.options)

    def draw_question(self, screen):
        sz = L.s(85)
        _draw_shape(screen, self._shape["name"],
                    self._target["rgb"], L.cx, L.ui_y + L.s(88), sz)
        draw_text_centered(screen, "What color is this?",
                           Fonts.body(L.font_size(28)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_y + L.s(144)))

    def _draw_bubble_label(self, screen, i, rect):
        # Big color swatch + name
        name  = self.options[i]
        color = next((c for c in COLORS if c["name"]==name), COLORS[0])
        sw    = int(rect.w * 0.55)
        sh_h  = int(rect.h * 0.38)
        sx    = rect.centerx - sw//2
        sy    = rect.centery - sh_h - L.s(6)
        swatch= pygame.Rect(sx, sy, sw, sh_h)
        pygame.draw.rect(screen, color["rgb"], swatch,
                         border_radius=L.s(8))
        pygame.draw.rect(screen, (255,255,255), swatch, 2,
                         border_radius=L.s(8))
        draw_text_centered(screen, name,
                           Fonts.body(L.font_size(22)), Colors.TEXT_WHITE,
                           (rect.centerx, rect.centery + L.s(20)))


# ── Shapes & Colors menu ───────────────────────────────────────────────────────
class ShapesColorsMenu:
    ITEMS = [
        {"id":"shapes","label":"Shapes","emoji":"🔷",
         "color_a":(60,180,255),"color_b":(20,100,200)},
        {"id":"colors","label":"Colors","emoji":"🎨",
         "color_a":(255,120,60),"color_b":(180,60,20)},
        {"id":"back",  "label":"Back",  "emoji":"👈",
         "color_a":(70,65,90), "color_b":(40,38,60)},
    ]

    def __init__(self, ge):
        self.ge      = ge
        self.hold    = HoldDetector(2.0)
        self.stars   = [(random.randint(0,L.sw),random.randint(0,L.sh),
                         random.randint(1,2),random.uniform(0,6.28))
                        for _ in range(80)]
        self.scales  = [1.0]*len(self.ITEMS)
        self.hover   = -1
        self.t       = 0.0
        self.result  = None
        self._clock  = pygame.time.Clock()
        self._efont  = pygame.font.SysFont("Segoe UI Emoji", L.font_size(52))

    def run(self, screen) -> str:
        from modules.gesture_engine import HoldDetector as HD
        self.result = None
        while self.result is None:
            dt = self._clock.tick(60) / 1000.0
            self.t += dt
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:           return "back"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "back"
            gf = self.ge.get()
            self._update(gf)
            self._draw(screen, gf)
            pygame.display.flip()
        return self.result

    def _update(self, gf):
        cx,cy=gf.cursor; p=gf.is_pinching
        rects=L.card_grid(len(self.ITEMS),cols=3)
        nh=next((i for i,r in enumerate(rects) if r.collidepoint(cx,cy)),-1)
        self.hover=nh
        for i in range(len(self.ITEMS)):
            t_=1.06 if i==nh else 1.0
            self.scales[i]+=(t_-self.scales[i])*0.18
        for i,item in enumerate(self.ITEMS):
            _,fired=self.hold.update(item["id"],(nh==i)and p)
            if fired: self.result=item["id"]

    def _draw(self, screen, gf):
        screen.fill(Colors.BG_DEEP)
        draw_stars_bg(screen,self.stars,self.t)
        ov=pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
        pygame.draw.rect(ov,(255,255,255,12),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         border_radius=L.s(20))
        pygame.draw.rect(ov,(255,255,255,28),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         width=1,border_radius=L.s(20))
        screen.blit(ov,(0,0))

        yt=L.ui_y+L.s(36)+int(L.s(3)*math.sin(self.t*1.2))
        draw_text_centered(screen,"Shapes & Colors",
                           Fonts.title(L.font_size(56)),Colors.TEXT_WHITE,
                           (L.cx,yt),shadow=True,shadow_color=(60,30,120))
        draw_text_centered(screen,"What do you want to learn?",
                           Fonts.body(L.font_size(24)),Colors.TEXT_MUTED,
                           (L.cx,yt+L.s(42)))

        rects=L.card_grid(len(self.ITEMS),cols=3)
        for i,(item,rect) in enumerate(zip(self.ITEMS,rects)):
            sc=self.scales[i]
            w,h=int(rect.w*sc),int(rect.h*sc)
            r2=pygame.Rect(rect.centerx-w//2,rect.centery-h//2,w,h)
            sh=pygame.Surface((w+L.s(14),h+L.s(14)),pygame.SRCALPHA)
            pygame.draw.rect(sh,(0,0,0,70),sh.get_rect(),border_radius=L.s(24))
            screen.blit(sh,(r2.x-L.s(7),r2.y+L.s(7)))
            gradient_rect(screen,r2,item["color_a"],item["color_b"],radius=L.s(20))
            if i==self.hover:
                pygame.draw.rect(screen,(255,255,255),r2,width=3,border_radius=L.s(20))
            em=self._efont.render(item["emoji"],True,(255,255,255))
            screen.blit(em,em.get_rect(center=(r2.centerx,r2.centery-L.s(16))))
            draw_text_centered(screen,item["label"],
                               Fonts.body(L.font_size(26)),Colors.TEXT_WHITE,
                               (r2.centerx,r2.centery+L.s(28)),
                               shadow=True,shadow_color=(0,0,0))
            if i==self.hover and gf.is_pinching:
                st=self.hold._start.get(item["id"])
                if st:
                    p=min((time.time()-st)/2.0,1.0)
                    hold_ring(screen,r2.center,L.s(32),p)
                    if p>0:
                        draw_hold_loading_screen(screen,item["label"],
                                                  p,item["color_a"],self.t)

        if gf.hand_visible:
            draw_hand_skeleton(screen,gf.landmarks,gf.is_pinching)
            cx,cy=gf.cursor
            if gf.is_pinching:
                glow_circle(screen,(cx,cy),L.s(14),Colors.CYAN,layers=3)
            else:
                pygame.draw.circle(screen,Colors.TEXT_WHITE,(cx,cy),L.s(10),2)
                pygame.draw.circle(screen,Colors.CYAN,(cx,cy),L.s(4))

        particle_burst(screen,[],0)


from modules.gesture_engine import HoldDetector

def run_shapes_colors(screen, ge: GestureEngine) -> str:
    while True:
        menu   = ShapesColorsMenu(ge)
        choice = menu.run(screen)
        if choice == "shapes":
            ShapeLesson(ge).run(screen)
        elif choice == "colors":
            ColorLesson(ge).run(screen)
        else:
            return "menu"
