import cv2
import random
import time
from modules.sound_player import play_sound

def run_odd_even(cap, tracker):
    h, w = 480, 640
    last_click = 0
    correct_time = None

    number = random.randint(1, 99)
    correct_answer = "Even" if number % 2 == 0 else "Odd"

    choices = ["Odd", "Even"]
    random.shuffle(choices)

    button_w, button_h = 180, 100
    button_y = h // 2
    spacing = 100
    buttons = []

    for i, label in enumerate(choices):
        x = spacing + i * (button_w + spacing)
        buttons.append((label, (x, button_y, button_w, button_h)))

    # BACK button
    back_button = (w - 140, 20, 120, 60)

    result = ""
    result_time = 0

    while True:
        success, frame = cap.read()
        if not success:
            break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (w, h))
        landmarks = tracker.get_landmarks(frame)

        # Title
        cv2.putText(frame, "Is this number Odd or Even?", (40, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3)

        # Number
        cv2.putText(frame, str(number), (w//2 - 40, 140),
                    cv2.FONT_HERSHEY_DUPLEX, 2.5, (0, 255, 255), 5)

        # Buttons
        for label, (bx, by, bw, bh) in buttons:
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (100, 255, 255), -1)
            cv2.putText(frame, label, (bx + 20, by + 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)

        # BACK button
        bx, by, bw, bh = back_button
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 255, 255), -1)
        cv2.putText(frame, "BACK", (bx + 10, by + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Feedback
        if result and time.time() - result_time < 2:
            color = (0, 255, 0) if result == "Correct!" else (0, 0, 255)
            cv2.putText(frame, result, (200, 420), cv2.FONT_HERSHEY_SIMPLEX, 1.8, color, 4)
        elif result == "Correct!" and time.time() - result_time >= 2:
            play_sound("assets/sounds/well_done.mp3")
            break
        else:
            result = ""

        if landmarks:
            x1, y1 = landmarks[4]    # Thumb
            x2, y2 = landmarks[8]    # Index
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2)**2 + (y1 - y2)**2)**0.5

            if dist < 40 and time.time() - last_click > 1:
                # Check BACK
                if bx < cx < bx + bw and by < cy < by + bh:
                    play_sound("assets/sounds/welcome.mp3")
                    break

                # Check answers
                for label, (bx, by, bw, bh) in buttons:
                    if bx < cx < bx + bw and by < cy < by + bh:
                        if label == correct_answer:
                            play_sound("assets/sounds/correct.mp3")
                            result = "Correct!"
                        else:
                            play_sound("assets/sounds/wrong.mp3")
                            result = "Wrong!"
                        result_time = time.time()
                        last_click = time.time()
                        break

        tracker.draw_hand(frame)
        cv2.imshow("Odd or Even", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Odd or Even")
    except:
        pass
