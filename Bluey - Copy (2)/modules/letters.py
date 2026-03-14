import cv2
import time
import string
from modules.sound_player import play_sound

# ── constants ──────────────────────────────────────────────────────────────
W, H   = 640, 480
FONT   = cv2.FONT_HERSHEY_SIMPLEX
COLS   = 9          # letters per row  (A-I, J-R, S-Z + gap)
ROWS   = 3
BTN_W  = 58
BTN_H  = 58
PAD_X  = 10
PAD_Y  = 10
HOLD_S = 3          # seconds to hold pinch for selection
PINCH  = 40         # pixel distance for pinch

ALL_LETTERS = list(string.ascii_uppercase)   # A … Z


# ── colour helpers ─────────────────────────────────────────────────────────
COLOR_MASTERED   = (60,  200, 90)    # green  – stage 5 complete
COLOR_INPROGRESS = (30,  180, 230)   # amber-ish (BGR: blue channel low) – started
COLOR_UNTOUCHED  = (160, 160, 160)   # gray
COLOR_TEXT_DARK  = (20,  20,  20)
COLOR_TEXT_LIGHT = (240, 240, 240)
COLOR_BACK_BTN   = (255, 255, 255)
COLOR_BACK_TEXT  = (0,   0,   200)


def _letter_color(letter: str, progress) -> tuple:
    """Return BGR fill color for a letter tile based on progress stage."""
    stage = progress.get_stage(letter)
    hist  = progress.get_history(letter)
    if not hist:
        return COLOR_UNTOUCHED
    if stage >= 5 and any(h["stage"] == 5 and h["accuracy"] >= 0.8 for h in hist):
        return COLOR_MASTERED
    return COLOR_INPROGRESS


def _build_grid() -> list:
    """Return list of (letter, (x, y, w, h)) for the 26-letter grid."""
    boxes = []
    total_w = COLS * BTN_W + (COLS - 1) * PAD_X
    x_start = (W - total_w) // 2
    y_start = 90

    for i, letter in enumerate(ALL_LETTERS):
        col = i % COLS
        row = i // COLS
        x = x_start + col * (BTN_W + PAD_X)
        y = y_start + row * (BTN_H + PAD_Y)
        boxes.append((letter, (x, y, BTN_W, BTN_H)))
    return boxes


# ── public entry point ─────────────────────────────────────────────────────
def run_letters(cap, tracker, progress):
    """
    Show an A-Z grid coloured by progress.
    Pinch-hold a letter to launch its tracing session.
    """
    # Import here to avoid circular imports at module load time
    from modules.tracing_engine import TracingEngine

    grid      = _build_grid()
    back_btn  = (W - 130, 15, 110, 50)
    hold_start = None
    hold_target = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (W, H))
        landmarks = tracker.get_landmarks(frame)

        # ── draw header ────────────────────────────────────────────────────
        cv2.putText(frame, "Choose a letter to practise",
                    (20, 55), FONT, 0.9, (0, 120, 255), 2)

        # ── draw letter grid ───────────────────────────────────────────────
        for letter, (x, y, bw, bh) in grid:
            fill  = _letter_color(letter, progress)
            stage = progress.get_stage(letter)
            hist  = progress.get_history(letter)

            cv2.rectangle(frame, (x, y), (x + bw, y + bh), fill, -1)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (50, 50, 50), 1)

            # Star badge for mastered letters
            if stage >= 5 and any(h["stage"] == 5 and h["accuracy"] >= 0.8
                                  for h in hist):
                cv2.putText(frame, "*", (x + bw - 16, y + 14),
                            FONT, 0.5, (255, 220, 0), 2)

            text_color = COLOR_TEXT_DARK if fill == COLOR_UNTOUCHED else COLOR_TEXT_LIGHT
            cv2.putText(frame, letter,
                        (x + 14, y + bh - 14), FONT, 1.1, text_color, 2)

        # ── legend ─────────────────────────────────────────────────────────
        leg_y = H - 28
        for color, label, lx in [
            (COLOR_MASTERED,   "Mastered",    20),
            (COLOR_INPROGRESS, "In progress", 140),
            (COLOR_UNTOUCHED,  "Not started", 280),
        ]:
            cv2.circle(frame, (lx + 8, leg_y), 8, color, -1)
            cv2.putText(frame, label, (lx + 22, leg_y + 5),
                        FONT, 0.5, (220, 220, 220), 1)

        # ── back button ────────────────────────────────────────────────────
        bx, by, bw, bh = back_btn
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), COLOR_BACK_BTN, -1)
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (200, 200, 200), 1)
        cv2.putText(frame, "BACK", (bx + 18, by + 34), FONT, 0.9, COLOR_BACK_TEXT, 2)

        # ── gesture detection ──────────────────────────────────────────────
        if landmarks and len(landmarks) >= 9:
            x1, y1 = landmarks[4]   # thumb tip
            x2, y2 = landmarks[8]   # index tip
            cx, cy  = (x1 + x2) // 2, (y1 + y2) // 2
            dist    = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

            # find what's being hovered
            hovered = None
            if bx < cx < bx + bw and by < cy < by + bh:
                hovered = "__BACK__"
            else:
                for letter, (x, y, lbw, lbh) in grid:
                    if x < cx < x + lbw and y < cy < y + lbh:
                        hovered = letter
                        break

            if dist < PINCH and hovered is not None:
                if hold_target != hovered:
                    hold_start  = time.time()
                    hold_target = hovered

                elapsed  = time.time() - hold_start
                progress_ = min(elapsed / HOLD_S, 1.0)
                cv2.ellipse(frame, (cx, cy), (38, 38),
                            -90, 0, progress_ * 360, (0, 220, 0), 5)

                if progress_ >= 1.0:
                    hold_start  = None
                    hold_target = None

                    if hovered == "__BACK__":
                        play_sound("assets/sounds/welcome.mp3")
                        break

                    # ── launch tracing session for chosen letter ───────────
                    play_sound("assets/sounds/welcome.mp3")
                    try:
                        cv2.destroyWindow("Letters")
                    except Exception:
                        pass
                    engine = TracingEngine(cap, tracker, hovered, progress)
                    engine.run()
                    time.sleep(0.5)
            else:
                hold_start  = None
                hold_target = None

        tracker.draw_hand(frame)
        cv2.imshow("Letters", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Letters")
    except Exception:
        pass
