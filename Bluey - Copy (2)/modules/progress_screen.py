import cv2
import time
import string
import math
from modules.sound_player import play_sound

# ── layout ─────────────────────────────────────────────────────────────────
W, H   = 640, 480
FONT   = cv2.FONT_HERSHEY_SIMPLEX

# Grid: 9 letters per row, 3 rows  (A-I / J-R / S-Z)
COLS   = 9
RADIUS = 28        # circle radius for each letter bubble
GAP    = 12        # gap between circles
HOLD_S = 2

# ── colours (BGR) ──────────────────────────────────────────────────────────
C_MASTERED    = (60,  200, 90)     # green  – all 5 stages passed
C_INPROGRESS  = (30,  200, 220)    # yellow-ish (BGR) – started, not done
C_UNTOUCHED   = (100, 100, 100)    # gray   – never touched
C_STAR        = (0,   215, 255)    # gold star
C_RING        = (0,   220, 0)      # hold-progress ring
C_BACK_FILL   = (255, 255, 255)
C_BACK_TEXT   = (0,   0,   200)

ALL_LETTERS = list(string.ascii_uppercase)


# ── helpers ────────────────────────────────────────────────────────────────
def _stage_and_accuracy(letter: str, progress) -> tuple[int, float]:
    stage = progress.get_stage(letter)
    hist  = progress.get_history(letter)
    if not hist:
        return stage, 0.0
    recent = [h for h in hist if h["stage"] == stage]
    acc    = recent[-1]["accuracy"] if recent else 0.0
    return stage, acc


def _bubble_color(letter: str, progress) -> tuple:
    stage, acc = _stage_and_accuracy(letter, progress)
    hist = progress.get_history(letter)
    if not hist:
        return C_UNTOUCHED
    if stage >= 5 and any(h["stage"] == 5 and h["accuracy"] >= 0.8 for h in hist):
        return C_MASTERED
    return C_INPROGRESS


def _build_centers() -> list:
    """Return list of (letter, cx, cy) for the 26 bubbles."""
    diameter   = RADIUS * 2
    total_w    = COLS * diameter + (COLS - 1) * GAP
    x_start    = (W - total_w) // 2 + RADIUS
    y_start    = 110

    centers = []
    for i, letter in enumerate(ALL_LETTERS):
        col = i % COLS
        row = i // COLS
        cx  = x_start + col * (diameter + GAP)
        cy  = y_start + row * (diameter + GAP)
        centers.append((letter, cx, cy))
    return centers


def _draw_star(frame, cx, cy, r, color):
    """Draw a small 5-pointed star centred at (cx, cy) with outer radius r."""
    pts = []
    for k in range(10):
        angle = math.radians(-90 + k * 36)
        radius = r if k % 2 == 0 else r * 0.45
        pts.append((
            int(cx + radius * math.cos(angle)),
            int(cy + radius * math.sin(angle)),
        ))
    import numpy as np
    poly = np.array(pts, dtype=np.int32)
    cv2.fillPoly(frame, [poly], color)


def _accuracy_bar(frame, x, y, w, h, value: float, label: str):
    """Draw a thin labelled progress bar."""
    cv2.rectangle(frame, (x, y), (x + w, y + h), (60, 60, 60), -1)
    filled = int(w * value)
    if filled > 0:
        bar_color = C_MASTERED if value >= 0.8 else C_INPROGRESS
        cv2.rectangle(frame, (x, y), (x + filled, y + h), bar_color, -1)
    cv2.putText(frame, label, (x + w + 6, y + h - 1),
                FONT, 0.38, (200, 200, 200), 1)


# ── main screen ────────────────────────────────────────────────────────────
def show_progress(cap, tracker, progress):
    """
    Duolingo-style progress map.
    - Green filled circle  = mastered (stage 5, ≥ 80 %)
    - Yellow filled circle = in progress
    - Gray filled circle   = untouched
    - Gold star badge on mastered bubbles
    - Hover a bubble to see last accuracy bar + stage readout
    - Pinch-hold BACK to return
    """
    centers   = _build_centers()
    back_btn  = (W - 130, 15, 110, 50)
    hold_start  = None
    hold_target = None
    hovered_letter = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (W, H))
        landmarks = tracker.get_landmarks(frame)

        # ── header ─────────────────────────────────────────────────────────
        cv2.putText(frame, "Progress Map", (20, 48),
                    FONT, 1.1, (0, 120, 255), 3)
        summary = progress.summary()   # {letter: latest_accuracy}
        n_done  = sum(1 for l in ALL_LETTERS
                      if progress.get_stage(l) >= 5 and
                      any(h["stage"] == 5 and h["accuracy"] >= 0.8
                          for h in progress.get_history(l)))
        cv2.putText(frame, f"{n_done}/26 mastered",
                    (W - 170, 48), FONT, 0.65, (180, 180, 180), 1)

        # ── draw bubbles ───────────────────────────────────────────────────
        for letter, cx, cy in centers:
            color = _bubble_color(letter, progress)
            stage, acc = _stage_and_accuracy(letter, progress)
            hist  = progress.get_history(letter)

            # Outer glow ring for hovered
            if letter == hovered_letter:
                cv2.circle(frame, (cx, cy), RADIUS + 5, (200, 200, 200), 2)

            # Main bubble
            cv2.circle(frame, (cx, cy), RADIUS, color, -1)
            cv2.circle(frame, (cx, cy), RADIUS, (30, 30, 30), 1)   # border

            # Letter label
            text_color = (20, 20, 20) if color == C_UNTOUCHED else (240, 240, 240)
            cv2.putText(frame, letter,
                        (cx - 10, cy + 8), FONT, 0.75, text_color, 2)

            # Stage pip row beneath the letter (5 tiny dots = stages)
            for s in range(1, 6):
                pip_x = cx - 20 + (s - 1) * 10
                pip_y = cy + RADIUS - 6
                pip_color = (0, 200, 80) if s <= stage else (60, 60, 60)
                cv2.circle(frame, (pip_x, pip_y), 3, pip_color, -1)

            # Gold star for mastered
            if color == C_MASTERED:
                _draw_star(frame, cx + RADIUS - 8, cy - RADIUS + 8, 8, C_STAR)

        # ── detail panel for hovered letter ───────────────────────────────
        if hovered_letter:
            stage, acc = _stage_and_accuracy(hovered_letter, progress)
            hist = progress.get_history(hovered_letter)
            px, py = 20, H - 90

            cv2.rectangle(frame, (px - 4, py - 20),
                          (px + 260, py + 58), (30, 30, 30), -1)
            cv2.rectangle(frame, (px - 4, py - 20),
                          (px + 260, py + 58), (80, 80, 80), 1)

            cv2.putText(frame, f"Letter  {hovered_letter}",
                        (px, py), FONT, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Stage  {stage} / 5",
                        (px, py + 22), FONT, 0.6, (180, 180, 180), 1)

            _accuracy_bar(frame, px, py + 34, 180, 12, acc,
                          f"{int(acc * 100)}%")

            attempts = len(hist)
            cv2.putText(frame, f"{attempts} attempt{'s' if attempts != 1 else ''}",
                        (px + 195, py + 44), FONT, 0.42, (140, 140, 140), 1)

        # ── legend ─────────────────────────────────────────────────────────
        leg_y = H - 18
        for color, label, lx in [
            (C_MASTERED,   "Mastered",    20),
            (C_INPROGRESS, "In progress", 145),
            (C_UNTOUCHED,  "Not started", 285),
        ]:
            cv2.circle(frame, (lx + 7, leg_y), 7, color, -1)
            cv2.putText(frame, label, (lx + 20, leg_y + 5),
                        FONT, 0.45, (200, 200, 200), 1)

        # ── back button ────────────────────────────────────────────────────
        bx, by, bw, bh = back_btn
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), C_BACK_FILL, -1)
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (200, 200, 200), 1)
        cv2.putText(frame, "BACK", (bx + 18, by + 34), FONT, 0.9, C_BACK_TEXT, 2)

        # ── gesture ────────────────────────────────────────────────────────
        hovered_letter = None   # reset each frame
        if landmarks and len(landmarks) >= 9:
            x1, y1 = landmarks[4]
            x2, y2 = landmarks[8]
            cx_h, cy_h = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

            # Determine what's hovered
            hovered = None
            if bx < cx_h < bx + bw and by < cy_h < by + bh:
                hovered = "__BACK__"
            else:
                for letter, bcx, bcy in centers:
                    if math.hypot(cx_h - bcx, cy_h - bcy) < RADIUS + 6:
                        hovered = letter
                        hovered_letter = letter
                        break

            if dist < 40 and hovered is not None:
                if hold_target != hovered:
                    hold_start  = time.time()
                    hold_target = hovered

                elapsed  = time.time() - hold_start
                ring_prog = min(elapsed / HOLD_S, 1.0)
                cv2.ellipse(frame, (cx_h, cy_h), (38, 38),
                            -90, 0, ring_prog * 360, C_RING, 5)

                if ring_prog >= 1.0:
                    hold_start  = None
                    hold_target = None
                    if hovered == "__BACK__":
                        play_sound("assets/sounds/welcome.mp3")
                        break
                    # Future: tap a bubble → jump straight into that letter's session
            else:
                hold_start  = None
                hold_target = None

        tracker.draw_hand(frame)
        cv2.imshow("Progress Map", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Progress Map")
    except Exception:
        pass
