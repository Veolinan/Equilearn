# lessons/letters/lesson.py
"""
Letters lesson — two stages per letter:
  Stage 1: Dot-to-dot  — numbered dots appear on the letter strokes;
           child points to each dot in order (1→2→3…)
  Stage 2: Quiz        — see the letter, pick from 4 options
"""
import pygame, math, random, time, string

from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, gradient_rect, glow_circle,
    draw_text_centered, draw_stars_bg, hold_ring,
    particle_burst, draw_hand_skeleton,
    draw_hold_loading_screen, rounded_rect,
)
from modules.gesture_engine import GestureEngine, HoldDetector

FPS      = 60
HOLD_S   = 1.8   # hold time for dot selection
BACK_H   = 1.5

ALL_LETTERS = list(string.ascii_uppercase)

# Pre-defined stroke dot positions (normalised 0-1 within a 1×1 box)
# Each list = dots in tracing order.  We define A-Z here.
# Positions will be scaled to a canvas rect on screen.
LETTER_DOTS: dict[str, list[tuple]] = {
    "A": [(0.5,0.05),(0.15,0.95),(0.85,0.95),(0.3,0.55),(0.7,0.55)],
    "B": [(0.2,0.05),(0.2,0.95),(0.65,0.15),(0.65,0.5),(0.65,0.85),(0.2,0.5)],
    "C": [(0.8,0.2),(0.5,0.05),(0.15,0.5),(0.5,0.95),(0.8,0.8)],
    "D": [(0.2,0.05),(0.2,0.95),(0.7,0.75),(0.75,0.5),(0.7,0.25)],
    "E": [(0.75,0.05),(0.2,0.05),(0.2,0.5),(0.65,0.5),(0.2,0.95),(0.75,0.95)],
    "F": [(0.75,0.05),(0.2,0.05),(0.2,0.5),(0.65,0.5),(0.2,0.95)],
    "G": [(0.8,0.2),(0.5,0.05),(0.15,0.5),(0.5,0.95),(0.8,0.75),(0.8,0.5),(0.55,0.5)],
    "H": [(0.2,0.05),(0.2,0.95),(0.2,0.5),(0.8,0.5),(0.8,0.05),(0.8,0.95)],
    "I": [(0.3,0.05),(0.7,0.05),(0.5,0.05),(0.5,0.95),(0.3,0.95),(0.7,0.95)],
    "J": [(0.65,0.05),(0.65,0.75),(0.5,0.95),(0.3,0.85)],
    "K": [(0.2,0.05),(0.2,0.95),(0.2,0.5),(0.75,0.05),(0.75,0.95)],
    "L": [(0.2,0.05),(0.2,0.95),(0.75,0.95)],
    "M": [(0.1,0.95),(0.1,0.05),(0.5,0.55),(0.9,0.05),(0.9,0.95)],
    "N": [(0.15,0.95),(0.15,0.05),(0.85,0.95),(0.85,0.05)],
    "O": [(0.5,0.05),(0.15,0.5),(0.5,0.95),(0.85,0.5),(0.5,0.05)],
    "P": [(0.2,0.95),(0.2,0.05),(0.65,0.15),(0.65,0.5),(0.2,0.5)],
    "Q": [(0.5,0.05),(0.15,0.5),(0.5,0.95),(0.85,0.5),(0.65,0.75),(0.85,0.95)],
    "R": [(0.2,0.95),(0.2,0.05),(0.65,0.15),(0.65,0.5),(0.2,0.5),(0.65,0.95)],
    "S": [(0.75,0.15),(0.4,0.05),(0.15,0.25),(0.5,0.5),(0.85,0.75),(0.6,0.95),(0.25,0.85)],
    "T": [(0.1,0.05),(0.9,0.05),(0.5,0.05),(0.5,0.95)],
    "U": [(0.2,0.05),(0.2,0.75),(0.5,0.95),(0.8,0.75),(0.8,0.05)],
    "V": [(0.15,0.05),(0.5,0.95),(0.85,0.05)],
    "W": [(0.05,0.05),(0.25,0.95),(0.5,0.55),(0.75,0.95),(0.95,0.05)],
    "X": [(0.15,0.05),(0.85,0.95),(0.5,0.5),(0.15,0.95),(0.85,0.05)],
    "Y": [(0.15,0.05),(0.5,0.5),(0.85,0.05),(0.5,0.95)],
    "Z": [(0.15,0.05),(0.85,0.05),(0.15,0.95),(0.85,0.95)],
}


def _letter_canvas() -> pygame.Rect:
    """The rect inside which the letter dots are drawn."""
    size = min(int(L.ui_w * 0.35), int(L.ui_h * 0.55))
    cx   = L.cx
    cy   = L.ui_y + int(L.ui_h * 0.38)
    return pygame.Rect(cx - size//2, cy - size//2, size, size)


def _dot_positions(letter: str) -> list[tuple[int,int]]:
    """Return pixel positions for this letter's dots inside the canvas."""
    canvas  = _letter_canvas()
    raw     = LETTER_DOTS.get(letter, [(0.5,0.5)])
    pad     = int(canvas.width * 0.1)
    uw      = canvas.width  - pad * 2
    uh      = canvas.height - pad * 2
    return [(canvas.x + pad + int(nx*uw),
             canvas.y + pad + int(ny*uh))
            for nx, ny in raw]


def _emit(cx, cy, color, n=20):
    return [{"x":cx,"y":cy,
             "vx":math.cos(a)*s,"vy":math.sin(a)*s-120,
             "life":random.uniform(0.6,1.0),
             "color":color,"size":random.randint(L.s(4),L.s(10))}
            for a,s in [(random.uniform(0,math.pi*2),
                         random.uniform(80,240)) for _ in range(n)]]


# ── Dot-to-dot stage ──────────────────────────────────────────────────────────
class DotToDot:
    """
    Show a letter's skeleton as numbered dots.
    Child points + holds each dot in order.
    """
    DOT_R     = None   # set in run()
    REACH_R   = None   # how close cursor must be to count as "on dot"

    def __init__(self, ge: GestureEngine, letter: str):
        self.ge         = ge
        self.letter     = letter
        self.hold       = HoldDetector(HOLD_S)
        self.back_hold  = HoldDetector(BACK_H)
        self._clock     = pygame.time.Clock()
        self.t          = 0.0
        self.particles  = []
        self.stars      = [(random.randint(0,L.sw),random.randint(0,L.sh),
                            random.randint(1,2),random.uniform(0,6.28))
                           for _ in range(60)]

    def run(self, screen) -> str:
        """Returns 'done' when all dots hit, 'back' to exit."""
        self.dots     = _dot_positions(self.letter)
        self.n_dots   = len(self.dots)
        self.current  = 0
        self.trail    = []
        self.state    = "playing"
        self.cel_t    = 0.0
        self.particles= []

        # Say the letter name on entry
        try:
            from modules.sound_player import play_letter
            play_letter(self.letter)
        except Exception:
            pass

        DOT_R   = max(L.s(22), 18)
        REACH_R = DOT_R + L.s(20)

        while True:
            dt = self._clock.tick(FPS) / 1000.0
            self.t += dt

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: return "back"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "back"

            gf = self.ge.get()
            cx, cy = gf.cursor

            # Back button
            br = self._back_rect()
            _, back = self.back_hold.update(
                "back", br.collidepoint(cx,cy) and gf.is_pinching)
            if back: return "back"

            if self.state == "celebrating":
                self.cel_t += dt
                if self.cel_t > 2.0: return "done"
            elif self.state == "playing":
                # Check if cursor is on the current dot
                tx, ty = self.dots[self.current]
                dist   = math.hypot(cx-tx, cy-ty)
                on_dot = dist < REACH_R and gf.is_pinching

                _, fired = self.hold.update("dot", on_dot)
                if not on_dot:
                    self.hold._start.pop("dot", None)
                if fired:
                    self.trail.append(self.current)
                    self.particles += _emit(tx, ty, Colors.CYAN)
                    self.current += 1
                    if self.current >= self.n_dots:
                        self.state = "celebrating"
                        self.cel_t = 0.0
                        try:
                            from modules.sound_player import play_sound
                            play_sound("assets/sounds/well_done.mp3")
                        except: pass

            self._draw(screen, gf, DOT_R, REACH_R)
            pygame.display.flip()

    def _back_rect(self):
        return pygame.Rect(L.ui_x, L.ui_y, L.s(130), L.s(54))

    def _draw(self, screen, gf, DOT_R, REACH_R):
        screen.fill(Colors.BG_DEEP)
        draw_stars_bg(screen, self.stars, self.t)

        # Safe zone
        ov=pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
        pygame.draw.rect(ov,(255,255,255,12),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         border_radius=L.s(20))
        pygame.draw.rect(ov,(255,255,255,28),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         width=1,border_radius=L.s(20))
        screen.blit(ov,(0,0))

        # Back
        br=self._back_rect()
        b_act=br.collidepoint(*gf.cursor) and gf.is_pinching
        rounded_rect(screen,br,Colors.BG_CARD_HOVER if b_act else Colors.BG_CARD,
                     radius=L.s(14),border_color=Colors.PURPLE_LIGHT if b_act else None)
        draw_text_centered(screen,"← Back",Fonts.body(L.font_size(24)),
                           Colors.TEXT_LIGHT,br.center)

        # Title
        draw_text_centered(screen, f"Connect the dots  —  Letter {self.letter}",
                           Fonts.body(L.font_size(26)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_y + L.s(22)))

        # Big ghost letter in background
        ghost_font = pygame.font.SysFont("Arial", int(min(L.ui_w, L.ui_h)*0.65))
        ghost = ghost_font.render(self.letter, True, (255,255,255))
        ghost.set_alpha(18)
        canvas = _letter_canvas()
        screen.blit(ghost, ghost.get_rect(center=canvas.center))

        # Lines between completed dots
        if len(self.trail) >= 2:
            for i in range(len(self.trail)-1):
                a = self.dots[self.trail[i]]
                b = self.dots[self.trail[i+1]]
                pygame.draw.line(screen, Colors.CYAN, a, b, L.s(4))

        # Draw all dots
        for i,(dx,dy) in enumerate(self.dots):
            if i < self.current:
                # Completed — filled
                pygame.draw.circle(screen, Colors.GREEN, (dx,dy), DOT_R)
                pygame.draw.circle(screen, (255,255,255), (dx,dy), DOT_R, 2)
            elif i == self.current:
                # Current — pulsing
                pulse = 0.7 + 0.3*math.sin(self.t*5)
                pr    = int(DOT_R * pulse)
                glow_circle(screen,(dx,dy),pr+L.s(8),Colors.YELLOW,layers=3)
                pygame.draw.circle(screen, Colors.YELLOW, (dx,dy), pr)
                pygame.draw.circle(screen, (255,255,255), (dx,dy), pr, 3)
                # Number label
                nf=Fonts.body(L.font_size(20))
                draw_text_centered(screen,str(i+1),nf,(30,30,30),(dx,dy))
            else:
                # Future — faint outline
                pygame.draw.circle(screen, (80,70,110), (dx,dy), DOT_R, 2)
                nf=Fonts.label(L.font_size(18))
                draw_text_centered(screen,str(i+1),nf,(100,90,130),(dx,dy))

        # Hold ring on current dot
        if self.state == "playing" and self.current < self.n_dots:
            cx_g,cy_g = gf.cursor
            tx,ty = self.dots[self.current]
            dist = math.hypot(cx_g-tx, cy_g-ty)
            if dist < REACH_R and gf.is_pinching:
                st = self.hold._start.get("dot")
                if st:
                    p = min((time.time()-st)/HOLD_S, 1.0)
                    hold_ring(screen,(tx,ty),DOT_R+L.s(10),p,Colors.YELLOW)

        # Progress indicator
        prog_text = f"{self.current} / {self.n_dots} dots"
        draw_text_centered(screen, prog_text,
                           Fonts.label(L.font_size(22)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_bottom - L.s(30)))

        # Celebration
        if self.state == "celebrating":
            ov2=pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
            ov2.fill((10,8,20,int(120*min(self.cel_t,1.0))))
            screen.blit(ov2,(0,0))
            bounce=int(L.s(10)*abs(math.sin(self.t*5)))
            draw_text_centered(screen,"Well done! ⭐",
                               Fonts.title(L.font_size(64)),Colors.YELLOW,
                               (L.cx,L.cy-bounce),
                               shadow=True,shadow_color=(80,60,0))

        self.particles = particle_burst(screen, self.particles, 0)

        if gf.hand_visible:
            draw_hand_skeleton(screen, gf.landmarks, gf.is_pinching)
            cx_c,cy_c=gf.cursor
            if gf.is_pinching:
                glow_circle(screen,(cx_c,cy_c),L.s(14),Colors.CYAN,layers=3)
            else:
                pygame.draw.circle(screen,Colors.TEXT_WHITE,(cx_c,cy_c),L.s(10),2)
                pygame.draw.circle(screen,Colors.CYAN,(cx_c,cy_c),L.s(4))


# ── Letter quiz stage ─────────────────────────────────────────────────────────
class LetterQuiz:
    """Show a big letter, pick the correct name from 4 options."""

    def __init__(self, ge: GestureEngine, letter: str):
        self.ge        = ge
        self.letter    = letter
        self.hold      = HoldDetector(HOLD_S)
        self.back_hold = HoldDetector(BACK_H)
        self._clock    = pygame.time.Clock()
        self.t         = 0.0
        self.particles = []
        self.state     = "playing"
        self.result_msg= ""
        self.state_t   = 0.0
        self.wrong_idx = -1
        self.hover_idx = -1
        self.scales    = [1.0]*4
        self.stars     = [(random.randint(0,L.sw),random.randint(0,L.sh),
                           random.randint(1,2),random.uniform(0,6.28))
                          for _ in range(60)]

        pool   = [l for l in ALL_LETTERS if l != letter]
        distr  = random.sample(pool, 3) + [letter]
        random.shuffle(distr)
        self.options = distr
        self.correct = letter

    def _back_rect(self):
        return pygame.Rect(L.ui_x, L.ui_y, L.s(130), L.s(54))

    def _bubble_rects(self):
        n=4; slot_w=L.ui_w//n; bw=int(slot_w*0.70); bh=bw
        by=L.ui_y+int(L.ui_h*0.60)
        return [pygame.Rect(L.ui_x+slot_w*i+slot_w//2-bw//2,by,bw,bh)
                for i in range(n)]

    def run(self, screen) -> str:
        # Say the letter on entry
        try:
            from modules.sound_player import play_letter
            play_letter(self.letter)
        except Exception:
            pass

        PALETTES=[
            ((130,80,255),(80,40,180)),((60,180,255),(20,100,200)),
            ((255,120,60),(180,60,20)),((255,80,160),(180,30,100)),
        ]
        while True:
            dt=self._clock.tick(FPS)/1000.0; self.t+=dt
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return "back"
                if ev.type==pygame.KEYDOWN and ev.key==pygame.K_ESCAPE: return "back"

            gf=self.ge.get(); cx,cy=gf.cursor; p=gf.is_pinching

            _, back=self.back_hold.update("back",self._back_rect().collidepoint(cx,cy)and p)
            if back: return "back"

            if self.state=="correct":
                self.state_t+=dt
                if self.state_t>2.2: return "done"
            elif self.state=="wrong":
                self.state_t+=dt
                if self.state_t>1.6:
                    self.state="playing"; self.wrong_idx=-1

            rects=self._bubble_rects()
            nh=next((i for i,r in enumerate(rects) if r.collidepoint(cx,cy)),-1)
            self.hover_idx=nh
            for i in range(4):
                t_=1.08 if i==nh else 1.0
                self.scales[i]+=(t_-self.scales[i])*0.2

            if self.state=="playing":
                for i in range(4):
                    _,fired=self.hold.update(f"q{i}",(nh==i)and p)
                    if fired:
                        if self.options[i]==self.correct:
                            self.state="correct"; self.state_t=0.0
                            self.result_msg="Correct! ⭐"
                            r=rects[i]
                            self.particles+=_emit(r.centerx,r.centery,(130,80,255))
                            try:
                                from modules.sound_player import play_sound
                                play_sound("assets/sounds/correct.mp3")
                            except: pass
                        else:
                            self.state="wrong"; self.state_t=0.0
                            self.wrong_idx=i; self.result_msg="Try again! 💪"
                            try:
                                from modules.sound_player import play_sound
                                play_sound("assets/sounds/wrong.mp3")
                            except: pass

            # Draw
            screen.fill(Colors.BG_DEEP)
            draw_stars_bg(screen,self.stars,self.t)
            ov=pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
            pygame.draw.rect(ov,(255,255,255,12),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),border_radius=L.s(20))
            pygame.draw.rect(ov,(255,255,255,28),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),width=1,border_radius=L.s(20))
            screen.blit(ov,(0,0))

            br=self._back_rect()
            ba=br.collidepoint(*gf.cursor)and gf.is_pinching
            rounded_rect(screen,br,Colors.BG_CARD_HOVER if ba else Colors.BG_CARD,
                         radius=L.s(14),border_color=Colors.PURPLE_LIGHT if ba else None)
            draw_text_centered(screen,"← Back",Fonts.body(L.font_size(24)),Colors.TEXT_LIGHT,br.center)
            bst=self.back_hold._start.get("back")
            if bst: hold_ring(screen,br.center,L.s(28),min((time.time()-bst)/BACK_H,1.0),Colors.PURPLE_LIGHT)

            draw_text_centered(screen,"Which letter is this?",
                               Fonts.body(L.font_size(28)),Colors.TEXT_MUTED,
                               (L.cx,L.ui_y+L.s(22)))

            # Big letter display
            pulse=0.5+0.5*math.sin(self.t*2)
            lcol=(int(130+80*pulse),int(160+80*pulse),255)
            lf=pygame.font.SysFont("Arial Bold",int(min(L.ui_w,L.ui_h)*0.38))
            ls=lf.render(self.letter,True,lcol)
            screen.blit(ls,ls.get_rect(center=(L.cx,L.ui_y+L.s(105))))

            # Answer bubbles
            for i,(rect,pal) in enumerate(zip(rects,PALETTES)):
                sc=self.scales[i]
                w,h=int(rect.w*sc),int(rect.h*sc)
                r2=pygame.Rect(rect.centerx-w//2,rect.centery-h//2,w,h)
                sh=pygame.Surface((w+L.s(20),h+L.s(20)),pygame.SRCALPHA)
                pygame.draw.ellipse(sh,(0,0,0,70),sh.get_rect())
                screen.blit(sh,(r2.x-L.s(10),r2.y+L.s(12)))
                gradient_rect(screen,r2,pal[0],pal[1],radius=w//2)
                if i==self.wrong_idx:
                    fl=pygame.Surface((w,h),pygame.SRCALPHA)
                    pygame.draw.ellipse(fl,(255,60,60,140),fl.get_rect())
                    screen.blit(fl,r2.topleft)
                if self.state=="wrong" and self.options[i]==self.correct:
                    pygame.draw.ellipse(screen,Colors.YELLOW,r2,width=4)
                if i==self.hover_idx:
                    pygame.draw.ellipse(screen,(255,255,255),r2,width=4)
                lf2=pygame.font.SysFont("Arial Bold",int(r2.h*0.55))
                ls2=lf2.render(self.options[i],True,(255,255,255))
                screen.blit(ls2,ls2.get_rect(center=r2.center))
                if i==self.hover_idx and p:
                    st=self.hold._start.get(f"q{i}")
                    if st:
                        prog=min((time.time()-st)/HOLD_S,1.0)
                        hold_ring(screen,r2.center,r2.w//2+L.s(8),prog,Colors.HOLD_RING,L.s(7))
                        if prog>0:
                            draw_hold_loading_screen(screen,self.options[i],prog,pal[0],self.t)

            if self.result_msg:
                ry=L.ui_bottom-L.s(32)
                if self.state=="correct":
                    b=int(L.s(8)*abs(math.sin(self.t*6)))
                    draw_text_centered(screen,self.result_msg,Fonts.title(L.font_size(52)),
                                       Colors.CORRECT,(L.cx,ry-b),shadow=True,shadow_color=(0,80,30))
                elif self.state=="wrong":
                    draw_text_centered(screen,self.result_msg,Fonts.body(L.font_size(38)),
                                       Colors.WRONG,(L.cx,ry))

            self.particles=particle_burst(screen,self.particles,0)
            if gf.hand_visible:
                draw_hand_skeleton(screen,gf.landmarks,gf.is_pinching)
                if p: glow_circle(screen,(cx,cy),L.s(14),Colors.CYAN,layers=3)
                else:
                    pygame.draw.circle(screen,Colors.TEXT_WHITE,(cx,cy),L.s(10),2)
                    pygame.draw.circle(screen,Colors.CYAN,(cx,cy),L.s(4))
            pygame.display.flip()


# ── Letter selection menu ─────────────────────────────────────────────────────
class LetterSelectMenu:
    """A-Z grid; child picks a letter to practice."""

    COLS = 9

    def __init__(self, ge: GestureEngine):
        self.ge      = ge
        self.hold    = HoldDetector(1.5)
        self._clock  = pygame.time.Clock()
        self.t       = 0.0
        self.hover   = -1
        self.scales  = [1.0]*26
        self.result  = None
        self.stars   = [(random.randint(0,L.sw),random.randint(0,L.sh),
                         random.randint(1,2),random.uniform(0,6.28))
                        for _ in range(80)]

    def _rects(self):
        cols    = self.COLS
        rows    = math.ceil(26/cols)
        gap     = L.s(8)
        bw      = (L.ui_w - gap*(cols-1))//cols
        bh      = min(bw, (L.ui_h - L.s(80) - gap*(rows-1))//rows)
        y0      = L.ui_y + L.s(80)
        rects   = []
        for i,_ in enumerate(ALL_LETTERS):
            c = i%cols; r = i//cols
            x = L.ui_x + c*(bw+gap)
            y = y0 + r*(bh+gap)
            rects.append(pygame.Rect(x,y,bw,bh))
        return rects

    def run(self, screen) -> str:
        back_hold = HoldDetector(1.5)
        while self.result is None:
            dt=self._clock.tick(FPS)/1000.0; self.t+=dt
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return "back"
                if ev.type==pygame.KEYDOWN and ev.key==pygame.K_ESCAPE: return "back"

            gf=self.ge.get(); cx,cy=gf.cursor; p=gf.is_pinching
            br=pygame.Rect(L.ui_x,L.ui_y,L.s(130),L.s(54))
            _,bf=back_hold.update("back",br.collidepoint(cx,cy)and p)
            if bf: return "back"

            rects=self._rects()
            nh=next((i for i,r in enumerate(rects) if r.collidepoint(cx,cy)),-1)
            self.hover=nh
            for i in range(26):
                t_=1.08 if i==nh else 1.0
                self.scales[i]+=(t_-self.scales[i])*0.18
            for i,letter in enumerate(ALL_LETTERS):
                _,fired=self.hold.update(f"l{i}",(nh==i)and p)
                if fired: self.result=letter

            screen.fill(Colors.BG_DEEP)
            draw_stars_bg(screen,self.stars,self.t)
            ov=pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
            pygame.draw.rect(ov,(255,255,255,12),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),border_radius=L.s(20))
            pygame.draw.rect(ov,(255,255,255,28),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),width=1,border_radius=L.s(20))
            screen.blit(ov,(0,0))

            rounded_rect(screen,br,Colors.BG_CARD,radius=L.s(14))
            draw_text_centered(screen,"← Back",Fonts.body(L.font_size(24)),Colors.TEXT_LIGHT,br.center)

            draw_text_centered(screen,"Choose a Letter",
                               Fonts.title(L.font_size(46)),Colors.TEXT_WHITE,
                               (L.cx,L.ui_y+L.s(40)))

            for i,(letter,rect) in enumerate(zip(ALL_LETTERS,rects)):
                sc=self.scales[i]
                w,h=int(rect.w*sc),int(rect.h*sc)
                r2=pygame.Rect(rect.centerx-w//2,rect.centery-h//2,w,h)
                col=(130,80,255) if i==self.hover else (50,44,80)
                pygame.draw.rect(screen,col,r2,border_radius=L.s(10))
                if i==self.hover:
                    pygame.draw.rect(screen,(255,255,255),r2,width=2,border_radius=L.s(10))
                lf=Fonts.title(L.font_size(32))
                draw_text_centered(screen,letter,lf,Colors.TEXT_WHITE,r2.center)
                if i==self.hover and p:
                    st=self.hold._start.get(f"l{i}")
                    if st:
                        prog=min((time.time()-st)/1.5,1.0)
                        hold_ring(screen,r2.center,r2.w//2+L.s(6),prog,Colors.CYAN)
                        if prog>0:
                            draw_hold_loading_screen(screen,letter,prog,(130,80,255),self.t)

            if gf.hand_visible:
                draw_hand_skeleton(screen,gf.landmarks,gf.is_pinching)
                if p: glow_circle(screen,(cx,cy),L.s(14),Colors.CYAN,layers=3)
                else:
                    pygame.draw.circle(screen,Colors.TEXT_WHITE,(cx,cy),L.s(10),2)
                    pygame.draw.circle(screen,Colors.CYAN,(cx,cy),L.s(4))
            pygame.display.flip()
        return self.result


# ── Public entry point ────────────────────────────────────────────────────────
def run_letters(screen, ge: GestureEngine) -> str:
    while True:
        menu   = LetterSelectMenu(ge)
        choice = menu.run(screen)
        if choice == "back": return "menu"

        # Dot-to-dot first
        result = DotToDot(ge, choice).run(screen)
        if result == "back": continue

        # Then quiz
        LetterQuiz(ge, choice).run(screen)
