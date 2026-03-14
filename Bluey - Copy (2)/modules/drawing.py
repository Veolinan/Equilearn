import cv2
import numpy as np
import time
from modules.sound_player import play_sound

def run_drawing(cap, tracker):
    canvas = None
    prev_point = None
    last_click = 0
    back_button = (30, 30, 100, 60)

    while True:
        success, frame = cap.read()
        if not success:
            print("Failed to grab frame")
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        if canvas is None:
            canvas = np.zeros_like(frame)

        landmarks = tracker.get_landmarks(frame)

        # Draw back button
        x, y, bw, bh = back_button
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 0, 0), 2)
        cv2.putText(frame, "BACK", (x + 10, y + 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

        if landmarks and len(landmarks) >= 9:
            x1, y1 = landmarks[4]   # Thumb tip
            x2, y2 = landmarks[8]   # Index tip
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2)**2 + (y1 - y2)**2) ** 0.5

            # Back button pinch detection
            if dist < 40 and x < cx < x + bw and y < cy < y + bh:
                if time.time() - last_click > 1:
                    play_sound("assets/sounds/welcome.mp3")
                    break
                last_click = time.time()

            # Drawing
            if dist < 40:
                if prev_point:
                    cv2.line(canvas, prev_point, (x2, y2), (255, 0, 255), 5)
                prev_point = (x2, y2)
            else:
                prev_point = None

        # Draw instructions
        cv2.putText(frame, "Draw with Index & Thumb - Pinch BACK to return", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)

        # Combine canvas with live frame
        combined = cv2.addWeighted(frame, 0.5, canvas, 0.5, 0)

        tracker.draw_hand(combined)

        cv2.imshow("Drawing", combined)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyWindow("Drawing")
