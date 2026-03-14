import cv2
import os
import time
from modules.sound_player import play_sound

class Menu:
    def __init__(self, items, width, height):
        self.items = items
        self.buttons = []
        self.icons = {}
        self.hovered_index = -1
        self.last_hovered = -1
        self.width = width
        self.height = height
        self.hover_sounds_played = {}
        self.build_buttons(width, height)

    def build_buttons(self, width, height):
        spacing = height // (len(self.items) + 2)
        for i, label in enumerate(self.items):
            x = width // 6
            y = spacing * (i + 1)
            self.buttons.append({
                "label": label,
                "pos": (x, y),
                "hovered": False,
                "select_start_time": None
            })

            icon_path = f"assets/icons/{label.lower().replace('&', '').replace(' ', '')}.png"
            if os.path.exists(icon_path):
                self.icons[label] = cv2.resize(cv2.imread(icon_path, cv2.IMREAD_UNCHANGED), (50, 50))

    def draw(self, frame):
        for idx, btn in enumerate(self.buttons):
            x, y = btn["pos"]
            label = btn["label"]
            hovered = btn["hovered"]
            color = (0, 120, 255) if hovered else (0, 0, 200)

            cv2.rectangle(frame, (x, y), (x + 320, y + 70), color, -1)

            # Icon
            if label in self.icons:
                icon = self.icons[label]
                if icon.shape[2] == 4:
                    alpha_s = icon[:, :, 3] / 255.0
                    alpha_l = 1.0 - alpha_s
                    for c in range(3):
                        frame[y+10:y+60, x+10:x+60, c] = (
                            alpha_s * icon[:, :, c] + alpha_l * frame[y+10:y+60, x+10:x+60, c]
                        )
                else:
                    frame[y+10:y+60, x+10:x+60] = icon

            # Text
            cv2.putText(frame, label, (x + 70, y + 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Progress ring for selection
            if btn["select_start_time"]:
                duration = time.time() - btn["select_start_time"]
                if duration < 4:
                    progress = int((duration / 4) * 360)
                    center = (x + 160, y + 35)
                    cv2.ellipse(frame, center, (40, 40), 0, 0, progress, (0, 255, 0), 5)

    def update_hover(self, x, y):
        self.hovered_index = -1
        for i, btn in enumerate(self.buttons):
            bx, by = btn["pos"]
            in_button = bx < x < bx + 320 and by < y < by + 70
            btn["hovered"] = in_button

            if in_button:
                self.hovered_index = i
                label = btn["label"]

                # Play sound only once per hover
                if i != self.last_hovered:
                    self.last_hovered = i
                    sound_file = f"assets/sounds/{label.lower().replace('&', '').replace(' ', '')}.mp3"
                    if os.path.exists(sound_file):
                        play_sound(sound_file)
            else:
                btn["select_start_time"] = None

    def update_selection_timer(self, x, y):
        for btn in self.buttons:
            bx, by = btn["pos"]
            if bx < x < bx + 320 and by < y < by + 70:
                if btn["select_start_time"] is None:
                    btn["select_start_time"] = time.time()
                elif time.time() - btn["select_start_time"] >= 4:
                    return btn["label"]
            else:
                btn["select_start_time"] = None
        return None
