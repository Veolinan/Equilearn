import cv2
import random
import time
from modules.sound_player import play_sound

EMOJIS = ["🍎", "🐠", "🐶", "⭐", "🦋", "🎈", "🍓", "🧸"]

def run_division(cap, tracker):
    w, h = 640, 480
    font = cv2.FONT_HERSHEY_SIMPLEX
    emoji = random.choice(EMOJIS)

    # Generate divisible numbers
    divisor = random.randint(1, 5)
    quotient = random.randint(1, 5)
    dividend = divisor * quotient

    question_text = f"{dividend} {emoji}s ÷ {divisor} = ?"

    # Options (correct + 3 wrong)
    options = [quotient]
    while len(options) < 4:
        fake = random.randint(1, 9)
        if fake not in options:
            options.append(fake)
    random.shuffle(options)

    # Visual emoji layout
    emoji_positions = []
    for i in range(dividend):
        x = 60 + (i % 6) * 90
        y = 120 + (i // 6) * 90
        emoji_positions.append((x, y))

    # Layout option boxes
    option_boxes = []
    spacing = 120
    for i, val in enumerate(options):
        x = 70 + i * spacing
        y = h - 120
        option_boxes.append((val, (x, y, 100, 100)))

    # Back button
    back_btn = (w - 130, 20, 100, 60)

    result = ""
    result_time = 0
    hold_start = None
    hold_target = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (w, h))
        landmarks = tracker.get_landmarks(frame)

        # === UI Drawing ===
        cv2.putText(frame, question_text, (20, 60), font, 1.0, (255, 100, 50), 3)

        for x, y in emoji_positions:
            cv2.putText(frame, emoji, (x, y), font, 2.5, (0, 0, 0), 4)

        # Draw options
        for val, (x, y, bw, bh) in option_boxes:
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (255, 240, 200), -1)
            cv2.putText(frame, str(val), (x + 20, y + 65), font, 2, (0, 0, 0), 4)

        # BACK button
        bx, by, bw, bh = back_btn
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 255, 255), -1)
        cv2.putText(frame, "BACK", (bx + 10, by + 40), font, 1, (0, 0, 255), 2)

        # Feedback message
        if result and time.time() - result_time < 2:
            color = (0, 255, 0) if result == "Correct!" else (0, 0, 255)
            cv2.putText(frame, result, (220, 420), font, 1.5, color, 4)
        elif result == "Correct!" and time.time() - result_time >= 2:
            play_sound("assets/sounds/well_done.mp3")
            break

        # === Gesture detection ===
        if landmarks:
            x1, y1 = landmarks[4]
            x2, y2 = landmarks[8]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2)**2 + (y1 - y2)**2) ** 0.5

            hovering = None
            for val, (x, y, bw, bh) in option_boxes + [("BACK", back_btn)]:
                if x < cx < x + bw and y < cy < y + bh:
                    hovering = val
                    break

            if dist < 40 and hovering:
                if hold_target != hovering:
                    hold_start = time.time()
                    hold_target = hovering

                elapsed = time.time() - hold_start
                progress = min(elapsed / 4, 1)
                cv2.ellipse(frame, (cx, cy), (40, 40), -90, 0, progress * 360, (0, 255, 0), 5)

                if progress == 1:
                    if hovering == "BACK":
                        play_sound("assets/sounds/welcome.mp3")
                        return
                    elif isinstance(hovering, int):
                        if hovering == quotient:
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
        cv2.imshow("Division", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Division")
    except:
        pass
