import cv2
import random
import time
from modules.sound_player import play_sound

def run_subtraction(cap, tracker):
    h, w = 480, 640
    last_click = 0
    result_message = ""
    result_time = 0

    # Generate subtraction question
    a = random.randint(5, 9)
    b = random.randint(1, a - 1)
    answer = a - b

    # Generate answer options
    options = [answer]
    while len(options) < 3:
        fake = random.randint(0, 9)
        if fake not in options:
            options.append(fake)
    random.shuffle(options)

    # Option button layout
    button_size = (100, 100)
    button_y = 320
    spacing = 100
    buttons = []
    for i, opt in enumerate(options):
        x = 70 + i * (button_size[0] + spacing)
        buttons.append((opt, (x, button_y, *button_size)))

    # Back button (top-right)
    back_button = (w - 140, 20, 120, 60)

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (w, h))
        landmarks = tracker.get_landmarks(frame)

        # --- UI Drawing ---

        # Instructions
        cv2.putText(frame, "Solve this:", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        # Subtraction problem
        cv2.putText(frame, f"{a} - {b} = ?", (w//2 - 100, 140), cv2.FONT_HERSHEY_DUPLEX, 2.2, (0, 255, 255), 5)

        # Emojis to show subtraction visually
        for i in range(a):
            emoji = "🍎" if i < (a - b) else "🍎"
            color = (0, 255, 0) if i < (a - b) else (0, 0, 255)
            cx = 50 + i * 50
            cv2.putText(frame, "🍎", (cx, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 4)

        # Answer options
        for opt, (bx, by, bw, bh) in buttons:
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 200, 0), -1)
            cv2.putText(frame, str(opt), (bx + 30, by + 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)

        # BACK button
        bx, by, bw, bh = back_button
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 255, 255), -1)
        cv2.putText(frame, "BACK", (bx + 10, by + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Result feedback
        if result_message and time.time() - result_time < 1.5:
            color = (0, 255, 0) if result_message == "Correct!" else (0, 0, 255)
            cv2.putText(frame, result_message, (180, 440),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.8, color, 4)
        elif result_message == "Correct!" and time.time() - result_time >= 2:
            play_sound("assets/sounds/well_done.mp3")
            break
        else:
            result_message = ""

        # === Gesture Detection ===
        if landmarks:
            x1, y1 = landmarks[4]  # Thumb
            x2, y2 = landmarks[8]  # Index
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

            if dist < 40 and time.time() - last_click > 1:
                # Check back
                if bx < cx < bx + bw and by < cy < by + bh:
                    play_sound("assets/sounds/welcome.mp3")
                    break

                # Check answer buttons
                for opt, (bx, by, bw, bh) in buttons:
                    if bx < cx < bx + bw and by < cy < by + bh:
                        if opt == answer:
                            result_message = "Correct!"
                            play_sound("assets/sounds/correct.mp3")
                        else:
                            result_message = "Wrong!"
                            play_sound("assets/sounds/wrong.mp3")
                        result_time = time.time()
                        last_click = time.time()
                        break

        tracker.draw_hand(frame)
        cv2.imshow("Subtraction", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Subtraction")
    except:
        pass
