import cv2
import time
import random
from modules.sound_player import play_sound

def run_tracing(cap, tracker):
    h, w = 480, 640
    number = str(random.randint(0, 9))
    last_click = 0
    trail = []
    max_trail = 40
    show_check = False
    feedback_msg = ""
    feedback_time = 0

    # Back button
    back_button = (w - 140, 20, 120, 60)

    # Load number image (outline) — you can use white PNGs with black number outlines
    number_path = f"assets/numbers/{number}.png"
    number_img = cv2.imread(number_path, cv2.IMREAD_UNCHANGED)
    if number_img is not None:
        number_img = cv2.resize(number_img, (200, 300))

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (w, h))
        landmarks = tracker.get_landmarks(frame)

        # Draw tracing instructions
        cv2.putText(frame, f"Trace the number {number}!", (30, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 3)

        # Place the number outline
        if number_img is not None:
            x_offset, y_offset = w // 2 - 100, h // 2 - 150
            for c in range(3):
                mask = number_img[:, :, 3] > 0
                frame[y_offset:y_offset+number_img.shape[0],
                      x_offset:x_offset+number_img.shape[1], c][mask] = number_img[:, :, c][mask]

        # Show trail
        for i in range(1, len(trail)):
            cv2.line(frame, trail[i - 1], trail[i], (0, 255, 255), 6)

        # Show BACK button
        bx, by, bw, bh = back_button
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 255, 255), -1)
        cv2.putText(frame, "BACK", (bx + 10, by + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Show feedback message
        if feedback_msg and time.time() - feedback_time < 1.5:
            color = (0, 255, 0) if feedback_msg == "Well done!" else (0, 0, 255)
            cv2.putText(frame, feedback_msg, (180, 440),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 4)
        elif feedback_msg == "Well done!" and time.time() - feedback_time >= 2:
            break
        else:
            feedback_msg = ""

        # Detect hand
        if landmarks:
            x1, y1 = landmarks[8]  # Index tip
            trail.append((x1, y1))
            if len(trail) > max_trail:
                trail.pop(0)

            # Pinch to finish tracing
            thumb_x, thumb_y = landmarks[4]
            dist = ((x1 - thumb_x) ** 2 + (y1 - thumb_y) ** 2) ** 0.5
            if dist < 35 and time.time() - last_click > 1:
                # Check if enough tracing was done
                if len(trail) > 15:
                    play_sound("assets/sounds/well_done.mp3")
                    feedback_msg = "Well done!"
                    feedback_time = time.time()
                else:
                    play_sound("assets/sounds/wrong.mp3")
                    feedback_msg = "Try again!"
                    feedback_time = time.time()
                last_click = time.time()

            # Back button
            if bx < x1 < bx + bw and by < y1 < by + bh and dist < 35:
                play_sound("assets/sounds/welcome.mp3")
                break

        tracker.draw_hand(frame)
        cv2.imshow("Tracing", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Tracing")
    except:
        pass
