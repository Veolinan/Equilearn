import cv2

def draw_back_button(frame):
    h, w, _ = frame.shape
    bw, bh = 150, 60
    bx, by = w - bw - 30, 30  # Top-right with padding

    # Draw filled white rounded button background (simulated)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 255, 255), -1)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 0, 0), 2)

    # Optional: Add shadow
    cv2.putText(frame, "← Back", (bx + 20, by + 40),
                cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 255), 2)

    return (bx, by, bw, bh)


def is_back_pressed(landmarks, back_button_coords):
    if not landmarks:
        return False
    x1, y1 = landmarks[4]   # Thumb
    x2, y2 = landmarks[8]   # Index
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

    bx, by, bw, bh = back_button_coords
    return dist < 40 and bx < cx < bx + bw and by < cy < by + bh
