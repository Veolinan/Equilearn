# main.py
import sys, os, pygame, cv2, random, math, time
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modules.ui.layout import L
from modules.gesture_engine import GestureEngine, HoldDetector
from modules.progress_tracker import PT   # singleton — already initialised
from main_menu import run_main_menu

TITLE = "Touchless Tutor"
FPS   = 60


def _loading_screen(screen, message):
    screen.fill((15, 12, 30))
    try:
        from modules.ui.renderer import Fonts, Colors, draw_text_centered
        draw_text_centered(screen, message,
                           Fonts.body(L.font_size(36)), Colors.TEXT_MUTED,
                           (L.cx, L.cy))
    except Exception:
        f = pygame.font.Font(None, 40)
        s = f.render(message, True, (180, 175, 210))
        screen.blit(s, s.get_rect(center=(L.cx, L.cy)))
    pygame.display.flip()


def main():
    pygame.init()
    pygame.display.set_caption(TITLE)

    info   = pygame.display.Info()
    screen = pygame.display.set_mode((info.current_w, info.current_h),
                                     pygame.NOFRAME)
    L.init(screen)
    print(f"Display: {L}")

    _loading_screen(screen, "Starting camera…")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        _loading_screen(screen, "Camera not found.")
        pygame.time.wait(3000); pygame.quit(); sys.exit(1)

    _loading_screen(screen, "Loading hand tracker…")
    ge = GestureEngine(cap, screen_w=L.sw, screen_h=L.sh, mirror=True)

    # Start web dashboard (background thread — parents open http://localhost:5000)
    try:
        from dashboard.server import start_dashboard_server
        start_dashboard_server()
    except Exception as e:
        print(f"[Dashboard] Could not start: {e}")

    # Generate any missing audio files (gTTS, runs in background thread)
    _loading_screen(screen, "Preparing audio…")
    import threading
    def _gen_audio():
        from modules.sound_player import generate_missing_audio
        generate_missing_audio(verbose=True)
    threading.Thread(target=_gen_audio, daemon=True).start()

    _loading_screen(screen, "Ready!")
    pygame.time.wait(400)

    # ── Lazy module loaders ───────────────────────────────────────────────
    def numbers_menu():
        from lessons.numbers.menu import run_numbers_menu
        return run_numbers_menu

    def numbers_router():
        from lessons.numbers.addition import run_addition
        from lessons.numbers.lessons import (
            run_subtraction, run_multiplication, run_division,
            run_counting, run_odd_even, run_fill_missing,
        )
        return {
            "addition":       run_addition,
            "subtraction":    run_subtraction,
            "multiplication": run_multiplication,
            "division":       run_division,
            "counting":       run_counting,
            "odd_even":       run_odd_even,
            "fill_missing":   run_fill_missing,
        }

    _num_router = None
    scene = "menu"

    while True:
        if scene == "menu":
            scene = run_main_menu(screen, ge)

        elif scene == "numbers":
            _num_router = _num_router or numbers_router()
            run_num     = numbers_menu()
            while True:
                choice = run_num(screen, ge)
                if choice in ("back", None):
                    break
                runner = _num_router.get(choice)
                if runner:
                    runner(screen, ge)
            scene = "menu"

        elif scene == "shapes":
            from lessons.shapes_colors.lesson import run_shapes_colors
            run_shapes_colors(screen, ge)
            scene = "menu"

        elif scene == "letters":
            from lessons.letters.lesson import run_letters
            run_letters(screen, ge)
            scene = "menu"

        elif scene == "progress":
            from lessons.progress.screen import run_progress
            run_progress(screen, ge)
            scene = "menu"

        elif scene == "drawing":
            scene = "menu"   # placeholder

        elif scene == "quit" or scene is None:
            break

        else:
            scene = "menu"

    ge.stop()
    cap.release()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
