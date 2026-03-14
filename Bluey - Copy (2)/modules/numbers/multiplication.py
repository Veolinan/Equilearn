import cv2
import random
import time
from modules.sound_player import play_sound

def run_multiplication(cap, tracker):
    w, h = 640, 480
    font = cv2.FONT_HERSHEY_SIMPLEX

    # Generate random multiplication question
    a = random.randint(2, 9)
    b = random.randint(2, 9)
    correct = a * b
    question_text = f"{a} x {b} = ?"

    # Generate answer choices
    options = [correct]
    while len(options) < 4:
        wrong = correct + random.choice([-4, -2, -1, 1, 2, 3, 5])
        if wrong not in options and wrong > 0:
            options.append(wrong)
    random.shuffle(options)

    # Position option buttons
    spacing = 130
    option_boxes = []
    for i, val in enumerate(options):
        x = 60 + i * spacing
        y = h // 2 + 30
        option_boxes.append((val, (x, y, 100, 100)))

    # Back button
    back_btn = (w - 140, 20, 110, 60)

    result = ""
    result_time = 0
    hold_start = None
    hold_target = None

    while True:
        success, frame = cap.read()
        if not success:
            break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (w, h))
        landmarks = tracker.get_landmarks(frame)

        # === Draw UI ===
        cv2.putText(frame, "Pick the correct answer:", (30, 60), font, 1, (50, 100, 255), 3)
        cv2.putText(frame, question_text, (200, 120), font, 1.6, (0, 0, 0), 4)

        # Draw option buttons
        for val, (x, y, bw, bh) in option_boxes:
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (250, 250, 200), -1)
            cv2.putText(frame, str(val), (x + 20, y + 65), font, 2, (0, 0, 0), 4)

        # Draw BACK button
        bx, by, bw, bh = back_btn
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 255, 255), -1)
        cv2.putText(frame, "BACK", (bx + 10, by + 40), font, 1, (0, 0, 255), 2)

        # Feedback message
        if result and time.time() - result_time < 1.5:
            color = (0, 255, 0) if result == "Correct!" else (0, 0, 255)
            cv2.putText(frame, result, (230, 420), font, 1.5, color, 4)
        elif result == "Correct!" and time.time() - result_time >= 2:
            play_sound("assets/sounds/well_done.mp3")
            break

        # === Gesture Detection ===
        if landmarks:
            x1, y1 = landmarks[4]
            x2, y2 = landmarks[8]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

            hovering = None
            for val, (x, y, bw, bh) in option_boxes + [("BACK", back_btn)]:
                if x < cx < x + bw and y < cy < y + bh:
                    hovering = val
                    break

            if dist < 40 and hovering:
                if hold_target != hovering:
                    hold_start = time.time()
                    hold_target = hovering

                progress = min((time.time() - hold_start) / 4, 1)
                cv2.ellipse(frame, (cx, cy), (40, 40), -90, 0, progress * 360, (0, 255, 0), 5)

                if progress == 1:
                    if hovering == "BACK":
                        play_sound("assets/sounds/welcome.mp3")
                        return
                    elif isinstance(hovering, int):
                        if hovering == correct:
                            play_sound("assets/sounds/correct.mp3")
                            result = "Correct!"
                        else:
                            play_sound("assets/sounds/wrong.mp3")
                            result = "Wrong!"
                        result_time = time.time()
                        hold_start = None
                        hold_target = None
            else:
                hold_start = None
                hold_target = None

        tracker.draw_hand(frame)
        cv2.imshow("Multiplication", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Multiplication")
    except:
        pass
