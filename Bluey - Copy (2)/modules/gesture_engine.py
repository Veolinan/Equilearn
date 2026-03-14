# modules/gesture_engine.py
import cv2, math, threading, time
import numpy as np
import pygame

import mediapipe as mp
from mediapipe import Image, ImageFormat
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions

import os, urllib.request

# ── model ─────────────────────────────────────────────────────────────────────
MODEL_PATH = "hand_landmarker.task"
MODEL_URL  = ("https://storage.googleapis.com/mediapipe-models/"
              "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")

def _ensure_model():
    if not os.path.exists(MODEL_PATH):
        print(f"Downloading hand landmark model → {MODEL_PATH} …")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Download complete.")

# ── hand connections ───────────────────────────────────────────────────────────
_HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]

# ── tuning ─────────────────────────────────────────────────────────────────────
PINCH_THRESHOLD   = 0.28   # normalised pinch distance
SMOOTHING         = 0.18   # EMA for open hand
SMOOTHING_PINCH   = 0.10   # EMA for pinching (fingers occlude = more noise)

# Ghost persistence — how many seconds to keep showing the last known hand
# after detection drops out.  Eliminates flicker entirely for brief dropouts.
GHOST_SECONDS     = 0.18

# Camera target FPS — cap read loop to avoid hammering the detector
CAM_FPS           = 30


class GestureState:
    IDLE      = "IDLE"
    POINTING  = "POINTING"
    PINCHING  = "PINCHING"
    OPEN_PALM = "OPEN_PALM"
    THUMBS_UP = "THUMBS_UP"
    FINGERS_N = "FINGERS_N"
    FIST      = "FIST"


class GestureFrame:
    def __init__(self):
        self.state        = GestureState.IDLE
        self.cursor       = (0, 0)
        self.finger_count = 0
        self.landmarks    = []
        self.hand_visible = False
        self.wrist_y      = 0
        self.is_ghost     = False   # True when using last-known position

    @property
    def is_pinching(self):  return self.state == GestureState.PINCHING
    @property
    def is_pointing(self):  return self.state in (GestureState.POINTING,
                                                   GestureState.PINCHING)
    @property
    def is_fist(self):      return self.state == GestureState.FIST


class GestureEngine:
    def __init__(self, cap, screen_w: int, screen_h: int, mirror: bool = True):
        self.cap      = cap
        self.sw       = screen_w
        self.sh       = screen_h
        self.mirror   = mirror
        self._lock    = threading.Lock()
        self._running = True

        # Smoothing state
        self._smooth    = None
        self._smooth_lm = None

        # Ghost: hold the last real frame for GHOST_SECONDS after dropout
        self._last_real_gf   = GestureFrame()
        self._last_real_time = 0.0

        # Published frame (what get() returns)
        self._latest = GestureFrame()

        _ensure_model()

        # ── Use VIDEO mode: temporal tracking, far fewer dropouts ─────────
        opts = HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=mp_vision.RunningMode.VIDEO,  # KEY CHANGE
            num_hands=1,
            min_hand_detection_confidence=0.5,   # lowered: easier to first-find
            min_hand_presence_confidence=0.4,    # lowered: easier to keep tracking
            min_tracking_confidence=0.4,         # lowered: fewer mid-track drops
        )
        self._landmarker = HandLandmarker.create_from_options(opts)
        self._frame_ts_ms = 0   # monotonic timestamp for VIDEO mode

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ── background capture loop ────────────────────────────────────────────
    def _loop(self):
        frame_interval = 1.0 / CAM_FPS

        while self._running:
            t0 = time.time()

            ret, raw = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            if self.mirror:
                raw = cv2.flip(raw, 1)

            rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)

            try:
                # VIDEO mode requires a monotonically increasing timestamp in ms
                self._frame_ts_ms += int(frame_interval * 1000)
                mp_img = Image(image_format=ImageFormat.SRGB, data=rgb)
                result = self._landmarker.detect_for_video(
                    mp_img, self._frame_ts_ms)
                hands = []
                if result.hand_landmarks:
                    hands = [[(lm.x, lm.y) for lm in hand]
                             for hand in result.hand_landmarks]
            except Exception:
                hands = []

            now = time.time()
            gf  = self._parse(hands, now)

            with self._lock:
                self._latest = gf

            # Pace the loop — don't burn CPU faster than the camera delivers
            elapsed = time.time() - t0
            sleep   = frame_interval - elapsed
            if sleep > 0:
                time.sleep(sleep)

    # ── parse raw landmarks into a GestureFrame ────────────────────────────
    def _parse(self, hands: list, now: float) -> GestureFrame:

        if hands:
            # ── Real detection ─────────────────────────────────────────────
            MARGIN = 0.15
            def remap(v, lo, hi, out):
                return int((max(lo, min(hi, v)) - lo) / (hi - lo) * out)

            lm = [(remap(x, MARGIN, 1.0 - MARGIN, self.sw),
                   remap(y, MARGIN, 1.0 - MARGIN, self.sh))
                  for x, y in hands[0]]

            # Smooth all landmarks
            if self._smooth_lm is None:
                self._smooth_lm = lm[:]
            else:
                self._smooth_lm = [
                    (int(self._smooth_lm[i][0]
                         + SMOOTHING * (lm[i][0] - self._smooth_lm[i][0])),
                     int(self._smooth_lm[i][1]
                         + SMOOTHING * (lm[i][1] - self._smooth_lm[i][1])))
                    for i in range(len(lm))
                ]

            # Pinch
            hand_size  = math.hypot(lm[0][0]-lm[9][0], lm[0][1]-lm[9][1])
            pinch_dist = math.hypot(lm[4][0]-lm[8][0], lm[4][1]-lm[8][1])
            norm_pinch = pinch_dist / max(hand_size, 1)
            is_pinch   = norm_pinch < PINCH_THRESHOLD

            # Smooth cursor
            raw_cur = ((lm[4][0] + lm[8][0]) // 2,
                       (lm[4][1] + lm[8][1]) // 2)
            factor = SMOOTHING_PINCH if is_pinch else SMOOTHING
            if self._smooth is None:
                self._smooth = raw_cur
            else:
                sx = self._smooth[0] + factor * (raw_cur[0] - self._smooth[0])
                sy = self._smooth[1] + factor * (raw_cur[1] - self._smooth[1])
                self._smooth = (int(sx), int(sy))

            # Gesture classification
            tips = [8, 12, 16, 20]; pips = [6, 10, 14, 18]
            extended  = [lm[t][1] < lm[p][1] for t, p in zip(tips, pips)]
            count     = sum(extended)
            thumb_ext = math.hypot(lm[4][0]-lm[5][0],
                                   lm[4][1]-lm[5][1]) > hand_size * 0.45

            gf = GestureFrame()
            gf.hand_visible = True
            gf.landmarks    = self._smooth_lm
            gf.cursor       = self._smooth
            gf.wrist_y      = lm[0][1]
            gf.is_ghost     = False

            if norm_pinch < PINCH_THRESHOLD:
                gf.state = GestureState.PINCHING
            elif all(extended) and thumb_ext:
                gf.state = GestureState.OPEN_PALM
            elif not any(extended) and not thumb_ext:
                gf.state = GestureState.FIST
            elif not any(extended) and thumb_ext:
                gf.state = GestureState.THUMBS_UP
            elif extended[0] and not any(extended[1:]):
                gf.state = GestureState.POINTING
            elif count > 0:
                gf.state        = GestureState.FINGERS_N
                gf.finger_count = count
            else:
                gf.state = GestureState.IDLE

            # Save as last known real frame
            self._last_real_gf   = gf
            self._last_real_time = now
            return gf

        else:
            # ── No detection — use ghost if within grace window ────────────
            age = now - self._last_real_time
            if age < GHOST_SECONDS and self._last_real_gf.hand_visible:
                ghost          = GestureFrame()
                ghost.__dict__ = dict(self._last_real_gf.__dict__)
                ghost.is_ghost = True
                # Ghost never fires pinch — prevents phantom selections
                if ghost.state == GestureState.PINCHING:
                    ghost.state = GestureState.POINTING
                return ghost

            # Ghost expired — truly no hand
            self._smooth    = None
            self._smooth_lm = None
            gf = GestureFrame()
            gf.cursor = (self._last_real_gf.cursor
                         if self._last_real_gf.hand_visible
                         else (self.sw // 2, self.sh // 2))
            return gf

    # ── public API ─────────────────────────────────────────────────────────
    def get(self) -> GestureFrame:
        with self._lock:
            return self._latest

    def stop(self):
        self._running = False
        try:
            self._landmarker.close()
        except Exception:
            pass

    def draw_debug(self, surface, gf: GestureFrame):
        if not gf.landmarks:
            return
        color = (60, 200, 255) if not gf.is_ghost else (150, 150, 150)
        for a, b in _HAND_CONNECTIONS:
            pygame.draw.line(surface, color,
                             gf.landmarks[a], gf.landmarks[b], 2)
        for x, y in gf.landmarks:
            pygame.draw.circle(surface, (255, 255, 255), (x, y), 4)


# ── Hold-to-select tracker ─────────────────────────────────────────────────────
class HoldDetector:
    """
    Hold progress with grace period — brief dropouts don't reset the ring.
    Ghost frames (is_ghost=True) are treated as inactive to prevent
    phantom selections when the hand briefly disappears.
    """
    GRACE_S = 0.25

    def __init__(self, hold_seconds: float = 1.5):
        self.hold_seconds = hold_seconds
        self._start      : dict[str, float] = {}
        self._last_active: dict[str, float] = {}
        self._progress   : dict[str, float] = {}

    def update(self, key: str, active: bool) -> tuple[float, bool]:
        now = time.time()

        if active:
            self._last_active[key] = now
            if key not in self._start:
                already = self._progress.get(key, 0.0)
                self._start[key] = now - already * self.hold_seconds

            elapsed  = now - self._start[key]
            progress = min(elapsed / self.hold_seconds, 1.0)
            self._progress[key] = progress

            if progress >= 1.0:
                for d in (self._start, self._last_active, self._progress):
                    d.pop(key, None)
                return 1.0, True
            return progress, False

        else:
            last = self._last_active.get(key)
            if last and (now - last) < self.GRACE_S:
                return self._progress.get(key, 0.0), False

            for d in (self._start, self._last_active, self._progress):
                d.pop(key, None)
            return 0.0, False

    def reset(self, key: str | None = None):
        if key is None:
            self._start.clear()
            self._last_active.clear()
            self._progress.clear()
        else:
            for d in (self._start, self._last_active, self._progress):
                d.pop(key, None)
