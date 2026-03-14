# lessons/numbers/lessons.py
import random, math, time
import pygame

from lessons.base_quiz import BaseQuiz, _bubble_rects, BUBBLE_PALETTES, HOLD_S, BACK_HOLD
from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, draw_text_centered, gradient_rect,
    glow_circle, rounded_rect, hold_ring,
    draw_hold_loading_screen, particle_burst,
    draw_hand_skeleton, draw_stars_bg,
)
from modules.gesture_engine import GestureEngine

EMOJI_LIST = ["🍎","🐠","🐶","⭐","🦋","🎈","🍓","🧸","🌸","🦄","🍦","🐱"]


# ── Subtraction ──────────────────────────────────────────────────────────────
class SubtractionLesson(BaseQuiz):
    def __init__(self, ge): super().__init__(ge, "Subtraction")

    def gen_question(self):
        a = random.randint(3, 12)
        b = random.randint(1, a - 1)
        self.correct = a - b
        self.question_text = f"{a}  −  {b}  = ?"
        opts = {self.correct}
        while len(opts) < 4:
            w = self.correct + random.choice([-3,-2,-1,1,2,3])
            if w >= 0: opts.add(w)
        self.options = list(opts)
        random.shuffle(self.options)
        self._a, self._b = a, b

    def draw_question(self, screen):
        # Show emoji objects visually (a row of fruit, b crossed out)
        emoji = random.choice(EMOJI_LIST) if not hasattr(self,"_emoji") else self._emoji
        self._emoji = emoji
        ef = pygame.font.SysFont("Segoe UI Emoji", L.font_size(38))
        total_w = self._a * L.s(44)
        start_x = L.cx - total_w // 2
        y = L.ui_y + L.s(62)
        for i in range(self._a):
            x = start_x + i * L.s(44)
            surf = ef.render(emoji, True, (255,255,255))
            screen.blit(surf, (x, y))
            if i >= (self._a - self._b):
                # Cross out
                pygame.draw.line(screen, Colors.RED,
                                 (x, y), (x+L.s(36), y+L.s(36)), L.s(3))
        draw_text_centered(screen, self.question_text,
                           Fonts.title(L.font_size(58)), Colors.TEXT_WHITE,
                           (L.cx, y + L.s(52)),
                           shadow=True, shadow_color=(40,20,80))


# ── Multiplication ───────────────────────────────────────────────────────────
class MultiplicationLesson(BaseQuiz):
    def __init__(self, ge): super().__init__(ge, "Multiplication")

    def gen_question(self):
        self._a = random.randint(2, 9)
        self._b = random.randint(2, 9)
        self.correct = self._a * self._b
        self.question_text = f"{self._a}  ×  {self._b}  = ?"
        opts = {self.correct}
        while len(opts) < 4:
            w = self.correct + random.choice([-6,-4,-2,2,4,6])
            if w > 0: opts.add(w)
        self.options = list(opts)
        random.shuffle(self.options)

    def draw_question(self, screen):
        import math as _math
        pulse = 0.5 + 0.5 * _math.sin(self.t * 2.5)
        col   = (int(130+80*pulse), int(180+60*pulse), 255)
        draw_text_centered(screen, self.question_text,
                           Fonts.title(L.font_size(72)), col,
                           (L.cx, L.ui_y + L.s(72)),
                           shadow=True, shadow_color=(40,20,80))
        # Visual: grid of dots  (a × b)
        if self._a <= 5 and self._b <= 5:
            dot_r = L.s(6)
            gap   = L.s(18)
            gw    = self._b * gap
            gh    = self._a * gap
            ox    = L.cx - gw//2
            oy    = L.ui_y + L.s(120)
            for r in range(self._a):
                for c in range(self._b):
                    pygame.draw.circle(screen, Colors.CYAN,
                                       (ox + c*gap, oy + r*gap), dot_r)


# ── Division ─────────────────────────────────────────────────────────────────
class DivisionLesson(BaseQuiz):
    def __init__(self, ge): super().__init__(ge, "Division")

    def gen_question(self):
        divisor  = random.randint(2, 5)
        quotient = random.randint(2, 6)
        dividend = divisor * quotient
        self.correct = quotient
        self.question_text = f"{dividend}  ÷  {divisor}  = ?"
        self._dividend, self._divisor = dividend, divisor
        opts = {quotient}
        while len(opts) < 4:
            w = quotient + random.choice([-3,-2,-1,1,2,3])
            if w > 0: opts.add(w)
        self.options = list(opts)
        random.shuffle(self.options)

    def draw_question(self, screen):
        # Show dividend items split into divisor groups
        emoji = "🍎"
        ef    = pygame.font.SysFont("Segoe UI Emoji", L.font_size(30))
        cols  = self._divisor
        rows  = self.correct
        gap   = L.s(36)
        gw    = cols * gap + L.s(20) * (cols - 1)
        ox    = L.cx - gw // 2
        oy    = L.ui_y + L.s(50)

        for grp in range(rows):
            for col in range(cols):
                x = ox + col * (gap + L.s(20))
                y = oy + grp * L.s(38)
                surf = ef.render(emoji, True, (255,255,255))
                screen.blit(surf, (x, y))

        draw_text_centered(screen, self.question_text,
                           Fonts.title(L.font_size(58)), Colors.TEXT_WHITE,
                           (L.cx, oy + rows*L.s(38) + L.s(16)),
                           shadow=True, shadow_color=(40,20,80))


# ── Counting ─────────────────────────────────────────────────────────────────
class CountingLesson(BaseQuiz):
    def __init__(self, ge): super().__init__(ge, "Counting")

    def gen_question(self):
        self._count = random.randint(1, 9)
        self._emoji = random.choice(EMOJI_LIST)
        self.correct = self._count
        self.question_text = f"How many {self._emoji}s?"
        opts = {self._count}
        while len(opts) < 4:
            w = random.randint(1, 9)
            opts.add(w)
        self.options = list(opts)
        random.shuffle(self.options)

    def draw_question(self, screen):
        ef   = pygame.font.SysFont("Segoe UI Emoji", L.font_size(48))
        cols = min(self._count, 5)
        rows = (self._count + cols - 1) // cols
        gap  = L.s(56)
        ox   = L.cx - (cols * gap) // 2
        oy   = L.ui_y + L.s(34)
        for i in range(self._count):
            col = i % cols
            row = i // cols
            surf= ef.render(self._emoji, True, (255,255,255))
            screen.blit(surf, (ox + col*gap, oy + row*L.s(52)))
        draw_text_centered(screen, "How many?",
                           Fonts.body(L.font_size(32)), Colors.TEXT_MUTED,
                           (L.cx, oy + rows*L.s(52) + L.s(8)))


# ── Odd / Even ────────────────────────────────────────────────────────────────
class OddEvenLesson(BaseQuiz):
    """Two large buttons: Odd / Even. Inherits full BaseQuiz loop."""

    def __init__(self, ge):
        super().__init__(ge, "Odd or Even?")

    def gen_question(self):
        n               = random.randint(1, 20)
        self._number    = n
        self.correct    = "Even" if n % 2 == 0 else "Odd"
        self.question_text = str(n)
        # Only 2 options — BaseQuiz supports variable-length options list
        self.options    = ["Odd", "Even"]

    def draw_question(self, screen):
        pulse = 0.5 + 0.5 * math.sin(self.t * 2.0)
        col   = (int(200 + 55 * pulse), int(200 + 55 * pulse), 80)
        draw_text_centered(screen, str(self._number),
                           Fonts.title(L.font_size(100)), col,
                           (L.cx, L.ui_y + L.s(82)),
                           shadow=True, shadow_color=(60, 40, 0))
        draw_text_centered(screen, "Is this number Odd or Even?",
                           Fonts.body(L.font_size(28)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_y + L.s(146)))

    # Override bubble layout: 2 wide rectangular buttons instead of 4 circles
    def _get_bubble_rects(self):
        bw = int(L.ui_w * 0.36)
        bh = L.s(120)
        by = L.ui_y + int(L.ui_h * 0.58)
        return [
            pygame.Rect(L.cx - bw - L.s(24), by, bw, bh),
            pygame.Rect(L.cx + L.s(24),       by, bw, bh),
        ]

    # Patch the base _update and _draw to use rectangular rects
    def _update(self, gf, dt):
        self.particles = particle_burst(pygame.display.get_surface(),
                                        self.particles, dt)
        cx, cy   = gf.cursor
        pinching = gf.is_pinching

        _, back = self.back_hold.update(
            "back", self._back_rect().collidepoint(cx, cy) and pinching)
        if back:
            return "back"

        if self.state == "correct":
            self.state_t += dt
            if self.state_t > 2.2:
                self._reset()
            return None

        if self.state == "wrong":
            self.state_t += dt
            self.shake_off = int(L.s(10) * math.sin(self.t * 40))
            if self.state_t > 1.6:
                self.state = "playing"
                self.wrong_idx = -1
                self.shake_off = 0
            return None

        rects     = self._get_bubble_rects()
        new_hover = next((i for i, r in enumerate(rects)
                          if r.collidepoint(cx, cy)), -1)
        self.hover_idx = new_hover

        # Smooth scale
        if not hasattr(self, '_oe_scales') or len(self._oe_scales) != 2:
            self._oe_scales = [1.0, 1.0]
        for i in range(2):
            t_ = 1.06 if i == new_hover else 1.0
            self._oe_scales[i] += (t_ - self._oe_scales[i]) * 0.2

        for i in range(2):
            _, fired = self.hold.update(
                f"opt_{i}", (new_hover == i) and pinching)
            if fired:
                if self.options[i] == self.correct:
                    self.state      = "correct"
                    self.state_t    = 0.0
                    self.result_msg = random.choice(
                        ["Amazing! 🎉", "Brilliant! ⭐", "Perfect! 🌟"])
                    r = rects[i]
                    self.particles += _emit_local(
                        r.centerx, r.centery, BUBBLE_PALETTES[i][0])
                    self._play("correct.mp3")
                else:
                    self.state      = "wrong"
                    self.state_t    = 0.0
                    self.wrong_idx  = i
                    self.result_msg = random.choice(
                        ["Try again! 💪", "Almost! 🤔", "Keep going! 💡"])
                    self._play("wrong.mp3")
        return None

    def _draw(self, screen, gf):
        # Background, safe zone, back button, title — same as base
        screen.fill(Colors.BG_DEEP)
        from modules.ui.renderer import draw_stars_bg, particle_burst as pb
        draw_stars_bg(screen, self.stars, self.t)

        ov = pygame.Surface((L.sw, L.sh), pygame.SRCALPHA)
        pygame.draw.rect(ov, (255, 255, 255, 12),
                         (L.ui_x, L.ui_y, L.ui_w, L.ui_h),
                         border_radius=L.s(20))
        pygame.draw.rect(ov, (255, 255, 255, 28),
                         (L.ui_x, L.ui_y, L.ui_w, L.ui_h),
                         width=1, border_radius=L.s(20))
        screen.blit(ov, (0, 0))

        br    = self._back_rect()
        b_act = br.collidepoint(*gf.cursor) and gf.is_pinching
        rounded_rect(screen, br,
                     Colors.BG_CARD_HOVER if b_act else Colors.BG_CARD,
                     radius=L.s(14),
                     border_color=Colors.PURPLE_LIGHT if b_act else None)
        draw_text_centered(screen, "← Back",
                           Fonts.body(L.font_size(24)), Colors.TEXT_LIGHT,
                           br.center)

        # Back hold ring
        bst = self.back_hold._start.get("back")
        if bst:
            hold_ring(screen, br.center, L.s(28),
                      min((time.time() - bst) / BACK_HOLD, 1.0),
                      Colors.PURPLE_LIGHT)

        draw_text_centered(screen, self.title,
                           Fonts.label(L.font_size(22)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_y + L.s(22)))
        self.draw_question(screen)

        # Instruction
        draw_text_centered(screen, "Point and hold your answer  👆",
                           Fonts.label(L.font_size(22)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_y + L.s(170)))

        # 2 wide buttons
        PAL = [((80, 180, 255), (20, 100, 200)),
               ((255, 120, 60), (180, 60, 20))]
        rects = self._get_bubble_rects()
        scales = getattr(self, '_oe_scales', [1.0, 1.0])

        for i, (rect, pal) in enumerate(zip(rects, PAL)):
            sc   = scales[i]
            w, h = int(rect.w * sc), int(rect.h * sc)
            r2   = pygame.Rect(rect.centerx - w//2,
                               rect.centery - h//2, w, h)

            # Shadow
            sh = pygame.Surface((w + L.s(16), h + L.s(16)), pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, 80), sh.get_rect(),
                             border_radius=L.s(24))
            screen.blit(sh, (r2.x - L.s(8), r2.y + L.s(8)))

            gradient_rect(screen, r2, pal[0], pal[1], radius=L.s(22))

            # Wrong flash
            if i == self.wrong_idx:
                fl = pygame.Surface((w, h), pygame.SRCALPHA)
                alpha = int(160 * (1 - self.state_t / 1.6))
                pygame.draw.rect(fl, (255, 60, 60, alpha),
                                 fl.get_rect(), border_radius=L.s(22))
                screen.blit(fl, r2.topleft)

            # Hint highlight on correct when wrong
            if self.state == "wrong" and self.options[i] == self.correct:
                pygame.draw.rect(screen, Colors.YELLOW, r2,
                                 width=4, border_radius=L.s(22))

            # Hover border
            if i == self.hover_idx:
                pygame.draw.rect(screen, (255, 255, 255), r2,
                                 width=3, border_radius=L.s(22))

            draw_text_centered(screen, self.options[i],
                               Fonts.title(L.font_size(56)),
                               Colors.TEXT_WHITE, r2.center,
                               shadow=True, shadow_color=(0, 0, 0))

            # Hold ring + loading screen
            if i == self.hover_idx and gf.is_pinching:
                st = self.hold._start.get(f"opt_{i}")
                if st:
                    p = min((time.time() - st) / HOLD_S, 1.0)
                    hold_ring(screen, r2.center, r2.w // 2 + L.s(8),
                              p, Colors.HOLD_RING, thickness=L.s(7))
                    if p > 0:
                        draw_hold_loading_screen(
                            screen, self.options[i], p, pal[0], self.t)

        # Result message
        if self.result_msg:
            ry = L.ui_bottom - L.s(32)
            if self.state == "correct":
                bounce = int(L.s(8) * abs(math.sin(self.t * 6)))
                draw_text_centered(screen, self.result_msg,
                                   Fonts.title(L.font_size(52)),
                                   Colors.CORRECT,
                                   (L.cx, ry - bounce),
                                   shadow=True, shadow_color=(0, 80, 30))
            elif self.state == "wrong":
                draw_text_centered(screen, self.result_msg,
                                   Fonts.body(L.font_size(38)),
                                   Colors.WRONG,
                                   (L.cx + self.shake_off, ry))

        pb(screen, self.particles, 0)
        self._draw_cursor(screen, gf)


def _emit_local(cx, cy, color, n=28):
    import math, random
    return [{"x":cx,"y":cy,
             "vx":math.cos(a)*s,"vy":math.sin(a)*s-150,
             "life":random.uniform(0.7,1.0),
             "color":color,"size":random.randint(L.s(5),L.s(12))}
            for a,s in [(random.uniform(0,math.pi*2),
                         random.uniform(100,340)) for _ in range(n)]]


# ── Fill in the Missing ───────────────────────────────────────────────────────
class FillMissingLesson(BaseQuiz):
    def __init__(self, ge): super().__init__(ge, "Fill the Missing Number")

    def gen_question(self):
        start = random.randint(1, 8)
        step  = random.choice([1, 2, 3])
        seq   = [start + i*step for i in range(5)]
        missing_idx = random.randint(1, 3)
        self.correct = seq[missing_idx]
        display = [str(n) for n in seq]
        display[missing_idx] = "?"
        self.question_text = "  ,  ".join(display)
        self._seq   = display
        self._blank = missing_idx
        opts = {self.correct}
        while len(opts) < 4:
            w = self.correct + random.randint(-4, 4)
            if w > 0: opts.add(w)
        self.options = list(opts)
        random.shuffle(self.options)

    def draw_question(self, screen):
        # Draw sequence as large number tiles
        n     = len(self._seq)
        tile_w= int(L.ui_w * 0.14)
        tile_h= L.s(64)
        gap   = L.s(10)
        total = n*tile_w + (n-1)*gap
        ox    = L.cx - total//2
        oy    = L.ui_y + L.s(50)

        for i, val in enumerate(self._seq):
            x = ox + i*(tile_w+gap)
            color = (Colors.YELLOW if val=="?" else
                     (50,44,80))
            border= Colors.YELLOW if val=="?" else (80,70,120)
            tile  = pygame.Rect(x, oy, tile_w, tile_h)
            rounded_rect(screen, tile, color, radius=L.s(12),
                         border_color=border, border_width=2)
            fc = Colors.TEXT_DARK if val=="?" else Colors.TEXT_WHITE
            draw_text_centered(screen, val,
                               Fonts.title(L.font_size(40)), fc,
                               tile.center)
            # Separator comma
            if i < n-1:
                draw_text_centered(screen, ",",
                                   Fonts.body(L.font_size(28)),
                                   Colors.TEXT_MUTED,
                                   (x+tile_w+gap//2, oy+tile_h//2+L.s(4)))

        draw_text_centered(screen, "What number is missing?",
                           Fonts.body(L.font_size(26)), Colors.TEXT_MUTED,
                           (L.cx, oy + tile_h + L.s(16)))


# ── Public runners ────────────────────────────────────────────────────────────
def run_subtraction(screen, ge):    return SubtractionLesson(ge).run(screen)
def run_multiplication(screen, ge): return MultiplicationLesson(ge).run(screen)
def run_division(screen, ge):       return DivisionLesson(ge).run(screen)
def run_counting(screen, ge):       return CountingLesson(ge).run(screen)
def run_odd_even(screen, ge):       return OddEvenLesson(ge).run(screen)
def run_fill_missing(screen, ge):   return FillMissingLesson(ge).run(screen)
