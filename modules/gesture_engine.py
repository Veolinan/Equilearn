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

# ── download model once ────────────────────────────────────────────────────
MODEL_PATH = "hand_landmarker.task"
MODEL_URL  = ("https://storage.googleapis.com/mediapipe-models/"
              "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")

def _ensure_model():
    if not os.path.exists(MODEL_PATH):
        print(f"Downloading hand landmark model → {MODEL_PATH} …")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Download complete.")

# ── hand connections for debug skeleton ───────────────────────────────────
_HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]

PINCH_THRESHOLD  = 0.28   # normalised — real pinch ~0.20-0.26, open hand ~0.5+
SMOOTHING        = 0.18   # EMA factor — lower = smoother but slightly laggier
SMOOTHING_PINCH  = 0.10   # extra dampening when pinching (fingers touching = more noise)


class GestureState:
    IDLE      = "IDLE"
    POINTING  = "POINTING"
    PINCHING  = "PINCHING"
    OPEN_PALM = "OPEN_PALM"
    THUMBS_UP = "THUMBS_UP"
    FINGERS_N = "FINGERS_N"
    FIST      = "FIST"       # all fingers curled — use for drag/scroll


class GestureFrame:
    def __init__(self):
        self.state        = GestureState.IDLE
        self.cursor       = (0, 0)
        self.finger_count = 0
        self.landmarks    = []
        self.hand_visible = False
        self.wrist_y      = 0    # raw wrist Y in screen pixels (for scroll drag)

    @property
    def is_pinching(self):
        return self.state == GestureState.PINCHING

    @property
    def is_pointing(self):
        return self.state in (GestureState.POINTING, GestureState.PINCHING)

    @property
    def is_fist(self):
        return self.state == GestureState.FIST


class GestureEngine:
    def __init__(self, cap, screen_w: int, screen_h: int, mirror: bool = True):
        self.cap      = cap
        self.sw       = screen_w
        self.sh       = screen_h
        self.mirror   = mirror
        self._latest  = GestureFrame()
        self._lock    = threading.Lock()
        self._running = True
        self._smooth  = None

        _ensure_model()

        opts = HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self._landmarker = HandLandmarker.create_from_options(opts)

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            ret, raw = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            if self.mirror:
                raw = cv2.flip(raw, 1)
            rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
            try:
                mp_img = Image(image_format=ImageFormat.SRGB, data=rgb)
                result = self._landmarker.detect(mp_img)
                hands  = []
                if result.hand_landmarks:
                    hands = [[(lm.x, lm.y) for lm in hand]
                             for hand in result.hand_landmarks]
            except Exception as e:
                hands = []
            gf = self._parse(hands)
            with self._lock:
                self._latest = gf

    def _parse(self, hands: list) -> GestureFrame:
        gf = GestureFrame()
        if not hands:
            self._smooth    = None
            self._smooth_lm = None
            gf.cursor = (self.sw // 2, self.sh // 2)
            return gf

        # ── Safe-zone remapping ───────────────────────────────────────────
        # The camera sees the full frame but hands near edges go out of shot.
        # We remap the central 70% of the camera (15%–85%) to fill the full
        # screen, so the child never needs to point at the physical edge.
        MARGIN = 0.15   # ignore outer 15% of camera on each side

        def remap(v: float, lo: float, hi: float, out: int) -> int:
            clamped = max(lo, min(hi, v))
            return int((clamped - lo) / (hi - lo) * out)

        lm = [
            (remap(x, MARGIN, 1.0 - MARGIN, self.sw),
             remap(y, MARGIN, 1.0 - MARGIN, self.sh))
            for x, y in hands[0]
        ]

        gf.hand_visible = True
        gf.wrist_y      = lm[0][1]   # raw wrist Y for scroll tracking

        # Smooth all 21 landmarks — reduces skeleton jitter visually
        if not hasattr(self, '_smooth_lm') or self._smooth_lm is None:
            self._smooth_lm = lm[:]
        else:
            self._smooth_lm = [
                (int(self._smooth_lm[i][0] + SMOOTHING * (lm[i][0] - self._smooth_lm[i][0])),
                 int(self._smooth_lm[i][1] + SMOOTHING * (lm[i][1] - self._smooth_lm[i][1])))
                for i in range(len(lm))
            ]
        gf.landmarks = self._smooth_lm

        # Pinch distance — compute on raw lm (not smoothed) for accurate detection
        hand_size  = math.hypot(lm[0][0]-lm[9][0], lm[0][1]-lm[9][1])
        pinch_dist = math.hypot(lm[4][0]-lm[8][0], lm[4][1]-lm[8][1])
        norm_pinch = pinch_dist / max(hand_size, 1)
        is_pinch   = norm_pinch < PINCH_THRESHOLD

        # Cursor: midpoint of thumb+index, with stronger smoothing when pinching
        raw_cur = ((lm[4][0] + lm[8][0]) // 2,
                   (lm[4][1] + lm[8][1]) // 2)
        factor = SMOOTHING_PINCH if is_pinch else SMOOTHING
        if self._smooth is None:
            self._smooth = raw_cur
        else:
            sx = self._smooth[0] + factor * (raw_cur[0] - self._smooth[0])
            sy = self._smooth[1] + factor * (raw_cur[1] - self._smooth[1])
            self._smooth = (int(sx), int(sy))
        gf.cursor = self._smooth

        # Finger extension
        tips = [8, 12, 16, 20];  pips = [6, 10, 14, 18]
        extended   = [lm[t][1] < lm[p][1] for t, p in zip(tips, pips)]
        count      = sum(extended)
        # Thumb extended = tip far from index MCP — works regardless of mirror
        thumb_ext  = math.hypot(lm[4][0]-lm[5][0],
                                lm[4][1]-lm[5][1]) > hand_size * 0.45

        if norm_pinch < PINCH_THRESHOLD:
            gf.state = GestureState.PINCHING
        elif all(extended) and thumb_ext:
            gf.state = GestureState.OPEN_PALM
        elif not any(extended) and not thumb_ext:
            # All fingers AND thumb curled in → fist
            gf.state = GestureState.FIST
        elif not any(extended) and thumb_ext:
            gf.state = GestureState.THUMBS_UP
        elif extended[0] and not any(extended[1:]):
            gf.state = GestureState.POINTING
        elif count > 0:
            gf.state = GestureState.FINGERS_N
            gf.finger_count = count
        else:
            gf.state = GestureState.IDLE

        return gf

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
        for a, b in _HAND_CONNECTIONS:
            pygame.draw.line(surface, (60, 200, 255),
                             gf.landmarks[a], gf.landmarks[b], 2)
        for x, y in gf.landmarks:
            pygame.draw.circle(surface, (255, 255, 255), (x, y), 4)


# ── Hold-to-select tracker ─────────────────────────────────────────────────
class HoldDetector:
    """
    Tracks pinch-hold progress with a grace period.
    Brief interruptions (hand flicker, single dropped frame) do not reset
    progress — the hold timer only resets if the pinch breaks for longer
    than GRACE_S seconds.
    """
    GRACE_S = 0.22   # seconds of interrupted pinch tolerated before reset

    def __init__(self, hold_seconds: float = 1.5):
        self.hold_seconds = hold_seconds
        self._start     : dict[str, float] = {}   # key → hold start time
        self._last_active: dict[str, float] = {}  # key → last time active=True
        self._progress  : dict[str, float] = {}   # key → frozen progress at break

    def update(self, key: str, active: bool) -> tuple[float, bool]:
        now = time.time()

        if active:
            self._last_active[key] = now

            if key not in self._start:
                # Fresh start or resuming after grace — adjust start so
                # progress continues from where it was
                already = self._progress.get(key, 0.0)
                self._start[key] = now - already * self.hold_seconds

            elapsed  = now - self._start[key]
            progress = min(elapsed / self.hold_seconds, 1.0)
            self._progress[key] = progress

            if progress >= 1.0:
                # Clean up and fire
                for d in (self._start, self._last_active, self._progress):
                    d.pop(key, None)
                return 1.0, True
            return progress, False

        else:
            last = self._last_active.get(key)
            if last and (now - last) < self.GRACE_S:
                # Within grace period — freeze progress, keep start alive
                return self._progress.get(key, 0.0), False

            # Grace period expired — full reset
            for d in (self._start, self._last_active, self._progress):
                d.pop(key, None)
            return 0.0, False

    def reset(self, key: str | None = None):
        """Manually reset one key or all keys."""
        if key is None:
            self._start.clear()
            self._last_active.clear()
            self._progress.clear()
        else:
            for d in (self._start, self._last_active, self._progress):
                d.pop(key, None)
