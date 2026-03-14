# modules/numbers/addition.py
import random
from modules.base_lesson import BaseLesson

class AdditionLesson(BaseLesson):
    def __init__(self, cap, tracker):
        super().__init__(cap, tracker, title="Addition")
        self.a = random.randint(1, 9)
        self.b = random.randint(1, 9)
        self.correct = self.a + self.b
        options = {self.correct}
        while len(options) < 4:
            options.add(random.randint(2, 18))
        opts = list(options)
        random.shuffle(opts)
        self._boxes = [
            (v, (80 + i*130, self.H//2, 110, 100))
            for i, v in enumerate(opts)
        ]

    def get_option_boxes(self): return self._boxes
    def check_answer(self, v): return v == self.correct
    def draw_content(self, frame):
        import cv2
        cv2.putText(frame, f"What is {self.a} + {self.b}?",
                    (30, 80), self.FONT, 1.5, (0,120,255), 4)

def run_addition(cap, tracker):
    AdditionLesson(cap, tracker).run()