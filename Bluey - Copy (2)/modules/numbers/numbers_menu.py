import cv2
import time
from modules.menu import Menu
from modules.sound_player import play_sound

# Import submodules
from modules.numbers.addition import run_addition
from modules.numbers.subtraction import run_subtraction
from modules.numbers.multiplication import run_multiplication
from modules.numbers.division import run_division
from modules.numbers.tracing import run_tracing
from modules.numbers.odd_even import run_odd_even
from modules.numbers.fill_missing import run_fill_missing

def show_numbers_menu(cap, tracker):
    labels = [
        "Addition", "Subtraction", "Multiplication",
        "Division", "Tracing", "Odd/Even", "Fill Missing", "Back"
    ]

    success, frame = cap.read()
    if not success:
        return
    h, w = frame.shape[:2]
    menu = Menu(labels, w, h)

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        landmarks = tracker.get_landmarks(frame)
        menu.draw(frame)

        if landmarks and len(landmarks) >= 9:
            x1, y1 = landmarks[4]
            x2, y2 = landmarks[8]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((x1 - x2)**2 + (y1 - y2)**2)**0.5

            menu.update_hover(cx, cy)

            if dist < 40:
                selection = menu.update_selection_timer(cx, cy)
                if selection:
                    print(f"🔢 Subselected: {selection}")
                    play_sound("assets/sounds/welcome.mp3")
                    time.sleep(0.8)

                    if selection == "Addition":
                        run_addition(cap, tracker)
                    elif selection == "Subtraction":
                        run_subtraction(cap, tracker)
                    elif selection == "Multiplication":
                        run_multiplication(cap, tracker)
                    elif selection == "Division":
                        run_division(cap, tracker)
                    elif selection == "Tracing":
                        run_tracing(cap, tracker)
                    elif selection == "Odd/Even":
                        run_odd_even(cap, tracker)
                    elif selection == "Fill Missing":
                        run_fill_missing(cap, tracker)
                    elif selection == "Back":
                        break

                    time.sleep(0.8)

        tracker.draw_hand(frame)
        cv2.imshow("Numbers Menu", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    try:
        cv2.destroyWindow("Numbers Menu")
    except:
        pass
