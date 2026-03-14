import cv2
import time
from modules.sound_player import play_sound
from modules.hand_tracker import HandTracker

# Submodule runners
from modules.numbers.addition import run_addition
from modules.numbers.subtraction import run_subtraction
from modules.numbers.multiplication import run_multiplication
from modules.numbers.division import run_division
from modules.numbers.counting import run_counting
from modules.numbers.tracing import run_tracing
from modules.numbers.odd_even import run_odd_even
from modules.numbers.fill_missing import run_fill_missing

def run_numbers(cap, tracker: HandTracker):
    labels = [
        "Addition", "Subtraction", "Multiplication", "Division",
        "Counting", "Tracing", "Odd/Even", "Fill Missing", "Back"
    ]

    h, w = 480, 640
    last_hovered = None
    hover_start_time = 0

    button_areas = []
    rows = 3
    cols = 3
    button_width = 180
    button_height = 80
    padding_x = (w - cols * button_width) // (cols + 1)
    padding_y = 40

    for i in range(len(labels)):
        col = i % cols
        row = i // cols
        x = padding_x + col * (button_width + padding_x)
        y = padding_y + row * (button_height + padding_y)
        button_areas.append((labels[i], (x, y, button_width, button_height)))

    while True:
        success, frame = cap.read()
        if not success:
            break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (w, h))

        landmarks = tracker.get_landmarks(frame)

        # Draw buttons
        for label, (x, y, bw, bh) in button_areas:
            color = (0, 150, 255)
            if last_hovered == label and time.time() - hover_start_time > 0.5:
                color = (0, 255, 0)  # Glow effect
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, -1)
            cv2.putText(frame, label, (x + 10, y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

        if landmarks:
            x1, y1 = landmarks[4]
            x2, y2 = landmarks[8]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2)**2 + (y1 - y2)**2)**0.5

            hovered = None
            for label, (x, y, bw, bh) in button_areas:
                if x < cx < x + bw and y < cy < y + bh:
                    hovered = label
                    if hovered != last_hovered:
                        hover_start_time = time.time()
                        play_sound(f"assets/sounds/{label.lower().replace('/', '').replace(' ', '')}.mp3")
                        last_hovered = hovered
                    break

            if hovered and dist < 40:
                held_duration = time.time() - hover_start_time
                cv2.ellipse(frame, (cx, cy), (30, 30), -90, 0, min(360, int(held_duration / 4 * 360)), (255, 255, 255), 5)

                if held_duration >= 4:
                    play_sound("assets/sounds/welcome.mp3")
                    if hovered == "Addition":
                        run_addition(cap, tracker)
                    elif hovered == "Subtraction":
                        run_subtraction(cap, tracker)
                    elif hovered == "Multiplication":
                        run_multiplication(cap, tracker)
                    elif hovered == "Division":
                        run_division(cap, tracker)
                    elif hovered == "Counting":
                        run_counting(cap, tracker)
                    elif hovered == "Tracing":
                        run_tracing(cap, tracker)
                    elif hovered == "Odd/Even":
                        run_odd_even(cap, tracker)
                    elif hovered == "Fill Missing":
                        run_fill_missing(cap, tracker)
                    elif hovered == "Back":
                        return
                    last_hovered = None
                    hover_start_time = 0
            else:
                hover_start_time = time.time()

        tracker.draw_hand(frame)
        cv2.imshow("Numbers Menu", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Numbers Menu")
    except:
        pass
