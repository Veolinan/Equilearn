# lessons/numbers/addition.py
import pygame, math, random, time

from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, rounded_rect, gradient_rect,
    glow_circle, draw_text_centered, draw_stars_bg,
    hold_ring, particle_burst, draw_hand_skeleton,
    draw_hold_loading_screen,
)
from modules.gesture_engine import GestureEngine, HoldDetector

FPS       = 60
HOLD_S    = 2.0
BACK_HOLD = 1.5

BUBBLE_PALETTES = [
    ((255,100, 80),(180, 40, 20)),
    (( 80,180,255),( 20,100,200)),
    ((120,220, 80),( 50,150, 20)),
    ((255,180, 50),(180,110, 10)),
]


def _bubble_rects():
    n      = 4
    slot_w = L.ui_w // n
    bw     = int(slot_w * 0.70)
    bh     = bw
    by     = L.ui_y + int(L.ui_h * 0.52)
    rects  = []
    for i in range(n):
        cx = L.ui_x + slot_w * i + slot_w // 2
        rects.append(pygame.Rect(cx - bw//2, by, bw, bh))
    return rects


def _emit(cx, cy, color, n=28):
    return [{"x":cx,"y":cy,
             "vx":math.cos(a)*s,"vy":math.sin(a)*s-150,
             "life":random.uniform(0.7,1.0),
             "color":color,"size":random.randint(L.s(5),L.s(12))}
            for a,s in [(random.uniform(0,math.pi*2),
                         random.uniform(100,340)) for _ in range(n)]]


def _gen_problem():
    a = random.randint(1,9); b = random.randint(1,9)
    correct = a+b
    opts = {correct}
    while len(opts) < 4:
        w = correct + random.choice([-4,-3,-2,-1,1,2,3,4])
        if w > 0: opts.add(w)
    opts = list(opts); random.shuffle(opts)
    return a, b, correct, opts


class AdditionLesson:
    def __init__(self, ge: GestureEngine):
        self.ge         = ge
        self.hold       = HoldDetector(hold_seconds=HOLD_S)
        self.back_hold  = HoldDetector(hold_seconds=BACK_HOLD)
        self.particles  = []
        self.t          = 0.0
        self._clock     = pygame.time.Clock()
        self._emoji_font = pygame.font.SysFont("Segoe UI Emoji", L.font_size(48))
        self._new_problem()

    def _new_problem(self):
        self.a, self.b, self.correct, self.opts = _gen_problem()
        self.rects      = _bubble_rects()
        self.hover_idx  = -1
        self.scales     = [1.0]*4
        self.state      = "playing"
        self.state_t    = 0.0
        self.wrong_idx  = -1
        self.shake_off  = 0
        self.result_msg = ""
        self.stars      = [(random.randint(0,L.sw), random.randint(0,L.sh),
                            random.randint(1,2), random.uniform(0,6.28))
                           for _ in range(60)]
        self.particles  = []

    def run(self, screen: pygame.Surface) -> str:
        while True:
            dt = self._clock.tick(FPS) / 1000.0
            self.t += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT: return "back"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return "back"
            gf = self.ge.get()
            r  = self._update(gf, dt)
            if r: return r
            self._draw(screen, gf)
            pygame.display.flip()

    def _back_rect(self):
        w, h = L.s(130), L.s(54)
        return pygame.Rect(L.ui_x, L.ui_y, w, h)

    def _update(self, gf, dt):
        self.particles = particle_burst(pygame.display.get_surface(),
                                        self.particles, dt)
        cx, cy   = gf.cursor
        pinching = gf.is_pinching

        _, back_fired = self.back_hold.update(
            "back", self._back_rect().collidepoint(cx,cy) and pinching)
        if back_fired: return "back"

        if self.state == "correct":
            self.state_t += dt
            if self.state_t > 2.2: self._new_problem()
            return None
        if self.state == "wrong":
            self.state_t += dt
            self.shake_off = int(L.s(10)*math.sin(self.t*40))
            if self.state_t > 1.6:
                self.state="playing"; self.wrong_idx=-1; self.shake_off=0
            return None

        self.rects  = _bubble_rects()
        new_hover   = -1
        for i,rect in enumerate(self.rects):
            if rect.collidepoint(cx,cy): new_hover=i; break
        self.hover_idx = new_hover

        for i in range(4):
            t_ = 1.08 if i==new_hover else 1.0
            self.scales[i] += (t_-self.scales[i])*0.2

        for i in range(4):
            active = (new_hover==i) and pinching
            prog, fired = self.hold.update(f"opt_{i}", active)
            if fired:
                chosen = self.opts[i]
                if chosen==self.correct:
                    self.state="correct"; self.state_t=0.0
                    self.result_msg=random.choice(["Amazing! 🎉","Brilliant! ⭐","Perfect! 🌟"])
                    r = self.rects[i]
                    self.particles += _emit(r.centerx,r.centery,BUBBLE_PALETTES[i][0],n=40)
                    try:
                        from modules.sound_player import play_sound
                        play_sound("assets/sounds/correct.mp3")
                    except: pass
                else:
                    self.state="wrong"; self.state_t=0.0; self.wrong_idx=i
                    self.result_msg="Try again! 💪"
                    try:
                        from modules.sound_player import play_sound
                        play_sound("assets/sounds/wrong.mp3")
                    except: pass
        return None

    def _draw(self, screen, gf):
        screen.fill(Colors.BG_DEEP)
        draw_stars_bg(screen, self.stars, self.t)

        # Top gradient
        grad = pygame.Surface((L.sw, L.s(180)), pygame.SRCALPHA)
        for y in range(L.s(180)):
            a = int(60*(1-y/L.s(180)))
            pygame.draw.line(grad,(130,80,255,a),(0,y),(L.sw,y))
        screen.blit(grad,(0,0))

        # Safe zone overlay
        ov = pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
        pygame.draw.rect(ov,(255,255,255,12),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         border_radius=L.s(20))
        pygame.draw.rect(ov,(255,255,255,28),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         width=1,border_radius=L.s(20))
        screen.blit(ov,(0,0))

        # Back button
        br = self._back_rect()
        bactive = self._back_rect().collidepoint(*gf.cursor) and gf.is_pinching
        rounded_rect(screen,br,Colors.BG_CARD_HOVER if bactive else Colors.BG_CARD,
                     radius=L.s(14),
                     border_color=Colors.PURPLE_LIGHT if bactive else None)
        draw_text_centered(screen,"← Back",Fonts.body(L.font_size(24)),
                           Colors.TEXT_LIGHT,br.center)
        bst = self.back_hold._start.get("back")
        if bst:
            p=min((time.time()-bst)/BACK_HOLD,1.0)
            hold_ring(screen,br.center,L.s(28),p,Colors.PURPLE_LIGHT)

        # Question
        pulse = 0.5+0.5*math.sin(self.t*2.5)
        qcol  = (int(130+80*pulse),int(180+60*pulse),255)
        draw_text_centered(screen,f"{self.a}  +  {self.b}  = ?",
                           Fonts.title(L.font_size(72)),qcol,
                           (L.cx, L.ui_y+L.s(60)),
                           shadow=True,shadow_color=(40,20,80))
        draw_text_centered(screen,"Point and hold your answer  👆",
                           Fonts.label(L.font_size(24)),Colors.TEXT_MUTED,
                           (L.cx, L.ui_y+L.s(120)))

        # Bubbles
        for i,(rect,pal) in enumerate(zip(self.rects,BUBBLE_PALETTES)):
            self._draw_bubble(screen,i,rect,pal)

        # Result
        if self.result_msg:
            if self.state=="correct":
                bounce=int(L.s(8)*abs(math.sin(self.t*6)))
                draw_text_centered(screen,self.result_msg,
                                   Fonts.title(L.font_size(54)),Colors.CORRECT,
                                   (L.cx,L.ui_bottom-L.s(30)-bounce),
                                   shadow=True,shadow_color=(0,80,30))
            elif self.state=="wrong":
                draw_text_centered(screen,self.result_msg,
                                   Fonts.body(L.font_size(40)),Colors.WRONG,
                                   (L.cx+self.shake_off,L.ui_bottom-L.s(30)))

        self.particles = particle_burst(screen,self.particles,0)
        self._draw_cursor(screen,gf)

    def _draw_bubble(self,screen,i,base_rect,palette):
        sc   = self.scales[i]
        w,h  = int(base_rect.w*sc),int(base_rect.h*sc)
        rect = pygame.Rect(base_rect.centerx-w//2,base_rect.centery-h//2,w,h)
        is_h = (i==self.hover_idx)
        is_w = (i==self.wrong_idx)
        is_c = (self.opts[i]==self.correct)

        sh_s=pygame.Surface((w+L.s(20),h+L.s(20)),pygame.SRCALPHA)
        pygame.draw.ellipse(sh_s,(0,0,0,70),sh_s.get_rect())
        screen.blit(sh_s,(rect.x-L.s(10),rect.y+L.s(12)))

        gradient_rect(screen,rect,palette[0],palette[1],radius=w//2)

        if is_w:
            alpha=int(160*(1-self.state_t/1.6))
            fl=pygame.Surface((w,h),pygame.SRCALPHA)
            pygame.draw.ellipse(fl,(255,60,60,alpha),fl.get_rect())
            screen.blit(fl,rect.topleft)

        if self.state=="wrong" and is_c:
            ax,ay=rect.centerx,rect.top-L.s(24)
            pygame.draw.polygon(screen,Colors.YELLOW,
                                [(ax,ay+L.s(20)),(ax-L.s(14),ay),(ax+L.s(14),ay)])

        if is_h:
            pygame.draw.ellipse(screen,(255,255,255),rect,width=4)

        draw_text_centered(screen,str(self.opts[i]),
                           Fonts.title(L.font_size(66)),Colors.TEXT_WHITE,
                           rect.center,shadow=True,shadow_color=(0,0,0))

        if is_h and self.ge.get().is_pinching:
            st=self.hold._start.get(f"opt_{i}")
            if st:
                p=min((time.time()-st)/HOLD_S,1.0)
                hold_ring(screen,rect.center,rect.w//2+L.s(8),p,
                          Colors.HOLD_RING,thickness=L.s(7))

    def _draw_cursor(self,screen,gf):
        if not gf.hand_visible: return
        draw_hand_skeleton(screen,gf.landmarks,gf.is_pinching)
        cx,cy=gf.cursor
        if gf.is_pinching:
            glow_circle(screen,(cx,cy),L.s(14),Colors.CYAN,layers=3)
        else:
            pygame.draw.circle(screen,Colors.TEXT_WHITE,(cx,cy),L.s(10),2)
            pygame.draw.circle(screen,Colors.CYAN,(cx,cy),L.s(4))

        if gf.is_pinching and self.hover_idx>=0 and self.state=="playing":
            st=self.hold._start.get(f"opt_{self.hover_idx}")
            if st:
                p=min((time.time()-st)/HOLD_S,1.0)
                draw_hold_loading_screen(screen,str(self.opts[self.hover_idx]),
                                         p,BUBBLE_PALETTES[self.hover_idx][0],self.t)

        if gf.is_pinching and self._back_rect().collidepoint(cx,cy):
            st=self.back_hold._start.get("back")
            if st:
                p=min((time.time()-st)/BACK_HOLD,1.0)
                draw_hold_loading_screen(screen,"Menu",p,Colors.PURPLE_LIGHT,self.t)


def run_addition(screen: pygame.Surface, ge: GestureEngine) -> str:
    return AdditionLesson(ge).run(screen)
