# lessons/base_quiz.py
"""
Base class for any lesson that shows a question + 4 answer bubbles.
Subclasses override:
  - gen_question()  → sets self.question_text, self.correct, self.options[]
  - draw_question() → draws the visual question above the bubbles
"""
import pygame, math, random, time

from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, gradient_rect, glow_circle,
    draw_text_centered, draw_stars_bg,
    hold_ring, particle_burst, draw_hand_skeleton,
    draw_hold_loading_screen, rounded_rect,
)
from modules.gesture_engine import GestureEngine, HoldDetector

FPS       = 60
HOLD_S    = 2.0
BACK_HOLD = 1.5

BUBBLE_PALETTES = [
    ((255, 100,  80), (180,  40,  20)),
    (( 80, 180, 255), ( 20, 100, 200)),
    ((120, 220,  80), ( 50, 150,  20)),
    ((255, 180,  50), (180, 110,  10)),
]


def _emit(cx, cy, color, n=28):
    return [{"x": cx, "y": cy,
             "vx": math.cos(a)*s, "vy": math.sin(a)*s - 150,
             "life": random.uniform(0.7, 1.0),
             "color": color, "size": random.randint(L.s(5), L.s(12))}
            for a, s in [(random.uniform(0, math.pi*2),
                          random.uniform(100, 340)) for _ in range(n)]]


def _bubble_rects(n=4):
    slot_w = L.ui_w // n
    bw     = int(slot_w * 0.70)
    bh     = bw
    by     = L.ui_y + int(L.ui_h * 0.55)
    return [pygame.Rect(L.ui_x + slot_w*i + slot_w//2 - bw//2, by, bw, bh)
            for i in range(n)]


class BaseQuiz:
    def __init__(self, ge: GestureEngine, title: str = "Lesson",
                 lesson_id: str = ""):
        self.ge        = ge
        self.title     = title
        self.lesson_id = lesson_id   # used for difficulty + tracking
        self.hold      = HoldDetector(HOLD_S)
        self.back_hold = HoldDetector(BACK_HOLD)
        self._clock    = pygame.time.Clock()
        self.t         = 0.0
        self.particles = []
        self.stars     = self._gen_stars()

        # Scroll handler — fist drag shifts UI zone
        from modules.ui.scroll import ScrollHandler
        self._scroll = ScrollHandler()
        L.reset_scroll()

        # Load difficulty once per lesson session
        if lesson_id:
            from modules.difficulty import DM
            self.difficulty = DM.params(lesson_id)
        else:
            self.difficulty = {"level": 1, "label": "⭐"}

        self._reset()

    def _gen_stars(self):
        return [(random.randint(0, L.sw), random.randint(0, L.sh),
                 random.randint(1, 2), random.uniform(0, 6.28))
                for _ in range(60)]

    def _reset(self):
        self.options       = []
        self.correct       = None
        self.question_text = ""
        self.hover_idx     = -1
        self.scales        = [1.0]*4
        self.state         = "playing"
        self.state_t       = 0.0
        self.wrong_idx     = -1
        self.shake_off     = 0
        self.result_msg    = ""
        self.particles     = []
        self._level_up     = False
        self._levelup_t    = 0.0
        self._question_t   = time.time()   # when question was shown
        self._attempt_num  = 1             # resets on new question
        self.gen_question()

    # ── subclasses override ──────────────────────────────────────────────
    def gen_question(self):
        raise NotImplementedError

    def draw_question(self, screen):
        """Draw the question visual above the bubbles."""
        draw_text_centered(screen, self.question_text,
                           Fonts.title(L.font_size(68)), Colors.TEXT_WHITE,
                           (L.cx, L.ui_y + L.s(70)),
                           shadow=True, shadow_color=(40, 20, 80))
    # ────────────────────────────────────────────────────────────────────

    def _back_rect(self):
        return pygame.Rect(L.ui_x, L.ui_y, L.s(130), L.s(54))

    def run(self, screen) -> str:
        while True:
            dt = self._clock.tick(FPS) / 1000.0
            self.t += dt
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: return "back"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "back"
            gf = self.ge.get()
            r  = self._update(gf, dt)
            if r: return r
            self._draw(screen, gf)
            pygame.display.flip()

    def _update(self, gf, dt):
        self.particles = particle_burst(pygame.display.get_surface(),
                                        self.particles, dt)
        # Fist drag → scroll UI zone
        self._scroll.update(gf)

        cx, cy   = gf.cursor
        pinching = gf.is_pinching

        _, back_fired = self.back_hold.update(
            "back", self._back_rect().collidepoint(cx, cy) and pinching)
        if back_fired: return "back"

        if self.state == "correct":
            self.state_t += dt
            if self.state_t > 2.2: self._reset()
            return None
        if self.state == "wrong":
            self.state_t += dt
            self.shake_off = int(L.s(10) * math.sin(self.t * 40))
            if self.state_t > 1.6:
                self.state         = "playing"
                self.wrong_idx     = -1
                self.shake_off     = 0
                self._question_t   = time.time()   # restart timer for retry
            return None

        rects     = _bubble_rects(len(self.options))
        new_hover = next((i for i, r in enumerate(rects)
                          if r.collidepoint(cx, cy)), -1)
        self.hover_idx = new_hover

        for i in range(len(self.options)):
            t_ = 1.08 if i == new_hover else 1.0
            self.scales[i] += (t_ - self.scales[i]) * 0.2

        for i in range(len(self.options)):
            _, fired = self.hold.update(f"opt_{i}",
                                        (new_hover == i) and pinching)
            if fired:
                is_correct = (self.options[i] == self.correct)

                # ── Auto-record to ProgressTracker ─────────────────────
                if self.lesson_id:
                    try:
                        from modules.progress_tracker import PT
                        response_time = time.time() - self._question_t
                        PT.record_lesson(self.lesson_id, is_correct,
                                         response_time_s=response_time,
                                         attempt_number=self._attempt_num)
                        if not is_correct:
                            self._attempt_num += 1   # next try = attempt 2+
                        else:
                            self._attempt_num = 1    # will reset on _reset()
                        from modules.difficulty import DM
                        new_diff = DM.params(self.lesson_id)
                        if new_diff["level"] > self.difficulty["level"]:
                            self.difficulty = new_diff
                            self._level_up  = True
                    except Exception as e:
                        print(f"[Progress] record failed: {e}")

                if is_correct:
                    self.state      = "correct"
                    self.state_t    = 0.0
                    self.result_msg = random.choice(
                        ["Amazing! 🎉", "Brilliant! ⭐", "Perfect! 🌟",
                         "Wonderful! 🌈", "You got it! 🎊"])
                    r = rects[i]
                    self.particles += _emit(r.centerx, r.centery,
                                            BUBBLE_PALETTES[i % 4][0], n=40)
                    self._play("correct.mp3")
                else:
                    self.state      = "wrong"
                    self.state_t    = 0.0
                    self.wrong_idx  = i
                    self.result_msg = random.choice(
                        ["Try again! 💪", "Almost! 🤔", "Keep going! 💡"])
                    self._play("wrong.mp3")
        return None

    def _play(self, sound: str):
        """Play a named sound. Uses the proper priority system."""
        try:
            from modules import sound_player as sp
            name = sound.replace(".mp3", "")
            fn   = getattr(sp, f"play_{name}", None)
            if fn:
                fn()
            else:
                sp.play_sound(f"assets/sounds/{sound}")
        except Exception:
            pass

    def _draw(self, screen, gf):
        screen.fill(Colors.BG_DEEP)
        draw_stars_bg(screen, self.stars, self.t)

        # Top gradient wash
        grad = pygame.Surface((L.sw, L.s(200)), pygame.SRCALPHA)
        for y in range(L.s(200)):
            a = int(55 * (1 - y / L.s(200)))
            pygame.draw.line(grad, (100, 60, 220, a), (0, y), (L.sw, y))
        screen.blit(grad, (0, 0))

        # Safe zone outline
        ov = pygame.Surface((L.sw, L.sh), pygame.SRCALPHA)
        pygame.draw.rect(ov, (255, 255, 255, 12),
                         (L.ui_x, L.ui_y, L.ui_w, L.ui_h),
                         border_radius=L.s(20))
        pygame.draw.rect(ov, (255, 255, 255, 28),
                         (L.ui_x, L.ui_y, L.ui_w, L.ui_h),
                         width=1, border_radius=L.s(20))
        screen.blit(ov, (0, 0))

        # Back button
        br     = self._back_rect()
        b_act  = br.collidepoint(*gf.cursor) and gf.is_pinching
        rounded_rect(screen, br,
                     Colors.BG_CARD_HOVER if b_act else Colors.BG_CARD,
                     radius=L.s(14),
                     border_color=Colors.PURPLE_LIGHT if b_act else None)
        draw_text_centered(screen, "← Back",
                           Fonts.body(L.font_size(24)), Colors.TEXT_LIGHT,
                           br.center)
        bst = self.back_hold._start.get("back")
        if bst:
            hold_ring(screen, br.center, L.s(28),
                      min((time.time()-bst)/BACK_HOLD, 1.0),
                      Colors.PURPLE_LIGHT)

        # Lesson title + level badge (top centre)
        draw_text_centered(screen, self.title,
                           Fonts.label(L.font_size(22)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_y + L.s(22)))

        # Level badge — top right of UI zone
        level      = self.difficulty.get("level", 1)
        badge_lbl  = self.difficulty.get("label", "⭐")
        lvl_colors = {1: (180,140,40), 2: (100,180,255), 3: (120,220,80)}
        badge_col  = lvl_colors.get(level, (180,140,40))
        bx         = L.ui_right - L.s(12)
        by_badge   = L.ui_y + L.s(12)
        badge_font = Fonts.label(L.font_size(18))
        lvl_text   = f"Lv.{level}"
        lt_surf    = badge_font.render(lvl_text, True, badge_col)
        screen.blit(lt_surf, lt_surf.get_rect(topright=(bx, by_badge)))
        # Stars underneath
        star_surf  = pygame.font.SysFont("Segoe UI Emoji",
                         L.font_size(16)).render(badge_lbl, True, badge_col)
        screen.blit(star_surf, star_surf.get_rect(
            topright=(bx, by_badge + L.s(20))))

        # Progress to next level (thin bar under badge)
        streak     = self.difficulty.get("streak", 0)
        next_t     = self.difficulty.get("next_threshold")
        if next_t:
            prog_w  = L.s(80)
            prog_h  = L.s(5)
            prog_x  = bx - prog_w
            prog_y  = by_badge + L.s(40)
            pygame.draw.rect(screen, (50,44,80),
                             (prog_x, prog_y, prog_w, prog_h),
                             border_radius=L.s(3))
            fill = int(prog_w * min(streak / next_t, 1.0))
            if fill > 0:
                pygame.draw.rect(screen, badge_col,
                                 (prog_x, prog_y, fill, prog_h),
                                 border_radius=L.s(3))
            tip = Fonts.label(L.font_size(13))
            tip_s = tip.render(f"{streak}/{next_t}", True, Colors.TEXT_MUTED)
            screen.blit(tip_s, tip_s.get_rect(
                topright=(bx, prog_y + L.s(7))))

        # Level-up flash overlay
        if self._level_up:
            self._levelup_t += 1/60
            fade = max(0.0, 1.0 - self._levelup_t / 2.5)
            if fade > 0:
                ov2 = pygame.Surface((L.sw, L.sh), pygame.SRCALPHA)
                ov2.fill((80, 220, 120, int(40 * fade)))
                screen.blit(ov2, (0, 0))
                bounce = int(L.s(12) * abs(math.sin(self._levelup_t * 6)))
                draw_text_centered(screen,
                                   f"Level {level} unlocked!  🎉",
                                   Fonts.title(L.font_size(56)),
                                   (80, 220, 120),
                                   (L.cx, L.cy - bounce),
                                   shadow=True, shadow_color=(0,60,20))
            else:
                self._level_up  = False
                self._levelup_t = 0.0

        # Question (subclass)
        self.draw_question(screen)

        # Instruction
        draw_text_centered(screen, "Point and hold your answer  👆",
                           Fonts.label(L.font_size(22)), Colors.TEXT_MUTED,
                           (L.cx, L.ui_y + L.s(128)))

        # Bubbles
        rects = _bubble_rects(len(self.options))
        for i, (rect, pal) in enumerate(zip(rects, BUBBLE_PALETTES)):
            self._draw_bubble(screen, i, rect, pal)

        # Result message
        if self.result_msg:
            ry = L.ui_bottom - L.s(32)
            if self.state == "correct":
                bounce = int(L.s(8) * abs(math.sin(self.t * 6)))
                draw_text_centered(screen, self.result_msg,
                                   Fonts.title(L.font_size(52)), Colors.CORRECT,
                                   (L.cx, ry - bounce),
                                   shadow=True, shadow_color=(0, 80, 30))
            elif self.state == "wrong":
                draw_text_centered(screen, self.result_msg,
                                   Fonts.body(L.font_size(38)), Colors.WRONG,
                                   (L.cx + self.shake_off, ry))

        self.particles = particle_burst(screen, self.particles, 0)
        self._scroll.draw(screen)
        self._draw_gesture_hints(screen, gf)
        self._draw_cursor(screen, gf)

    def _draw_gesture_hints(self, screen, gf):
        """Gesture reference strip below safe zone."""
        from modules.gesture_engine import GestureState as GS
        hints = [
            ("👆", "Point",  gf.is_pointing),
            ("🤏", "Pinch",  gf.is_pinching),
            ("✊", "Scroll", gf.is_fist),
        ]
        em_font  = pygame.font.SysFont("Segoe UI Emoji", L.font_size(20))
        lbl_font = pygame.font.Font(None, L.font_size(16))
        total_w  = L.s(360)
        sx       = L.cx - total_w // 2
        sy       = L.sh - L.s(32)
        slot_w   = total_w // len(hints)
        for i, (emoji, label, active) in enumerate(hints):
            x    = sx + i * slot_w + slot_w // 2
            alp  = 240 if active else 55
            em_s = em_font.render(emoji, True, (255,255,255))
            em_s.set_alpha(alp)
            screen.blit(em_s, em_s.get_rect(center=(x, sy)))
            lb_s = lbl_font.render(label, True,
                                   (120,200,255) if active else (130,120,170))
            lb_s.set_alpha(alp)
            screen.blit(lb_s, lb_s.get_rect(center=(x, sy + L.s(16))))

    def _draw_bubble(self, screen, i, base_rect, pal):
        sc   = self.scales[i]
        w, h = int(base_rect.w * sc), int(base_rect.h * sc)
        rect = pygame.Rect(base_rect.centerx - w//2,
                           base_rect.centery - h//2, w, h)

        # Shadow
        sh = pygame.Surface((w+L.s(20), h+L.s(20)), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 70), sh.get_rect())
        screen.blit(sh, (rect.x-L.s(10), rect.y+L.s(12)))

        gradient_rect(screen, rect, pal[0], pal[1], radius=w//2)

        if i == self.wrong_idx:
            alpha = int(160*(1 - self.state_t/1.6))
            fl = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(fl, (255, 60, 60, alpha), fl.get_rect())
            screen.blit(fl, rect.topleft)

        if self.state == "wrong" and self.options[i] == self.correct:
            ax = rect.centerx
            ay = rect.top - L.s(24)
            pygame.draw.polygon(screen, Colors.YELLOW,
                                [(ax, ay+L.s(20)),
                                 (ax-L.s(14), ay),
                                 (ax+L.s(14), ay)])

        if i == self.hover_idx:
            pygame.draw.ellipse(screen, (255, 255, 255), rect, width=4)

        self._draw_bubble_label(screen, i, rect)

        if i == self.hover_idx and self.ge.get().is_pinching:
            st = self.hold._start.get(f"opt_{i}")
            if st:
                p = min((time.time()-st)/HOLD_S, 1.0)
                hold_ring(screen, rect.center, rect.w//2+L.s(8), p,
                          Colors.HOLD_RING, thickness=L.s(7))

    def _draw_bubble_label(self, screen, i, rect):
        """Default: draw option as text. Subclasses can override for shapes/colors."""
        draw_text_centered(screen, str(self.options[i]),
                           Fonts.title(L.font_size(62)), Colors.TEXT_WHITE,
                           rect.center, shadow=True, shadow_color=(0,0,0))

    def _draw_cursor(self, screen, gf):
        if not gf.hand_visible: return
        draw_hand_skeleton(screen, gf.landmarks, gf.is_pinching)
        cx, cy = gf.cursor
        if gf.is_pinching:
            glow_circle(screen, (cx, cy), L.s(14), Colors.CYAN, layers=3)
        else:
            pygame.draw.circle(screen, Colors.TEXT_WHITE, (cx, cy), L.s(10), 2)
            pygame.draw.circle(screen, Colors.CYAN, (cx, cy), L.s(4))

        if gf.is_pinching and self.hover_idx >= 0 and self.state == "playing":
            st = self.hold._start.get(f"opt_{self.hover_idx}")
            if st:
                p = min((time.time()-st)/HOLD_S, 1.0)
                draw_hold_loading_screen(
                    screen, str(self.options[self.hover_idx]),
                    p, BUBBLE_PALETTES[self.hover_idx % 4][0], self.t)

        if gf.is_pinching and self._back_rect().collidepoint(cx, cy):
            st = self.back_hold._start.get("back")
            if st:
                p = min((time.time()-st)/BACK_HOLD, 1.0)
                draw_hold_loading_screen(screen, "Menu", p,
                                         Colors.PURPLE_LIGHT, self.t)
