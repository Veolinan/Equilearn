import cv2
import random
import numpy as np
import time
from modules.sound_player import play_sound

# Define shape types and colors
shapes = [("Square", (0, 0, 255)), ("Circle", (0, 255, 0)), ("Triangle", (255, 0, 0))]

def draw_shape(frame, shape, color, pos, size=80, deform=False):
    x, y = pos
    if shape == "Square":
        if deform:
            # Draw a rectangle with unequal sides
            cv2.rectangle(frame, (x, y), (x + size, y + int(size * 0.7)), color, -1)
        else:
            cv2.rectangle(frame, (x, y), (x + size, y + size), color, -1)
    elif shape == "Circle":
        radius = size // 2
        if deform:
            axes = (radius, int(radius * 0.6))
            cv2.ellipse(frame, (x + radius, y + radius), axes, 0, 0, 360, color, -1)
        else:
            cv2.circle(frame, (x + radius, y + radius), radius, color, -1)
    elif shape == "Triangle":
        pts = np.array([[x + size // 2, y], [x, y + size], [x + size, y + size]], np.int32)
        if deform:
            pts = np.array([[x + size // 2, y + 10], [x + 10, y + size], [x + size - 10, y + size]], np.int32)
        cv2.drawContours(frame, [pts], 0, color, -1)

def run_shapes_colors(cap, tracker):
    # Get frame dimensions
    success, frame = cap.read()
    if not success:
        print("❌ Failed to read from camera.")
        return
    h, w, _ = frame.shape

    last_click = 0
    last_shuffle_time = 0
    feedback_time = 0
    feedback_text = ""
    feedback_color = (0, 255, 0)

    back_button = (w - 150, 30, 110, 60)  # Top-right corner

    def generate_scene():
        # Select target
        target_shape, target_color = random.choice(shapes)
        correct = ((target_shape, target_color), False)  # False: no deform
        distractors = []

        while len(distractors) < 3:
            shape, color = random.choice(shapes)
            deform = random.choice([True, False])
            if (shape != target_shape or color != target_color) or deform:
                distractors.append(((shape, color), deform))

        items = [correct] + distractors
        random.shuffle(items)

        positions = []
        spacing = w // (len(items) + 1)
        y_pos = h // 2
        for i, ((shape, color), deform) in enumerate(items):
            x_pos = spacing * (i + 1) - 40
            positions.append(((shape, color), (x_pos, y_pos), deform))
        return (target_shape, target_color), positions

    # First scene
    target, placed_shapes = generate_scene()

    while True:
        success, frame = cap.read()
        if not success:
            print("❌ Frame capture failed.")
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (w, h))
        landmarks = tracker.get_landmarks(frame)

        # Reshuffle every 5s if no correct answer
        if time.time() - last_shuffle_time > 5 and feedback_text == "":
            target, placed_shapes = generate_scene()
            last_shuffle_time = time.time()

        # Display instruction
        target_name = f"{['Red','Green','Blue'][[s[1] for s in shapes].index(target[1])]} {target[0]}"
        cv2.putText(frame, f"Point to the {target_name}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

        # Draw shapes
        shape_boxes = []
        for (shape, color), (x, y), deform in placed_shapes:
            draw_shape(frame, shape, color, (x, y), size=80, deform=deform)
            shape_boxes.append(((shape, color), (x, y, 80, 80), deform))

        # Draw BACK button (top right)
        bx, by, bw, bh = back_button
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 255, 255), -1)
        cv2.putText(frame, "BACK", (bx + 10, by + 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Feedback
        if feedback_text and time.time() - feedback_time < 1.5:
            cv2.putText(frame, feedback_text, (w // 2 - 100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.4, feedback_color, 3)
        elif feedback_text:
            feedback_text = ""

        # Gesture detection
        if landmarks:
            x1, y1 = landmarks[4]  # Thumb
            x2, y2 = landmarks[8]  # Index
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

            if dist < 40 and time.time() - last_click > 1:
                # Check BACK
                if bx < cx < bx + bw and by < cy < by + bh:
                    play_sound("assets/sounds/welcome.mp3")
                    break

                # Check selection
                for (shape, color), (sx, sy, sw, sh), deform in shape_boxes:
                    if sx < cx < sx + sw and sy < cy < sy + sh:
                        if (shape, color) == target and not deform:
                            play_sound("assets/sounds/well_done.mp3")
                            feedback_text = "Well Done!"
                            feedback_color = (0, 200, 0)
                            feedback_time = time.time()
                            target, placed_shapes = generate_scene()
                            last_shuffle_time = time.time()
                        else:
                            play_sound("assets/sounds/wrong.mp3")
                            feedback_text = "Wrong!"
                            feedback_color = (0, 0, 255)
                            feedback_time = time.time()
                        last_click = time.time()
                        break

        tracker.draw_hand(frame)
        cv2.imshow("Shapes & Colors", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break

    try:
        cv2.destroyWindow("Shapes & Colors")
    except:
        pass
