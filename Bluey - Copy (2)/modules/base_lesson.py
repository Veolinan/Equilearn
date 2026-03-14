# modules/base_lesson.py
import cv2, time
from modules.sound_player import play_sound

class BaseLesson:
    """All lessons inherit from this. Override draw_content() and check_answer()."""

    HOLD_SECONDS = 3          # seconds to hold pinch for selection
    PINCH_THRESHOLD = 40      # pixel distance for pinch detection
    W, H = 640, 480
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    def __init__(self, cap, tracker, title="Lesson"):
        self.cap = cap
        self.tracker = tracker
        self.title = title
        self.hold_start = None
        self.hold_target = None
        self.result = ""
        self.result_time = 0
        self.running = True
        # Back button — fixed position, top-right
        self.back_btn = (self.W - 130, 15, 110, 50)

    # ── subclasses override these ──────────────────────────────────────────
    def get_option_boxes(self) -> list:
        """Return list of (value, (x, y, w, h)) tuples."""
        raise NotImplementedError

    def draw_content(self, frame):
        """Draw question, emojis, anything lesson-specific."""
        raise NotImplementedError

    def check_answer(self, value) -> bool:
        """Return True if value is the correct answer."""
        raise NotImplementedError

    def on_correct(self):
        play_sound("assets/sounds/correct.mp3")
        self.result = "Correct!"
        self.result_time = time.time()

    def on_wrong(self):
        play_sound("assets/sounds/wrong.mp3")
        self.result = "Wrong!"
        self.result_time = time.time()
    # ──────────────────────────────────────────────────────────────────────

    def draw_back_button(self, frame):
        bx, by, bw, bh = self.back_btn
        cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), (255,255,255), -1)
        cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), (200,200,200), 2)
        cv2.putText(frame, "BACK", (bx+18, by+34), self.FONT, 0.9, (0,0,200), 2)

    def draw_options(self, frame):
        for val, (x, y, bw, bh) in self.get_option_boxes():
            cv2.rectangle(frame, (x,y), (x+bw, y+bh), (255,230,180), -1)
            cv2.rectangle(frame, (x,y), (x+bw, y+bh), (200,160,80), 2)
            cv2.putText(frame, str(val), (x+20, y+65), self.FONT, 2, (30,30,30), 4)

    def draw_feedback(self, frame):
        if not self.result:
            return
        elapsed = time.time() - self.result_time
        if elapsed < 2:
            color = (0,200,0) if self.result == "Correct!" else (0,0,220)
            cv2.putText(frame, self.result, (200,440), self.FONT, 1.5, color, 4)
        elif self.result == "Correct!" and elapsed >= 2:
            play_sound("assets/sounds/well_done.mp3")
            self.running = False

    def draw_hold_ring(self, frame, cx, cy, progress):
        cv2.ellipse(frame, (cx,cy), (40,40), -90, 0, progress*360, (0,220,0), 5)

    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (self.W, self.H))
            landmarks = self.tracker.get_landmarks(frame)

            self.draw_content(frame)
            self.draw_options(frame)
            self.draw_back_button(frame)
            self.draw_feedback(frame)

            if landmarks:
                x1,y1 = landmarks[4]   # thumb tip
                x2,y2 = landmarks[8]   # index tip
                cx,cy = (x1+x2)//2, (y1+y2)//2
                dist = ((x1-x2)**2+(y1-y2)**2)**0.5

                hovering = self._get_hovered(cx, cy)

                if dist < self.PINCH_THRESHOLD and hovering is not None:
                    if self.hold_target != hovering:
                        self.hold_start = time.time()
                        self.hold_target = hovering
                    elapsed = time.time() - self.hold_start
                    progress = min(elapsed / self.HOLD_SECONDS, 1.0)
                    self.draw_hold_ring(frame, cx, cy, progress)
                    if progress >= 1.0:
                        self._handle_selection(hovering)
                        self.hold_start = None
                        self.hold_target = None
                else:
                    self.hold_start = None
                    self.hold_target = None

            self.tracker.draw_hand(frame)
            cv2.imshow(self.title, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        try:
            cv2.destroyWindow(self.title)
        except:
            pass

    def _get_hovered(self, cx, cy):
        bx,by,bw,bh = self.back_btn
        if bx < cx < bx+bw and by < cy < by+bh:
            return "__BACK__"
        for val,(x,y,bw,bh) in self.get_option_boxes():
            if x < cx < x+bw and y < cy < y+bh:
                return val
        return None

    def _handle_selection(self, value):
        if value == "__BACK__":
            play_sound("assets/sounds/welcome.mp3")
            self.running = False
        elif self.check_answer(value):
            self.on_correct()
        else:
            self.on_wrong()