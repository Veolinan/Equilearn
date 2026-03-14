import cv2
import random
import time
from modules.sound_player import play_sound, speak_word  # speak_word uses gTTS

words = [
    "apple", "planet", "forest", "grapes", "clouds", "school", "window", "garden",
    "rocket", "yellow", "market", "dragon", "violin", "basket", "castle", "pencil",
    "bridge", "friend", "circle", "family", "monkey", "zebra", "orange", "future",
    "hunter", "guitar", "turtle", "singer", "dancer", "candle", "wallet", "parrot",
    "bottle", "helmet", "bucket", "tablet", "silver", "nature", "letter", "ticket",
    "random", "cactus", "butter", "island", "ribbon", "trains", "bubble", "pirate",
    "planetary", "structure", "elephant", "sunrise", "mountain", "activity"
]

def run_spellings(cap, tracker):
    h, w = 480, 640
    score = 0
    lives = 3
    last_click = 0

    def new_word():
        word = random.choice(words).upper()
        shuffled = list(word)
        random.shuffle(shuffled)
        boxes = []
        spacing = min(80, max(50, int((w - 160) / len(shuffled))))
        for i, letter in enumerate(shuffled):
            x = 80 + i * spacing
            y = h // 2
            boxes.append((letter, (x, y, 80, 80)))
        return word, shuffled, boxes

    word, shuffled_letters, letter_boxes = new_word()
    selected_indices = set()
    selected_letters = []
    back_button = (w - 130, 30, 100, 60)
    wrong_message = ""
    wrong_time = 0
    current_index = 0

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (w, h))
        landmarks = tracker.get_landmarks(frame)

        # UI Headers
        cv2.putText(frame, f"Score: {score}  Lives: {lives}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (50, 50, 255), 2)
        cv2.putText(frame, f"Spell: {word}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 100, 0), 2)
        if current_index < len(word):
            cv2.putText(frame, f"Select: {word[current_index]}", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 100, 0), 2)

        # User guidance
        cv2.putText(frame, "👉 Pinch to select a letter", (20, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (90, 90, 90), 2)

        # BACK button
        bx, by, bw, bh = back_button
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 0, 0), 2)
        cv2.putText(frame, "BACK", (bx + 10, by + 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

        # Draw letter boxes
        for i, (letter, (x, y, bw, bh)) in enumerate(letter_boxes):
            if i in selected_indices:
                color = (100, 255, 100)
            else:
                color = (220, 220, 220)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, -1)
            cv2.putText(frame, letter, (x + 15, y + 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)

        # Display current progress
        cv2.putText(frame, "Selected: " + ''.join(selected_letters), (20, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 50, 200), 2)
        if wrong_message and time.time() - wrong_time < 1.5:
            cv2.putText(frame, wrong_message, (180, 430), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        else:
            wrong_message = ""

        # Game over logic
        if lives <= 0:
            cv2.putText(frame, "Game Over!", (180, 280), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
            play_sound("assets/sounds/wrong.mp3")
            cv2.imshow("Spellings", frame)
            cv2.waitKey(2500)
            break

        # Gesture detection
        if landmarks:
            x1, y1 = landmarks[4]
            x2, y2 = landmarks[8]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2)**2 + (y1 - y2)**2)**0.5

            if dist < 40 and time.time() - last_click > 1.8:
                # Check back button
                if bx < cx < bx + bw and by < cy < by + bh:
                    play_sound("assets/sounds/welcome.mp3")
                    break

                # Check letter boxes
                for i, (letter, (lx, ly, lw, lh)) in enumerate(letter_boxes):
                    if i not in selected_indices and lx < cx < lx + lw and ly < cy < ly + lh:
                        if letter == word[current_index]:
                            play_sound("assets/sounds/correct.mp3")
                            selected_letters.append(letter)
                            selected_indices.add(i)
                            current_index += 1
                        else:
                            play_sound("assets/sounds/wrong.mp3")
                            wrong_message = "Wrong! Try Again"
                            wrong_time = time.time()
                            lives -= 1
                        last_click = time.time()
                        break

                # Word complete
                if ''.join(selected_letters) == word:
                    play_sound("assets/sounds/well_done.mp3")
                    speak_word(word.lower())  # Say the word
                    cv2.putText(frame, "🎉 Well Done!", (150, 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)
                    cv2.imshow("Spellings", frame)
                    cv2.waitKey(1800)
                    word, shuffled_letters, letter_boxes = new_word()
                    selected_letters = []
                    selected_indices = set()
                    current_index = 0
                    last_click = time.time()

        tracker.draw_hand(frame)
        cv2.imshow("Spellings", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyWindow("Spellings")
