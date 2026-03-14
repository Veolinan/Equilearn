"""
tracing_engine.py
=================
Scaffold-and-fade letter / number tracing with gesture control.

Gestures
--------
  PINCH  (thumb + index < PINCH_DRAW px)  →  draw / trace
  OPEN PALM (all 5 fingers extended)      →  pause tracing (lift pen)
  CHECK button (pinch-hold 2 s)           →  score the attempt
  BACK  button (pinch-hold 2 s)           →  return to caller
  CLEAR button (pinch-hold 2 s)           →  wipe trail and retry

Visual feedback
---------------
  • Animated pen cursor follows index-finger tip while drawing
  • Trail drawn in cyan with slight thickness variation for a natural feel
  • Ghost template shown at opacity depending on stage (1.0 / 0.6 / 0.25 / 0)
  • Accuracy shown as a filled arc + percentage after CHECK
  • Green flash  →  ≥ 80 %    Yellow flash  →  60-79 %    Red flash  →  < 60 %
"""

import cv2
import time
import math
import numpy as np
from modules.sound_player import play_sound


# ─── tuneable constants ────────────────────────────────────────────────────
W, H          = 640, 480
FONT          = cv2.FONT_HERSHEY_SIMPLEX
PINCH_DRAW    = 45    # px  – thumb↔index distance that means "pen down"
OPEN_THRESH   = 80    # px  – thumb↔pinky distance that means "open palm / pause"
HOLD_BTN_S    = 2.0   # seconds to hold a button
ADVANCE_ACC   = 0.80  # accuracy needed to move to next stage
RETRY_ACC     = 0.60  # below this → repeat stage; above → hint + retry

# Trail drawing
TRAIL_COLOR   = (0, 240, 200)
TRAIL_WIDTH   = 7
MAX_TRAIL     = 2000  # max points kept (prevents memory growth on long sessions)

# Pen cursor
PEN_COLOR     = (255, 255, 255)
PEN_RADIUS    = 10
PEN_TIP_COLOR = (0, 200, 255)

# Button palette  (BGR)
BTN_CHECK  = (50,  200,  50)
BTN_CLEAR  = (50,  180, 220)
BTN_BACK   = (60,   60, 200)
BTN_TEXT   = (255, 255, 255)

# Template ghost colours
GHOST_COLOR = (200, 200,  50)   # yellow guide lines

# Stage opacities
STAGE_OPACITY = {1: 1.0, 2: 0.60, 3: 0.25, 4: 0.0, 5: 0.0}


# ─── gesture helpers ───────────────────────────────────────────────────────
def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _is_pinching(lm) -> bool:
    """Thumb tip (4) close to index tip (8)."""
    return _dist(lm[4], lm[8]) < PINCH_DRAW


def _is_open_palm(lm) -> bool:
    """
    All four fingers extended: each fingertip clearly above its MCP joint.
    MCP joints: index=5, middle=9, ring=13, pinky=17
    Tips:        index=8, middle=12, ring=16, pinky=20
    Also check thumb tip (4) far from index MCP (5) for a fully open hand.
    """
    tips = [8, 12, 16, 20]
    mcps = [5,  9, 13, 17]
    extended = all(lm[tip][1] < lm[mcp][1] - 20 for tip, mcp in zip(tips, mcps))
    thumb_out = _dist(lm[4], lm[5]) > 40
    return extended and thumb_out


# ─── button helpers ────────────────────────────────────────────────────────
class HoldButton:
    """A rectangle button that activates after the user pinch-hovers it for hold_s seconds."""

    def __init__(self, label: str, x: int, y: int, w: int, h: int,
                 color: tuple, hold_s: float = HOLD_BTN_S):
        self.label  = label
        self.rect   = (x, y, w, h)
        self.color  = color
        self.hold_s = hold_s
        self._start = None

    def reset(self):
        self._start = None

    def contains(self, cx: int, cy: int) -> bool:
        x, y, w, h = self.rect
        return x < cx < x + w and y < cy < y + h

    def update(self, cx: int, cy: int, pinching: bool) -> bool:
        """Call every frame. Returns True the moment hold completes."""
        if pinching and self.contains(cx, cy):
            if self._start is None:
                self._start = time.time()
            elapsed = time.time() - self._start
            if elapsed >= self.hold_s:
                self._start = None
                return True
        else:
            self._start = None
        return False

    def progress(self, cx: int, cy: int) -> float:
        """0.0–1.0 fill for the ring, only when cursor is inside."""
        if self._start and self.contains(cx, cy):
            return min((time.time() - self._start) / self.hold_s, 1.0)
        return 0.0

    def draw(self, frame, cx: int = -1, cy: int = -1):
        x, y, w, h = self.rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), self.color, -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (30, 30, 30), 1)
        cv2.putText(frame, self.label, (x + 8, y + h - 10),
                    FONT, 0.65, BTN_TEXT, 2)
        # draw hold ring if hovering
        prog = self.progress(cx, cy)
        if prog > 0:
            cx_b = x + w // 2
            cy_b = y + h // 2
            cv2.ellipse(frame, (cx_b, cy_b), (min(w, h) // 2 - 4, min(w, h) // 2 - 4),
                        -90, 0, prog * 360, (255, 255, 255), 3)


# ─── main engine ──────────────────────────────────────────────────────────
class TracingEngine:
    """
    Full tracing session for one symbol.
    Call  engine.run()  – returns when the child finishes or navigates back.
    """

    def __init__(self, cap, tracker, symbol: str, progress,
                 stage: int | None = None):
        self.cap      = cap
        self.tracker  = tracker
        self.symbol   = symbol
        self.progress = progress
        self.stage    = stage if stage is not None else progress.get_stage(symbol)
        self.stage    = max(1, min(self.stage, 4))   # tracing stages 1-4 only

        self._trail: list[tuple[int, int]] = []
        self._paused   = False     # open-palm pause
        self._checked  = False     # True after child taps CHECK
        self._accuracy = 0.0
        self._result_color = (200, 200, 200)

        self._template = self._load_template()

        # Buttons  (positioned bottom bar)
        self._btn_check = HoldButton("CHECK ✓", 60,  H - 65, 130, 52, BTN_CHECK)
        self._btn_clear = HoldButton("CLEAR",  250,  H - 65, 130, 52, BTN_CLEAR)
        self._btn_back  = HoldButton("BACK",   450,  H - 65, 130, 52, BTN_BACK)

    # ── template loading ──────────────────────────────────────────────────
    def _load_template(self) -> np.ndarray | None:
        """Try assets/letters or assets/numbers; fall back to rendered glyph."""
        for folder in ("letters", "numbers"):
            path = f"assets/{folder}/{self.symbol}.png"
            img  = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                return cv2.resize(img, (200, 280))

        # Render fallback
        canvas = np.zeros((280, 200), np.uint8)
        cv2.putText(canvas, self.symbol, (20, 240), FONT, 8, 255, 22)
        return canvas

    # ── template overlay ──────────────────────────────────────────────────
    def _draw_template(self, frame: np.ndarray):
        opacity = STAGE_OPACITY.get(self.stage, 0.0)
        if opacity <= 0 or self._template is None:
            return

        x_off, y_off = W // 2 - 100, H // 2 - 155
        th, tw = self._template.shape[:2]
        # Clip to frame bounds
        fy2 = min(y_off + th, H)
        fx2 = min(x_off + tw, W)
        ty2 = fy2 - y_off
        tx2 = fx2 - x_off

        region  = frame[y_off:fy2, x_off:fx2].copy()
        overlay = region.copy()
        mask    = self._template[:ty2, :tx2] > 128
        overlay[mask] = GHOST_COLOR

        cv2.addWeighted(overlay, opacity, region, 1.0 - opacity, 0, region)
        frame[y_off:fy2, x_off:fx2] = region

    # ── trail drawing ─────────────────────────────────────────────────────
    def _draw_trail(self, frame: np.ndarray):
        if len(self._trail) < 2:
            return
        pts = self._trail
        for i in range(1, len(pts)):
            # Slight width variation based on speed for a natural feel
            speed = _dist(pts[i], pts[i - 1])
            w     = max(3, TRAIL_WIDTH - int(speed * 0.05))
            cv2.line(frame, pts[i - 1], pts[i], TRAIL_COLOR, w, cv2.LINE_AA)

    # ── pen cursor ────────────────────────────────────────────────────────
    def _draw_pen(self, frame: np.ndarray, ix: int, iy: int, drawing: bool):
        """Draw a small pen/nib icon at the index fingertip."""
        # Outer circle
        color = PEN_TIP_COLOR if drawing else (160, 160, 160)
        cv2.circle(frame, (ix, iy), PEN_RADIUS, color, 2, cv2.LINE_AA)
        # Inner dot  – filled when drawing
        if drawing:
            cv2.circle(frame, (ix, iy), 4, PEN_TIP_COLOR, -1, cv2.LINE_AA)
        # Pen body lines  (diagonal nib)
        tip_x, tip_y = ix, iy
        cv2.line(frame, (tip_x, tip_y),
                 (tip_x + 14, tip_y - 20), color, 2, cv2.LINE_AA)
        cv2.line(frame, (tip_x + 14, tip_y - 20),
                 (tip_x + 20, tip_y - 30), (220, 220, 180), 2, cv2.LINE_AA)

    # ── accuracy scoring ──────────────────────────────────────────────────
    def _score(self) -> float:
        if len(self._trail) < 15 or self._template is None:
            return 0.0

        # Build a mask of where the child drew
        drawn = np.zeros((H, W), np.uint8)
        for pt in self._trail:
            cv2.circle(drawn, pt, 16, 255, -1)

        # Template mask in frame coords
        x_off, y_off = W // 2 - 100, H // 2 - 155
        tmpl_full = np.zeros((H, W), np.uint8)
        th, tw = self._template.shape[:2]
        fy2, fx2 = min(y_off + th, H), min(x_off + tw, W)
        tmpl_full[y_off:fy2, x_off:fx2] = self._template[:fy2 - y_off, :fx2 - x_off]

        template_px = int(np.count_nonzero(tmpl_full))
        if template_px == 0:
            return 0.0

        overlap = cv2.bitwise_and(drawn, tmpl_full)
        coverage = int(np.count_nonzero(overlap)) / template_px

        # Penalise drawing wildly outside the template
        drawn_px = int(np.count_nonzero(drawn))
        outside  = drawn_px - int(np.count_nonzero(overlap))
        waste    = outside / max(drawn_px, 1)
        acc = coverage * (1.0 - 0.4 * waste)
        return float(np.clip(acc, 0.0, 1.0))

    # ── result arc ────────────────────────────────────────────────────────
    def _draw_result(self, frame: np.ndarray):
        if not self._checked:
            return
        acc   = self._accuracy
        cx, cy = W - 80, 80
        r      = 50
        # Background arc
        cv2.ellipse(frame, (cx, cy), (r, r), -90, 0, 360, (60, 60, 60), 8)
        # Filled arc
        cv2.ellipse(frame, (cx, cy), (r, r), -90, 0,
                    int(360 * acc), self._result_color, 8, cv2.LINE_AA)
        pct = f"{int(acc * 100)}%"
        cv2.putText(frame, pct, (cx - 22, cy + 8), FONT, 0.75,
                    self._result_color, 2)
        # Verdict text
        verdict = ("Amazing!" if acc >= 0.9
                   else "Well done!" if acc >= 0.8
                   else "Good try!" if acc >= 0.6
                   else "Try again!")
        cv2.putText(frame, verdict, (cx - 38, cy + r + 22),
                    FONT, 0.55, self._result_color, 2)

    # ── HUD ───────────────────────────────────────────────────────────────
    def _draw_hud(self, frame: np.ndarray, paused: bool):
        stage_names = {1: "Watch & copy", 2: "Trace (guided)",
                       3: "Trace (faded)", 4: "Trace (free)"}
        cv2.putText(frame,
                    f"Trace  {self.symbol}   –  Stage {self.stage}/4",
                    (16, 40), FONT, 0.85, (0, 180, 255), 2)
        cv2.putText(frame, stage_names.get(self.stage, ""),
                    (16, 64), FONT, 0.55, (160, 160, 160), 1)

        if paused:
            # Semi-transparent pause banner
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, H // 2 - 30), (W, H // 2 + 30),
                          (30, 30, 30), -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            cv2.putText(frame, "PAUSED  –  open palm",
                        (130, H // 2 + 12), FONT, 1.0, (200, 200, 50), 3)

        # Gesture hints  (bottom-left corner above buttons)
        cv2.putText(frame, "Pinch = draw    Open hand = pause",
                    (16, H - 76), FONT, 0.42, (120, 120, 120), 1)

    # ── main run loop ─────────────────────────────────────────────────────
    def run(self):
        self._trail   = []
        self._checked = False
        self._paused  = False
        self._btn_check.reset()
        self._btn_clear.reset()
        self._btn_back.reset()

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame     = cv2.flip(frame, 1)
            frame     = cv2.resize(frame, (W, H))
            landmarks = self.tracker.get_landmarks(frame)

            # ── draw layers (back → front) ────────────────────────────────
            self._draw_template(frame)
            self._draw_trail(frame)
            self._draw_result(frame)
            self._draw_hud(frame, self._paused)

            # Buttons  (always visible)
            cx_cursor = cy_cursor = -1
            pinching  = False

            if landmarks and len(landmarks) >= 21:
                ix, iy = landmarks[8]    # index tip
                tx, ty = landmarks[4]    # thumb tip
                cx_cursor = (ix + tx) // 2
                cy_cursor = (iy + ty) // 2
                pinching  = _is_pinching(landmarks)
                paused    = _is_open_palm(landmarks)
                self._paused = paused

                # ── draw pen cursor ───────────────────────────────────────
                drawing_now = pinching and not paused and not self._checked
                self._draw_pen(frame, ix, iy, drawing_now)

                # ── collect trail points ──────────────────────────────────
                if drawing_now:
                    self._trail.append((ix, iy))
                    if len(self._trail) > MAX_TRAIL:
                        self._trail.pop(0)

            # Draw buttons (after pen so ring is on top)
            self._btn_check.draw(frame, cx_cursor, cy_cursor)
            self._btn_clear.draw(frame, cx_cursor, cy_cursor)
            self._btn_back.draw(frame,  cx_cursor, cy_cursor)

            # ── button logic ──────────────────────────────────────────────
            if self._btn_back.update(cx_cursor, cy_cursor, pinching):
                play_sound("assets/sounds/welcome.mp3")
                break

            if self._btn_clear.update(cx_cursor, cy_cursor, pinching):
                self._trail   = []
                self._checked = False
                play_sound("assets/sounds/welcome.mp3")

            if self._btn_check.update(cx_cursor, cy_cursor, pinching):
                self._checked  = True
                self._accuracy = self._score()
                self.progress.record(self.symbol, self.stage, self._accuracy)

                if self._accuracy >= ADVANCE_ACC:
                    self._result_color = (50, 220, 80)     # green
                    play_sound("assets/sounds/well_done.mp3")
                    # Advance stage after brief display
                    self._show_result_pause(frame, 2.5)
                    next_stage = self.stage + 1
                    if next_stage <= 4:
                        self.progress.set_stage(self.symbol, next_stage)
                        self.stage    = next_stage
                        self._trail   = []
                        self._checked = False
                        self._btn_check.reset()
                        self._btn_clear.reset()
                        continue
                    else:
                        # All tracing stages complete → recognition quiz
                        self.progress.set_stage(self.symbol, 5)
                        break

                elif self._accuracy >= RETRY_ACC:
                    self._result_color = (0, 200, 230)     # yellow-ish
                    play_sound("assets/sounds/correct.mp3")
                else:
                    self._result_color = (60,  60, 220)    # red-ish
                    play_sound("assets/sounds/wrong.mp3")

            self.tracker.draw_hand(frame)
            cv2.imshow("Tracing", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        try:
            cv2.destroyWindow("Tracing")
        except Exception:
            pass

    # ── brief display pause after completing a stage ──────────────────────
    def _show_result_pause(self, last_frame, duration: float):
        end = time.time() + duration
        while time.time() < end:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (W, H))
            self._draw_template(frame)
            self._draw_trail(frame)
            self._draw_result(frame)

            pct = int(self._accuracy * 100)
            cv2.putText(frame, f"Stage complete!  {pct}%",
                        (120, H // 2), FONT, 1.4, self._result_color, 4)
            cv2.imshow("Tracing", frame)
            cv2.waitKey(33)