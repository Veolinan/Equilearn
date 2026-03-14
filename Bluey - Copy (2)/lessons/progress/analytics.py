# lessons/progress/analytics.py
"""
Analytics screen — time-based learning progress for caregivers.

Three tabs (pinch-hold tab to switch):
  1. Overview   — activity heatmap + weekly accuracy sparkline
  2. Lessons    — per-lesson accuracy trend bars + best streak badges
  3. Letters    — A-Z grid with stage progress rings

Navigation: pinch-hold a tab label (1.5s) to switch.
Back button: top-left, hold 1.5s.
"""
import pygame, math, random, time, string
from datetime import date, timedelta
from modules.ui.layout import L
from modules.ui.renderer import (
    Colors, Fonts, gradient_rect, glow_circle,
    draw_text_centered, draw_stars_bg, hold_ring,
    rounded_rect, particle_burst, draw_hand_skeleton,
)
from modules.gesture_engine import GestureEngine, HoldDetector
from modules.progress_tracker import PT

FPS = 60

# ── palette ───────────────────────────────────────────────────────────────────
C_MASTERED  = ( 50, 220, 100)
C_STARTED   = ( 50, 180, 255)
C_UNTOUCHED = ( 55,  50,  85)
C_GOLD      = (255, 210,  40)
C_PANEL     = ( 22,  18,  44)
C_ACCENT    = (130,  80, 255)
C_HEAT      = [
    ( 22,  18,  44),   # 0  — no activity
    ( 30,  60, 120),   # 1  — low
    ( 30, 120, 200),   # 2
    ( 40, 180, 220),   # 3
    ( 50, 220, 100),   # 4  — high
    (255, 210,  40),   # 5  — max
]

LESSONS = ["addition","subtraction","multiplication","division",
           "counting","odd_even","fill_missing","shapes","colors"]
LESSON_SHORT = {
    "addition": "Add", "subtraction": "Sub",
    "multiplication": "Mul", "division": "Div",
    "counting": "Count", "odd_even": "O/E",
    "fill_missing": "Fill", "shapes": "Shapes", "colors": "Colors",
}


# ── drawing helpers ────────────────────────────────────────────────────────────

def _draw_sparkline(surface, rect: pygame.Rect,
                    values: list[float],
                    color=(130, 80, 255),
                    fill=True, label=""):
    """Draw a sparkline inside rect. values = 0.0–1.0 list."""
    if not values:
        return
    n  = len(values)
    xs = [rect.x + int(i / max(n-1, 1) * rect.w) for i in range(n)]
    ys = [rect.bottom - int(v * rect.h) for v in values]

    # Fill under line
    if fill and n >= 2:
        pts  = list(zip(xs, ys))
        pts += [(xs[-1], rect.bottom), (xs[0], rect.bottom)]
        fill_surf = pygame.Surface((rect.w+4, rect.h+4), pygame.SRCALPHA)
        shifted   = [(x - rect.x, y - rect.y) for x, y in pts]
        pygame.draw.polygon(fill_surf, (*color, 35), shifted)
        surface.blit(fill_surf, (rect.x, rect.y))

    # Line
    if n >= 2:
        pts = list(zip(xs, ys))
        pygame.draw.lines(surface, color, False, pts, 2)

    # Latest dot
    if xs:
        pygame.draw.circle(surface, color, (xs[-1], ys[-1]), L.s(4))

    # Axis line
    pygame.draw.line(surface, (60, 55, 90),
                     (rect.x, rect.bottom), (rect.right, rect.bottom), 1)

    if label:
        lf = pygame.font.Font(None, L.font_size(16))
        ls = lf.render(label, True, (140, 130, 180))
        surface.blit(ls, (rect.x, rect.bottom + L.s(3)))


def _draw_heatmap(surface, rect: pygame.Rect,
                  sessions: list[dict], days: int = 28):
    """Calendar heatmap — each cell = one day, colour = activity level."""
    cols     = days
    cell_w   = max(4, (rect.w - cols + 1) // cols)
    cell_h   = max(8, rect.h)
    gap      = 2

    # Build lookup: date_str → question count
    activity = {}
    for s in sessions:
        d   = s.get("date", "")
        activity[d] = activity.get(d, 0) + s.get("questions", 0)
    max_q = max(activity.values()) if activity else 1

    today = date.today()
    for i in range(days):
        d   = str(today - timedelta(days=days - 1 - i))
        q   = activity.get(d, 0)
        lvl = 0
        if q > 0:
            lvl = min(5, 1 + int(q / max_q * 4.99))
        col = C_HEAT[lvl]
        x   = rect.x + i * (cell_w + gap)
        pygame.draw.rect(surface, col,
                         (x, rect.y, cell_w, cell_h),
                         border_radius=L.s(2))

    # Week labels under first day of each week
    lf = pygame.font.Font(None, L.font_size(14))
    for i in range(0, days, 7):
        d    = today - timedelta(days=days - 1 - i)
        txt  = d.strftime("%-d %b") if hasattr(d, 'strftime') else str(i)
        try:
            txt = d.strftime("%d %b")
        except Exception:
            txt = str(i)
        ls   = lf.render(txt, True, (90, 80, 120))
        x    = rect.x + i * (cell_w + gap)
        surface.blit(ls, (x, rect.bottom + L.s(3)))


def _draw_bar(surface, rect: pygame.Rect, value: float,
              color: tuple, label: str, sub: str = ""):
    """Horizontal bar with label."""
    pygame.draw.rect(surface, (40, 36, 70), rect, border_radius=L.s(4))
    if value > 0:
        fw = int(rect.w * value)
        pygame.draw.rect(surface, color,
                         pygame.Rect(rect.x, rect.y, fw, rect.h),
                         border_radius=L.s(4))
    # Label left
    lf = Fonts.label(L.font_size(15))
    ls = lf.render(label, True, Colors.TEXT_LIGHT)
    surface.blit(ls, (rect.x - ls.get_width() - L.s(6),
                      rect.centery - ls.get_height() // 2))
    # % right
    pct = f"{int(value*100)}%"
    ps  = lf.render(pct, True, color)
    surface.blit(ps, (rect.right + L.s(4),
                      rect.centery - ps.get_height() // 2))
    if sub:
        sf = pygame.font.Font(None, L.font_size(13))
        ss = sf.render(sub, True, (100, 90, 140))
        surface.blit(ss, (rect.x - ss.get_width() - L.s(6),
                          rect.centery + L.s(3)))


def _draw_star_badge(surface, cx, cy, r, color):
    pts = [(int(cx + (r if k%2==0 else r*0.42)
                * math.cos(math.radians(-90+k*36))),
            int(cy + (r if k%2==0 else r*0.42)
                * math.sin(math.radians(-90+k*36))))
           for k in range(10)]
    pygame.draw.polygon(surface, color, pts)


def _ring(surface, cx, cy, radius, progress, color, thickness, bg=(40,36,70)):
    """Progress arc ring."""
    pygame.draw.circle(surface, bg, (cx, cy), radius, thickness)
    if progress <= 0:
        return
    steps = max(3, int(60 * progress))
    pts   = []
    for i in range(steps + 1):
        a = -math.pi/2 + 2*math.pi * progress * i / steps
        pts.append((int(cx + radius * math.cos(a)),
                    int(cy + radius * math.sin(a))))
    if len(pts) >= 2:
        pygame.draw.lines(surface, color, False, pts, thickness)


# ── tab definitions ────────────────────────────────────────────────────────────
TABS = ["Overview", "Lessons", "Letters"]


# ── main analytics screen ──────────────────────────────────────────────────────
class AnalyticsScreen:

    def __init__(self, ge: GestureEngine):
        self.ge         = ge
        self.back_hold  = HoldDetector(1.5)
        self.tab_hold   = HoldDetector(1.5)
        self._clock     = pygame.time.Clock()
        self.t          = 0.0
        self.tab        = 0      # 0=Overview 1=Lessons 2=Letters
        self.particles  = []
        self.stars      = [(random.randint(0,L.sw), random.randint(0,L.sh),
                            random.randint(1,2), random.uniform(0,6.28))
                           for _ in range(60)]
        self._load()

    def _load(self):
        """Refresh all data from PT singleton."""
        stats            = PT.all_stats()
        self._letter_st  = stats["letters"]
        self._num_st     = stats["lessons"]
        self._shape_st   = stats["shapes"]
        self._detail     = stats["lesson_detail"]
        self._sessions   = PT.get_sessions(days=28)
        self._streak     = stats["streak"]
        self._stars      = stats["total_stars"]

        # Build weekly accuracy series (last 4 weeks, one point per day)
        day_acc = {}
        for s in self._sessions:
            day_acc[s["date"]] = s.get("accuracy", 0.0)
        today = date.today()
        self._weekly_acc = []
        for i in range(27, -1, -1):
            d   = str(today - timedelta(days=i))
            self._weekly_acc.append(day_acc.get(d, None))

        # Lesson accuracy (recent 10-question rolling average)
        self._lesson_acc = {}
        for lid in LESSONS:
            series = PT.get_accuracy_series(lid, days=28)
            self._lesson_acc[lid] = series[-1][1] if series else 0.0

        # Questions per day (for heatmap)
        self._all_sessions = PT.get_sessions(days=28)

    def run(self, screen) -> str:
        self._load()
        while True:
            dt = self._clock.tick(FPS) / 1000.0
            self.t += dt
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:  return "back"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "back"

            gf    = self.ge.get()
            cx,cy = gf.cursor
            pinch = gf.is_pinching

            # Back
            br = pygame.Rect(L.ui_x, L.ui_y, L.s(130), L.s(54))
            _, fired = self.back_hold.update(
                "back", br.collidepoint(cx, cy) and pinch)
            if fired:
                return "back"

            # Tab switching
            tab_rects = self._tab_rects()
            for i, tr in enumerate(tab_rects):
                _, tfired = self.tab_hold.update(
                    f"tab_{i}", tr.collidepoint(cx, cy) and pinch)
                if tfired and i != self.tab:
                    self.tab = i

            self.particles = particle_burst(
                pygame.display.get_surface(), self.particles, dt)

            self._draw(screen, gf)
            pygame.display.flip()

    # ── layout helpers ─────────────────────────────────────────────────────
    def _tab_rects(self) -> list[pygame.Rect]:
        tw  = L.s(160)
        th  = L.s(44)
        gap = L.s(10)
        total = len(TABS) * tw + (len(TABS)-1) * gap
        x0  = L.cx - total // 2
        ty  = L.ui_y + L.s(56)
        return [pygame.Rect(x0 + i*(tw+gap), ty, tw, th)
                for i in range(len(TABS))]

    def _content_rect(self) -> pygame.Rect:
        return pygame.Rect(L.ui_x, L.ui_y + L.s(116),
                           L.ui_w, L.ui_h - L.s(116))

    # ── draw ───────────────────────────────────────────────────────────────
    def _draw(self, screen, gf):
        screen.fill(Colors.BG_DEEP)

        # Nebula
        for i,(bx,by,br,bc) in enumerate([
            (int(L.sw*.25),int(L.sh*.3),L.s(180),(50,15,130)),
            (int(L.sw*.75),int(L.sh*.7),L.s(160),(15,50,150)),
        ]):
            ox = int(L.s(8)*math.sin(self.t*.3+i))
            oy = int(L.s(6)*math.cos(self.t*.25+i))
            bl = pygame.Surface((br*2,br*2),pygame.SRCALPHA)
            pygame.draw.circle(bl,(*bc,22),(br,br),br)
            screen.blit(bl,(bx-br+ox,by-br+oy))

        draw_stars_bg(screen, self.stars, self.t)

        # Safe zone
        ov = pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
        pygame.draw.rect(ov,(255,255,255,10),
                         (L.ui_x,L.ui_y,L.ui_w,L.ui_h),border_radius=L.s(20))
        pygame.draw.rect(ov,(255,255,255,24),
                         (L.ui_x,L.ui_y,L.ui_w,L.ui_h),
                         width=1,border_radius=L.s(20))
        screen.blit(ov,(0,0))

        # Back
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
                      min((time.time()-bst)/1.5,1.0), Colors.PURPLE_LIGHT)

        # Title
        draw_text_centered(screen, "Analytics",
                           Fonts.title(L.font_size(44)), Colors.TEXT_WHITE,
                           (L.cx, L.ui_y + L.s(28)),
                           shadow=True, shadow_color=(50,25,110))

        # Streak
        if self._streak > 0:
            sf = Fonts.body(L.font_size(20))
            ss = sf.render(f"🔥 {self._streak} day streak", True, C_GOLD)
            screen.blit(ss, ss.get_rect(
                midright=(L.ui_right - L.s(8), L.ui_y + L.s(28))))

        # Tabs
        tab_rects = self._tab_rects()
        cx_g, cy_g = gf.cursor
        for i, (name, tr) in enumerate(zip(TABS, tab_rects)):
            active  = (i == self.tab)
            hovering= tr.collidepoint(cx_g, cy_g)
            bg      = C_ACCENT if active else ((40,35,65) if hovering else C_PANEL)
            border  = Colors.PURPLE_LIGHT if active else None
            rounded_rect(screen, tr, bg, radius=L.s(12), border_color=border)
            draw_text_centered(screen, name,
                               Fonts.body(L.font_size(22)),
                               Colors.TEXT_WHITE if active else Colors.TEXT_MUTED,
                               tr.center)
            if hovering and gf.is_pinching and i != self.tab:
                st = self.tab_hold._start.get(f"tab_{i}")
                if st:
                    p = min((time.time()-st)/1.5, 1.0)
                    hold_ring(screen, tr.center, tr.w//2+L.s(4), p,
                              Colors.CYAN, thickness=3)

        # Content
        cr = self._content_rect()
        if self.tab == 0:   self._draw_overview(screen, cr)
        elif self.tab == 1: self._draw_lessons(screen, cr)
        else:               self._draw_letters(screen, cr)

        # Particles
        self.particles = particle_burst(screen, self.particles, 0)

        # Cursor
        if gf.hand_visible:
            draw_hand_skeleton(screen, gf.landmarks, gf.is_pinching)
            px,py = gf.cursor
            if gf.is_pinching:
                glow_circle(screen,(px,py),L.s(14),Colors.CYAN,layers=3)
            else:
                pygame.draw.circle(screen,Colors.TEXT_WHITE,(px,py),L.s(10),2)
                pygame.draw.circle(screen,Colors.CYAN,(px,py),L.s(4))

    # ── tab 0: Overview ────────────────────────────────────────────────────
    def _draw_overview(self, screen, cr: pygame.Rect):
        # ── Stats row ──────────────────────────────────────────────────────
        stats = PT.all_stats()
        n_mastered = (sum(1 for s in stats["letters"].values() if s=="mastered") +
                      sum(1 for s in stats["lessons"].values() if s=="mastered") +
                      sum(1 for s in stats["shapes"].values()  if s=="mastered"))
        n_total = (len(stats["letters"]) + len(stats["lessons"]) +
                   len(stats["shapes"]))

        total_q = sum(s.get("questions",0) for s in self._all_sessions)
        total_c = sum(s.get("correct",0)   for s in self._all_sessions)
        overall_acc = total_c / max(total_q, 1)
        total_min   = sum(s.get("duration_min",0) for s in self._all_sessions)
        days_active = len({s["date"] for s in self._all_sessions})

        stat_items = [
            ("Topics mastered",  f"{n_mastered}/{n_total}",  C_MASTERED),
            ("Overall accuracy", f"{int(overall_acc*100)}%", C_STARTED),
            ("Days active",      f"{days_active}",           C_GOLD),
            ("Questions answered",f"{total_q}",              C_ACCENT),
        ]
        sw_  = L.ui_w // len(stat_items)
        sy   = cr.y + L.s(8)
        sh_  = L.s(70)
        for i, (lbl, val, col) in enumerate(stat_items):
            sx = L.ui_x + i * sw_
            sr = pygame.Rect(sx+L.s(4), sy, sw_-L.s(8), sh_)
            rounded_rect(screen, sr, C_PANEL, radius=L.s(12))
            draw_text_centered(screen, val,
                               Fonts.title(L.font_size(34)), col,
                               (sr.centerx, sr.centery - L.s(8)))
            draw_text_centered(screen, lbl,
                               Fonts.label(L.font_size(15)), Colors.TEXT_MUTED,
                               (sr.centerx, sr.centery + L.s(16)))

        # ── Activity heatmap ────────────────────────────────────────────────
        hm_y = sy + sh_ + L.s(28)
        draw_text_centered(screen, "Activity — last 28 days",
                           Fonts.body(L.font_size(20)), Colors.TEXT_MUTED,
                           (L.cx, hm_y))
        hm_rect = pygame.Rect(L.ui_x + L.s(8), hm_y + L.s(22),
                               L.ui_w - L.s(16), L.s(22))
        _draw_heatmap(screen, hm_rect, self._all_sessions, days=28)

        # ── Accuracy sparkline ──────────────────────────────────────────────
        sp_y = hm_y + L.s(70)
        draw_text_centered(screen, "Daily accuracy trend",
                           Fonts.body(L.font_size(20)), Colors.TEXT_MUTED,
                           (L.cx, sp_y))
        # Fill gaps with None → interpolate for display
        filled = []
        last   = 0.5
        for v in self._weekly_acc:
            if v is not None:
                last = v
                filled.append(v)
            else:
                filled.append(None)
        # Draw as segments between non-None points
        sp_rect = pygame.Rect(L.ui_x + L.s(8), sp_y + L.s(22),
                               L.ui_w - L.s(16), L.s(80))
        # Background
        rounded_rect(screen, sp_rect, C_PANEL, radius=L.s(8))
        # 80% reference line
        ref_y = sp_rect.bottom - int(0.8 * sp_rect.h)
        pygame.draw.line(screen, (80,70,110),
                         (sp_rect.x, ref_y), (sp_rect.right, ref_y), 1)
        rf = pygame.font.Font(None, L.font_size(14))
        rs = rf.render("80%", True, (80,70,110))
        screen.blit(rs, (sp_rect.right + L.s(3), ref_y - L.s(6)))
        # Draw non-None segments
        pts = []
        n   = len(filled)
        for i, v in enumerate(filled):
            if v is not None:
                x = sp_rect.x + int(i / max(n-1,1) * sp_rect.w)
                y = sp_rect.bottom - int(v * sp_rect.h)
                pts.append((x, y))
            elif pts:
                if len(pts) >= 2:
                    pygame.draw.lines(screen, C_ACCENT, False, pts, 2)
                pts = []
        if len(pts) >= 2:
            pygame.draw.lines(screen, C_ACCENT, False, pts, 2)
        if pts:
            pygame.draw.circle(screen, C_ACCENT, pts[-1], L.s(4))

        # Legend
        leg_y = sp_rect.bottom + L.s(16)
        for col, lbl, lx in [
            (C_HEAT[0], "No activity",  L.ui_x),
            (C_HEAT[2], "Some",         L.ui_x + L.s(110)),
            (C_HEAT[5], "High",         L.ui_x + L.s(200)),
            (C_ACCENT,  "Accuracy line",L.ui_x + L.s(290)),
        ]:
            pygame.draw.rect(screen, col,
                             (lx, leg_y, L.s(12), L.s(12)),
                             border_radius=L.s(2))
            lf = pygame.font.Font(None, L.font_size(15))
            ls = lf.render(lbl, True, (110,100,150))
            screen.blit(ls, (lx + L.s(16), leg_y))

    # ── tab 1: Lessons ─────────────────────────────────────────────────────
    def _draw_lessons(self, screen, cr: pygame.Rect):
        all_lessons = LESSONS + ["shapes", "colors"]
        n      = len(all_lessons)
        row_h  = (cr.h - L.s(10)) // n
        bar_w  = int(L.ui_w * 0.42)
        bar_h  = max(L.s(14), row_h - L.s(16))
        lbl_w  = L.s(70)
        bar_x  = L.ui_x + lbl_w + L.s(10)

        draw_text_centered(screen, "Lesson accuracy  (rolling 10-question avg)",
                           Fonts.body(L.font_size(19)), Colors.TEXT_MUTED,
                           (L.cx, cr.y + L.s(6)))

        for i, lid in enumerate(all_lessons):
            y     = cr.y + L.s(28) + i * row_h
            acc   = self._lesson_acc.get(lid, 0.0)
            det   = self._detail.get(lid, {})
            best  = det.get("best_streak", 0)
            total = det.get("total_attempts", 0)

            if acc >= 0.80:   col = C_MASTERED
            elif acc >= 0.50: col = C_STARTED
            else:             col = (180, 80, 80)

            bar_rect = pygame.Rect(bar_x, y + (row_h - bar_h)//2,
                                   bar_w, bar_h)
            _draw_bar(screen, bar_rect, acc, col,
                      LESSON_SHORT.get(lid, lid),
                      sub=f"{total} attempts")

            # Sparkline for this lesson (tiny, to the right)
            series = PT.get_accuracy_series(lid, days=14)
            if series:
                vals = [v for _, v in series[-20:]]
                sp   = pygame.Rect(bar_x + bar_w + L.s(40),
                                   y + L.s(4), L.s(120), row_h - L.s(8))
                rounded_rect(screen, sp, C_PANEL, radius=L.s(4))
                _draw_sparkline(screen, sp, vals, color=col, fill=True)

            # Best streak badge
            if best >= 5:
                bx = bar_x + bar_w + L.s(170)
                by = y + row_h // 2
                badge_col = C_GOLD if best >= 10 else C_STARTED
                pygame.draw.circle(screen, badge_col, (bx, by), L.s(14))
                bf  = Fonts.label(L.font_size(13))
                bls = bf.render(str(best), True, (15,15,15))
                screen.blit(bls, bls.get_rect(center=(bx, by)))
                sf  = pygame.font.Font(None, L.font_size(11))
                ss  = sf.render("best", True, (15,15,15))
                screen.blit(ss, ss.get_rect(center=(bx, by + L.s(12))))

    # ── tab 2: Letters ─────────────────────────────────────────────────────
    def _draw_letters(self, screen, cr: pygame.Rect):
        draw_text_centered(screen, "Letter mastery  (ring = stage progress 1→5)",
                           Fonts.body(L.font_size(19)), Colors.TEXT_MUTED,
                           (L.cx, cr.y + L.s(6)))

        letters = list(string.ascii_uppercase)
        cols    = 9
        rows    = math.ceil(len(letters) / cols)
        gap     = L.s(8)
        avail_w = L.ui_w - L.s(12)
        avail_h = cr.h - L.s(30)
        iw      = (avail_w - gap*(cols-1)) // cols
        ih      = min(iw, (avail_h - gap*(rows-1)) // rows)
        r       = max(L.s(10), min(iw, ih) // 2 - L.s(3))
        gx      = L.ui_x + L.s(6)
        gy      = cr.y + L.s(26)

        for i, letter in enumerate(letters):
            col  = i % cols
            row  = i // cols
            ix   = gx + col * (iw + gap)
            iy   = gy + row * (ih + gap)
            cx_  = ix + iw // 2
            cy_  = iy + ih // 2

            status = self._letter_st.get(letter, "untouched")
            key    = f"letter_{letter}"
            entry  = PT._data.get(key, {})
            stage  = entry.get("stage", 1)

            # Background circle
            bg_col = {
                "mastered":  (30, 90, 50),
                "started":   (20, 50, 90),
                "untouched": (30, 27, 50),
            }.get(status, (30,27,50))
            pygame.draw.circle(screen, bg_col, (cx_, cy_), r)

            # Stage ring (5 segments)
            ring_r   = r + L.s(5)
            ring_th  = L.s(4)
            for s in range(1, 6):
                seg_start = -math.pi/2 + (s-1) * 2*math.pi/5
                seg_end   = seg_start + 2*math.pi/5 - 0.08
                seg_col   = (C_MASTERED if s <= stage and status != "untouched"
                             else (40,36,70))
                pts = []
                for k in range(12):
                    a   = seg_start + (seg_end-seg_start)*k/11
                    pts.append((int(cx_ + ring_r*math.cos(a)),
                                int(cy_ + ring_r*math.sin(a))))
                if len(pts) >= 2:
                    pygame.draw.lines(screen, seg_col, False, pts, ring_th)

            # Letter label
            tc = {
                "mastered":  (220, 255, 220),
                "started":   (200, 220, 255),
                "untouched": (80, 72, 120),
            }.get(status, (80,72,120))
            lf = Fonts.body(L.font_size(int(r * 0.9)))
            ls = lf.render(letter, True, tc)
            screen.blit(ls, ls.get_rect(center=(cx_, cy_)))

            # Star for mastered
            if status == "mastered":
                _draw_star_badge(screen, cx_+r-L.s(3), cy_-r+L.s(3),
                                 L.s(6), C_GOLD)

        # Legend
        leg_y = gy + rows*(ih+gap) + L.s(10)
        for col, lbl, lx in [
            ((30,90,50),  "Mastered",    L.ui_x),
            ((20,50,90),  "In progress", L.ui_x+L.s(110)),
            ((30,27,50),  "Not started", L.ui_x+L.s(240)),
        ]:
            pygame.draw.circle(screen, col, (lx+L.s(7), leg_y), L.s(7))
            ls = pygame.font.Font(None, L.font_size(16)).render(
                lbl, True, (110,100,150))
            screen.blit(ls, (lx+L.s(18), leg_y - L.s(6)))


# ── public entry ──────────────────────────────────────────────────────────────
def run_analytics(screen, ge: GestureEngine) -> str:
    return AnalyticsScreen(ge).run(screen)
