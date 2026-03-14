# lessons/progress/screen.py
"""
Progress screen — two views toggled by a top tab:
  SUMMARY   : letter circles A-Z + lesson pills + overall bar
  ANALYTICS : sparklines, response time, heatmap, metrics cards
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
C_MASTER  = ( 50, 220, 100)
C_STARTED = ( 50, 180, 255)
C_NONE    = ( 55,  50,  85)
C_GOLD    = (255, 210,  40)
C_PANEL   = ( 22,  18,  44)
C_ACCENT  = (130,  80, 255)

LESSONS = ["addition","subtraction","multiplication","division",
           "counting","odd_even","fill_missing"]
SHAPES  = ["shapes","colors"]
SHORT   = {"addition":"Add","subtraction":"Sub","multiplication":"Mul",
           "division":"Div","counting":"Count","odd_even":"Odd/Even",
           "fill_missing":"Fill","shapes":"Shapes","colors":"Colors"}

# ── tiny helpers ──────────────────────────────────────────────────────────────
def _sc(status):
    return {
        "mastered": C_MASTER, "started": C_STARTED, "untouched": C_NONE
    }.get(status, C_NONE)

def _star(surf, cx, cy, r, col):
    pts = [(int(cx+(r if k%2==0 else r*.42)*math.cos(math.radians(-90+k*36))),
            int(cy+(r if k%2==0 else r*.42)*math.sin(math.radians(-90+k*36))))
           for k in range(10)]
    pygame.draw.polygon(surf, col, pts)

def _flame(surf, cx, cy, sz, t):
    for col, sc, sp, ph in [
        ((255,80,20),1.0,3.0,0.0),((255,160,20),.7,4.0,.5),((255,240,80),.4,5.0,1.0)
    ]:
        fl = .85+.15*math.sin(t*sp+ph)
        w,h = int(sz*sc*.6*fl), int(sz*sc*fl)
        pts = [(cx,cy-h),(cx-w,cy),(cx-w//2,cy-h//3),
               (cx,cy-h//2),(cx+w//2,cy-h//3),(cx+w,cy)]
        s = pygame.Surface((sz*3,sz*3),pygame.SRCALPHA)
        shifted = [(x-cx+sz,y-cy+sz) for x,y in pts]
        pygame.draw.polygon(s, (*col,190), shifted)
        surf.blit(s,(cx-sz,cy-sz))

def _sparkline(surf, rect, vals, col=(130,80,255), fill=True):
    if len(vals) < 2: return
    n  = len(vals)
    xs = [rect.x + int(i/(n-1)*rect.w) for i in range(n)]
    ys = [rect.bottom - max(1, int(v*rect.h)) for v in vals]
    if fill:
        s = pygame.Surface((rect.w+2, rect.h+2), pygame.SRCALPHA)
        pts = list(zip([x-rect.x for x in xs],[y-rect.y for y in ys]))
        pts += [(xs[-1]-rect.x,rect.h),(0,rect.h)]
        pygame.draw.polygon(s, (*col,30), pts)
        surf.blit(s,(rect.x,rect.y))
    pygame.draw.lines(surf, col, False, list(zip(xs,ys)), 2)
    pygame.draw.circle(surf, col, (xs[-1],ys[-1]), L.s(4))
    pygame.draw.line(surf,(50,44,80),(rect.x,rect.bottom),(rect.right,rect.bottom),1)

def _heatmap(surf, rect, sessions, days=28):
    activity = {}
    for s in sessions:
        d = s.get("date","")
        activity[d] = activity.get(d,0) + s.get("questions",0)
    mx   = max(activity.values()) if activity else 1
    heat = [(22,18,44),(30,55,110),(30,110,190),(40,170,210),(50,220,100),(255,210,40)]
    cw   = max(3,(rect.w - days+1)//days); gap=2
    today = date.today()
    for i in range(days):
        d   = str(today-timedelta(days=days-1-i))
        q   = activity.get(d,0)
        lvl = 0 if q==0 else min(5,1+int(q/mx*4.99))
        x   = rect.x + i*(cw+gap)
        pygame.draw.rect(surf,heat[lvl],(x,rect.y,cw,rect.h),border_radius=2)


# ── main screen ───────────────────────────────────────────────────────────────
class ProgressScreen:
    def __init__(self, ge: GestureEngine):
        self.ge        = ge
        self.back_hold = HoldDetector(1.5)
        self.tab_hold  = HoldDetector(1.2)
        self._clock    = pygame.time.Clock()
        self.t         = 0.0
        self.tab       = 0    # 0=Summary 1=Analytics
        self.stars_bg  = [(random.randint(0,L.sw),random.randint(0,L.sh),
                           random.randint(1,2),random.uniform(0,6.28))
                          for _ in range(60)]
        self.particles = []
        self._refresh()

    def _refresh(self):
        stats            = PT.all_stats()
        self._letter_st  = stats["letters"]
        self._num_st     = stats["lessons"]
        self._shape_st   = stats["shapes"]
        self._detail     = stats["lesson_detail"]
        self._sessions   = PT.get_sessions(28)
        self._streak     = stats["streak"]
        self._stars      = stats["total_stars"]
        self._n_master   = (sum(1 for s in self._letter_st.values() if s=="mastered") +
                            sum(1 for s in self._num_st.values()    if s=="mastered") +
                            sum(1 for s in self._shape_st.values()  if s=="mastered"))
        self._n_total    = (len(self._letter_st)+len(self._num_st)+len(self._shape_st))

        # Analytics data
        self._acc_series  = {l: PT.get_accuracy_series(l,28)      for l in LESSONS+SHAPES}
        self._rt_series   = {l: PT.get_response_time_series(l,28) for l in LESSONS+SHAPES}
        self._fa_rate     = {l: PT.get_first_attempt_rate(l,28)    for l in LESSONS+SHAPES}

        # Daily accuracy for sparkline
        day_acc = {s["date"]: s["accuracy"] for s in self._sessions}
        today   = date.today()
        self._daily_acc = [day_acc.get(str(today-timedelta(days=27-i)))
                           for i in range(28)]

        # Daily avg response for sparkline
        day_rt = {s["date"]: s["avg_response_s"] for s in self._sessions
                  if s.get("avg_response_s",0)>0}
        max_rt  = max(day_rt.values(), default=12.0)
        self._daily_rt  = [1-min(day_rt.get(str(today-timedelta(days=27-i)),0)/max_rt,1)
                           for i in range(28)]  # inverted: faster=higher

    def run(self, screen) -> str:
        self._refresh()
        while True:
            dt = self._clock.tick(FPS)/1000.0
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
            _, fired = self.back_hold.update("back", br.collidepoint(cx,cy) and pinch)
            if fired: return "back"

            # Tab toggle
            tabs = self._tab_rects()
            for i,tr in enumerate(tabs):
                _, tf = self.tab_hold.update(f"t{i}", tr.collidepoint(cx,cy) and pinch)
                if tf and i != self.tab:
                    self.tab = i

            self.particles = particle_burst(pygame.display.get_surface(), self.particles, dt)
            self._draw(screen, gf)
            pygame.display.flip()

    def _tab_rects(self):
        tw, th = L.s(180), L.s(46)
        gap    = L.s(12)
        x0     = L.cx - (tw+gap//2)
        ty     = L.ui_y + L.s(58)
        return [pygame.Rect(x0+i*(tw+gap), ty, tw, th) for i in range(2)]

    # ── shared chrome ─────────────────────────────────────────────────────
    def _draw_chrome(self, screen, gf):
        screen.fill(Colors.BG_DEEP)
        for i,(bx,by,br,bc) in enumerate([
            (int(L.sw*.25),int(L.sh*.3),L.s(180),(50,15,120)),
            (int(L.sw*.75),int(L.sh*.7),L.s(160),(15,50,140)),
        ]):
            ox=int(L.s(8)*math.sin(self.t*.3+i)); oy=int(L.s(6)*math.cos(self.t*.25+i))
            bl=pygame.Surface((br*2,br*2),pygame.SRCALPHA)
            pygame.draw.circle(bl,(*bc,22),(br,br),br)
            screen.blit(bl,(bx-br+ox,by-br+oy))
        draw_stars_bg(screen, self.stars_bg, self.t)

        # Safe zone
        ov=pygame.Surface((L.sw,L.sh),pygame.SRCALPHA)
        pygame.draw.rect(ov,(255,255,255,10),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),border_radius=L.s(20))
        pygame.draw.rect(ov,(255,255,255,22),(L.ui_x,L.ui_y,L.ui_w,L.ui_h),width=1,border_radius=L.s(20))
        screen.blit(ov,(0,0))

        # Back btn
        br   = pygame.Rect(L.ui_x, L.ui_y, L.s(130), L.s(54))
        ba   = br.collidepoint(*gf.cursor) and gf.is_pinching
        rounded_rect(screen,br,Colors.BG_CARD_HOVER if ba else Colors.BG_CARD,
                     radius=L.s(14),border_color=Colors.PURPLE_LIGHT if ba else None)
        draw_text_centered(screen,"← Back",Fonts.body(L.font_size(22)),Colors.TEXT_LIGHT,br.center)
        bst = self.back_hold._start.get("back")
        if bst:
            hold_ring(screen,br.center,L.s(26),min((time.time()-bst)/1.5,1.0),Colors.PURPLE_LIGHT)

        # Title
        draw_text_centered(screen,"My Progress",
                           Fonts.title(L.font_size(42)),Colors.TEXT_WHITE,
                           (L.cx, L.ui_y+L.s(30)),shadow=True,shadow_color=(50,25,110))

        # Streak
        if self._streak > 0:
            _flame(screen, L.ui_right-L.s(50), L.ui_y+L.s(28), L.s(22), self.t)
            draw_text_centered(screen,f"{self._streak}",
                               Fonts.title(L.font_size(24)),C_GOLD,
                               (L.ui_right-L.s(50), L.ui_y+L.s(46)))

        # Tabs
        tabs = self._tab_rects()
        cx_g,cy_g = gf.cursor
        for i,(name,tr) in enumerate(zip(["Summary","Analytics"],tabs)):
            active = (i==self.tab)
            hover  = tr.collidepoint(cx_g,cy_g)
            bg     = C_ACCENT if active else ((38,33,62) if hover else C_PANEL)
            border = Colors.PURPLE_LIGHT if active else None
            rounded_rect(screen,tr,bg,radius=L.s(12),border_color=border)
            draw_text_centered(screen,name,
                               Fonts.body(L.font_size(22)),
                               Colors.TEXT_WHITE if active else Colors.TEXT_MUTED,
                               tr.center)
            if hover and gf.is_pinching and not active:
                st=self.tab_hold._start.get(f"t{i}")
                if st:
                    p=min((time.time()-st)/1.2,1.0)
                    hold_ring(screen,tr.center,tr.w//2+L.s(4),p,Colors.CYAN,thickness=3)

    # ── cursor ────────────────────────────────────────────────────────────
    def _draw_cursor(self, screen, gf):
        if not gf.hand_visible: return
        draw_hand_skeleton(screen, gf.landmarks, gf.is_pinching)
        cx,cy = gf.cursor
        if gf.is_pinching:
            glow_circle(screen,(cx,cy),L.s(14),Colors.CYAN,layers=3)
        else:
            pygame.draw.circle(screen,Colors.TEXT_WHITE,(cx,cy),L.s(10),2)
            pygame.draw.circle(screen,Colors.CYAN,(cx,cy),L.s(4))

    # ── main draw ─────────────────────────────────────────────────────────
    def _draw(self, screen, gf):
        self._draw_chrome(screen, gf)
        # Content area starts below tabs
        content_y = L.ui_y + L.s(116)
        content_h = L.ui_bottom - content_y
        cr = pygame.Rect(L.ui_x, content_y, L.ui_w, content_h)
        if self.tab == 0:
            self._draw_summary(screen, cr)
        else:
            self._draw_analytics(screen, cr)
        self.particles = particle_burst(screen, self.particles, 0)
        self._draw_cursor(screen, gf)

    # ══ TAB 0: SUMMARY ════════════════════════════════════════════════════
    def _draw_summary(self, screen, cr):
        # ── Overall progress bar ─────────────────────────────────────────
        bar_h = L.s(12)
        bar_r = pygame.Rect(L.ui_x, cr.y+L.s(6), L.ui_w, bar_h)
        pygame.draw.rect(screen,(44,38,74),bar_r,border_radius=L.s(6))
        if self._n_master and self._n_total:
            fw=int(L.ui_w*self._n_master/self._n_total)
            pygame.draw.rect(screen,C_MASTER,
                             pygame.Rect(L.ui_x,cr.y+L.s(6),fw,bar_h),border_radius=L.s(6))
        draw_text_centered(screen,f"{self._n_master}/{self._n_total} topics mastered",
                           Fonts.label(L.font_size(16)),Colors.TEXT_MUTED,
                           (L.cx, cr.y+bar_h+L.s(16)))

        # ── Three panels ─────────────────────────────────────────────────
        panel_y = cr.y + L.s(34)
        panel_h = cr.bottom - panel_y - L.s(22)
        gap     = L.s(12)
        pw      = (L.ui_w - gap*2) // 3

        # Letters
        self._draw_letter_panel(screen,
            pygame.Rect(L.ui_x, panel_y, pw, panel_h))

        # Numbers
        self._draw_lesson_panel(screen,
            pygame.Rect(L.ui_x+pw+gap, panel_y, pw, panel_h),
            "Numbers  🔢", LESSONS, self._num_st)

        # Shapes
        self._draw_lesson_panel(screen,
            pygame.Rect(L.ui_x+(pw+gap)*2, panel_y, pw, panel_h),
            "Shapes & Colors  🔷", SHAPES, self._shape_st)

        # Legend
        leg_y = cr.bottom - L.s(12)
        for col,lbl,lx in [(C_MASTER,"Mastered",L.ui_x),
                            (C_STARTED,"In progress",L.ui_x+L.s(110)),
                            (C_NONE,"Not started",L.ui_x+L.s(240))]:
            pygame.draw.circle(screen,col,(lx+L.s(6),leg_y),L.s(5))
            f=pygame.font.Font(None,L.font_size(15))
            screen.blit(f.render(lbl,True,(100,90,140)),(lx+L.s(14),leg_y-L.s(6)))

    def _draw_letter_panel(self, screen, rect):
        rounded_rect(screen,rect,C_PANEL,radius=L.s(14),
                     border_color=(60,54,100),border_width=1)
        draw_text_centered(screen,"Letters  🔤",
                           Fonts.body(L.font_size(20)),Colors.TEXT_WHITE,
                           (rect.centerx, rect.y+L.s(20)))

        letters = list(string.ascii_uppercase)
        cols    = 9; rows = 3
        gap     = L.s(4)
        avail_w = rect.w - L.s(12)
        avail_h = rect.h - L.s(38)
        iw      = (avail_w - gap*(cols-1)) // cols
        ih      = min(iw,(avail_h - gap*(rows-1)) // rows)
        r       = max(L.s(8), min(iw,ih)//2 - L.s(1))
        gx      = rect.x + L.s(6)
        gy      = rect.y + L.s(36) + (avail_h - rows*(ih+gap))//2

        for i,lt in enumerate(letters):
            col_ = i%cols; row_ = i//cols
            icx  = gx + col_*(iw+gap) + iw//2
            icy  = gy + row_*(ih+gap) + ih//2
            st   = self._letter_st.get(lt,"untouched")
            bg   = _sc(st)
            if st=="mastered":
                gc=pygame.Surface((r*2+6,r*2+6),pygame.SRCALPHA)
                pygame.draw.circle(gc,(*bg,50),(r+3,r+3),r+3)
                screen.blit(gc,(icx-r-3,icy-r-3))
            pygame.draw.circle(screen,bg,(icx,icy),r)
            pygame.draw.circle(screen,(255,255,255),(icx,icy),r,1)
            if st=="mastered":
                _star(screen,icx+r-L.s(2),icy-r+L.s(2),L.s(5),C_GOLD)
            if r >= L.s(10):
                tc=(15,15,15) if st!="untouched" else (100,90,140)
                f=Fonts.label(L.font_size(12))
                draw_text_centered(screen,lt,f,tc,(icx,icy))

    def _draw_lesson_panel(self, screen, rect, title, lesson_ids, status_dict):
        rounded_rect(screen,rect,C_PANEL,radius=L.s(14),
                     border_color=(60,54,100),border_width=1)
        draw_text_centered(screen,title,Fonts.body(L.font_size(20)),Colors.TEXT_WHITE,
                           (rect.centerx,rect.y+L.s(20)))

        n_m = sum(1 for l in lesson_ids if status_dict.get(l)=="mastered")
        draw_text_centered(screen,f"{n_m}/{len(lesson_ids)} mastered",
                           Fonts.label(L.font_size(14)),Colors.TEXT_MUTED,
                           (rect.centerx,rect.y+L.s(40)))

        bar=pygame.Rect(rect.x+L.s(10),rect.y+L.s(50),rect.w-L.s(20),L.s(6))
        pygame.draw.rect(screen,(40,36,70),bar,border_radius=L.s(3))
        if lesson_ids:
            fw=int(bar.w*n_m/len(lesson_ids))
            if fw>0:
                pygame.draw.rect(screen,C_MASTER,
                                 pygame.Rect(bar.x,bar.y,fw,bar.h),border_radius=L.s(3))

        n   = len(lesson_ids)
        rows= n; gap=L.s(4)
        avail_h = rect.h - L.s(62)
        row_h   = (avail_h - gap*(rows-1)) // rows
        pill_h  = max(L.s(16), min(row_h, L.s(28)))
        gy      = rect.y + L.s(62) + (avail_h - rows*(pill_h+gap))//2

        for i,lid in enumerate(lesson_ids):
            st   = status_dict.get(lid,"untouched")
            col_ = _sc(st)
            pr   = pygame.Rect(rect.x+L.s(8), gy+i*(pill_h+gap),
                               rect.w-L.s(16), pill_h)
            rounded_rect(screen,pr,col_,radius=L.s(6))
            if st=="mastered":
                _star(screen,pr.right-L.s(5),pr.y+L.s(5),L.s(5),C_GOLD)
            lbl = SHORT.get(lid,lid)
            tc  = (15,15,15) if st!="untouched" else (100,90,140)
            draw_text_centered(screen,lbl,Fonts.label(L.font_size(13)),tc,pr.center)

            # Accuracy badge right side
            if st != "untouched":
                d   = self._detail.get(lid,{})
                tot = d.get("total_attempts",0)
                cor = d.get("total_correct",0)
                if tot>0:
                    pct = f"{int(cor/tot*100)}%"
                    f   = pygame.font.Font(None,L.font_size(13))
                    ps  = f.render(pct,True,(15,15,15))
                    screen.blit(ps,(pr.right-ps.get_width()-L.s(4),
                                   pr.centery-ps.get_height()//2))

    # ══ TAB 1: ANALYTICS ══════════════════════════════════════════════════
    def _draw_analytics(self, screen, cr):
        # Layout: left column (60%) = charts, right column (40%) = metrics cards
        lw   = int(L.ui_w * 0.58)
        rw   = L.ui_w - lw - L.s(12)
        lx   = L.ui_x
        rx   = L.ui_x + lw + L.s(12)
        y    = cr.y + L.s(4)

        # ── LEFT: heatmap + accuracy sparkline + response time sparkline ──
        section_h = (cr.h - L.s(12)) // 3

        # 1. Activity heatmap
        sh_h = section_h - L.s(10)
        draw_text_centered(screen,"Activity — last 28 days",
                           Fonts.body(L.font_size(17)),Colors.TEXT_MUTED,
                           (lx+lw//2, y+L.s(8)))
        hm = pygame.Rect(lx, y+L.s(22), lw, L.s(18))
        _heatmap(screen, hm, self._sessions, 28)

        # Day labels
        today = date.today()
        lf_sm = pygame.font.Font(None,L.font_size(13))
        for i in range(0,28,7):
            d   = str(today-timedelta(days=27-i))
            try:
                from datetime import datetime
                lbl = datetime.strptime(d,"%Y-%m-%d").strftime("%d %b")
            except: lbl=d[-5:]
            cw  = max(3,(lw-27)//28); gap=2
            x_  = lx + i*(cw+gap)
            ls  = lf_sm.render(lbl,True,(80,72,120))
            screen.blit(ls,(x_,y+L.s(44)))

        # 2. Accuracy trend
        y2 = y + section_h
        draw_text_centered(screen,"Daily accuracy",
                           Fonts.body(L.font_size(17)),Colors.TEXT_MUTED,
                           (lx+lw//2, y2+L.s(6)))
        sp1 = pygame.Rect(lx, y2+L.s(22), lw, sh_h-L.s(26))
        rounded_rect(screen, sp1, C_PANEL, radius=L.s(6))
        # 80% ref line
        ref_y = sp1.bottom - int(.8*sp1.h)
        pygame.draw.line(screen,(70,60,100),(sp1.x,ref_y),(sp1.right,ref_y),1)
        screen.blit(lf_sm.render("80%",True,(70,60,100)),(sp1.right+L.s(2),ref_y-L.s(5)))
        vals = [v for v in self._daily_acc if v is not None]
        if len(vals) >= 2:
            _sparkline(screen, sp1, vals, (130,80,255))

        # 3. Response time trend (inverted: faster=higher)
        y3 = y + section_h*2
        draw_text_centered(screen,"Response speed  (↑ faster)",
                           Fonts.body(L.font_size(17)),Colors.TEXT_MUTED,
                           (lx+lw//2, y3+L.s(6)))
        sp2 = pygame.Rect(lx, y3+L.s(22), lw, sh_h-L.s(26))
        rounded_rect(screen, sp2, C_PANEL, radius=L.s(6))
        rt_vals = [v for v in self._daily_rt if v > 0]
        if len(rt_vals) >= 2:
            _sparkline(screen, sp2, rt_vals, (60,200,180))

        # ── RIGHT: metric cards ────────────────────────────────────────────
        all_lessons = LESSONS + SHAPES
        total_q  = sum(PT.get_lesson(l).get("total_attempts",0) for l in all_lessons)
        total_c  = sum(PT.get_lesson(l).get("total_correct",0)  for l in all_lessons)
        overall_acc = total_c/max(total_q,1)

        # Avg response time (from sessions)
        rt_list = [s["avg_response_s"] for s in self._sessions
                   if s.get("avg_response_s",0)>0]
        avg_rt  = round(sum(rt_list)/len(rt_list),1) if rt_list else 0

        # Avg first-attempt rate
        fa_rates = [v for v in self._fa_rate.values() if v>0]
        avg_fa   = round(sum(fa_rates)/len(fa_rates)*100) if fa_rates else 0

        days_active = len({s["date"] for s in self._sessions})

        # Best improvement: lesson with biggest accuracy gain over 2 weeks
        best_imp_lesson = "—"; best_imp_val = 0
        for lid in all_lessons:
            series = self._acc_series.get(lid,[])
            if len(series) >= 4:
                old_acc = series[0][1]
                new_acc = series[-1][1]
                if new_acc - old_acc > best_imp_val:
                    best_imp_val   = new_acc - old_acc
                    best_imp_lesson = SHORT.get(lid,lid)

        cards = [
            ("Overall accuracy",   f"{int(overall_acc*100)}%",  C_MASTER),
            ("Avg response time",  f"{avg_rt}s",                (60,200,180)),
            ("First-attempt rate", f"{avg_fa}%",                C_STARTED),
            ("Days active (28d)",  f"{days_active}",            C_GOLD),
            ("Questions answered", f"{total_q}",                C_ACCENT),
            ("Most improved",      best_imp_lesson,             (255,160,40)),
        ]
        card_h = (cr.h - L.s(8) - L.s(5)*(len(cards)-1)) // len(cards)
        for i,(lbl,val,col) in enumerate(cards):
            cy_ = y + i*(card_h+L.s(5))
            cr_ = pygame.Rect(rx, cy_, rw, card_h)
            rounded_rect(screen,cr_,C_PANEL,radius=L.s(10),
                         border_color=(*col,80),border_width=1)
            draw_text_centered(screen,val,
                               Fonts.title(L.font_size(30)),col,
                               (cr_.centerx, cr_.centery-L.s(8)))
            draw_text_centered(screen,lbl,
                               Fonts.label(L.font_size(14)),Colors.TEXT_MUTED,
                               (cr_.centerx, cr_.centery+L.s(14)))

        # ── Per-lesson accuracy mini-bars (below right cards if space) ────
        # Already shown well enough with the left sparklines


def run_progress(screen, ge: GestureEngine) -> str:
    return ProgressScreen(ge).run(screen)
