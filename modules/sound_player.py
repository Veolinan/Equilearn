# modules/sound_player.py
"""
Sound module for Touchless Tutor.

Features
────────
  • Non-blocking playback via pygame.mixer (never freezes the UI)
  • Queue: new sounds interrupt only lower-priority sounds
  • Auto-generates missing MP3s with gTTS on first run
  • Voice helpers: play_letter("A"), play_number(3), play_shape("Circle")
  • Volume control: set_volume(0.0–1.0)
  • Graceful no-op if mixer unavailable (no audio hardware)

Priority levels (higher = more important)
────────────────────────────────────────
  0  background music  (loops, always pre-emptable)
  1  voice / narration (letter names, number names)
  2  feedback          (correct, wrong, well_done)
  3  celebration       (level_up, streak)
"""
from __future__ import annotations
import os, threading, queue, time
import pygame

# ── Config ────────────────────────────────────────────────────────────────────
SOUNDS_DIR  = "assets/sounds"
FONTS_DIR   = "assets/fonts"
MASTER_VOL  = 0.85     # 0.0 – 1.0
VOICE_LANG  = "en"     # gTTS language code
_ENABLED    = False    # set True after successful mixer init


# ── Mixer init ────────────────────────────────────────────────────────────────
def _init_mixer():
    global _ENABLED
    if _ENABLED:
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(8)
        _ENABLED = True
    except Exception as e:
        print(f"[Sound] Mixer init failed — audio disabled. ({e})")


_init_mixer()


# ── Sound cache ───────────────────────────────────────────────────────────────
_cache: dict[str, pygame.mixer.Sound] = {}
_cache_lock = threading.Lock()


def _load(path: str) -> pygame.mixer.Sound | None:
    if not _ENABLED or not os.path.exists(path):
        return None
    with _cache_lock:
        if path not in _cache:
            try:
                _cache[path] = pygame.mixer.Sound(path)
                _cache[path].set_volume(MASTER_VOL)
            except Exception as e:
                print(f"[Sound] Failed to load {path}: {e}")
                return None
        return _cache[path]


# ── Playback queue ─────────────────────────────────────────────────────────────
# We dedicate channel 0 to background music, channels 1-7 to effects/voice.
_BG_CHANNEL   = pygame.mixer.Channel(0) if _ENABLED else None
_SFX_CHANNEL  = pygame.mixer.Channel(1) if _ENABLED else None
_VOICE_CHANNEL= pygame.mixer.Channel(2) if _ENABLED else None

_current_priority = -1
_play_lock = threading.Lock()


def play_sound(path: str, priority: int = 2, loop: bool = False):
    """
    Play a sound file non-blocking.
    Higher priority pre-empts lower priority sounds.
    """
    if not _ENABLED:
        return

    def _play():
        global _current_priority
        snd = _load(path)
        if snd is None:
            return
        with _play_lock:
            if priority >= _current_priority:
                _current_priority = priority
                loops = -1 if loop else 0
                if priority == 0:
                    if _BG_CHANNEL:
                        _BG_CHANNEL.play(snd, loops=loops, fade_ms=500)
                elif priority <= 1:
                    if _VOICE_CHANNEL:
                        _VOICE_CHANNEL.play(snd, loops=loops)
                else:
                    if _SFX_CHANNEL:
                        _SFX_CHANNEL.stop()
                        _SFX_CHANNEL.play(snd, loops=loops)

                # Reset priority after sound ends
                duration = snd.get_length()
                def _reset():
                    time.sleep(duration + 0.05)
                    global _current_priority
                    with _play_lock:
                        if _current_priority == priority:
                            _current_priority = -1
                threading.Thread(target=_reset, daemon=True).start()

    threading.Thread(target=_play, daemon=True).start()


def stop_all():
    if _ENABLED:
        pygame.mixer.stop()


def set_volume(vol: float):
    """Set master volume 0.0 – 1.0."""
    global MASTER_VOL
    MASTER_VOL = max(0.0, min(1.0, vol))
    with _cache_lock:
        for snd in _cache.values():
            snd.set_volume(MASTER_VOL)


# ── Named sound shortcuts ─────────────────────────────────────────────────────
def play_correct():
    play_sound(f"{SOUNDS_DIR}/correct.mp3",  priority=2)

def play_wrong():
    play_sound(f"{SOUNDS_DIR}/wrong.mp3",    priority=2)

def play_well_done():
    play_sound(f"{SOUNDS_DIR}/well_done.mp3",priority=2)

def play_welcome():
    play_sound(f"{SOUNDS_DIR}/welcome.mp3",  priority=2)

def play_level_up():
    play_sound(f"{SOUNDS_DIR}/level_up.mp3", priority=3)

def play_letter(letter: str):
    """Say the letter name aloud, e.g. play_letter('A') → "A" """
    play_sound(f"{SOUNDS_DIR}/letter_{letter.lower()}.mp3", priority=1)

def play_number(n: int):
    """Say the number aloud, e.g. play_number(3) → "Three" """
    play_sound(f"{SOUNDS_DIR}/number_{n}.mp3", priority=1)

def play_shape(name: str):
    """Say the shape name aloud, e.g. play_shape('Circle') """
    play_sound(f"{SOUNDS_DIR}/shape_{name.lower()}.mp3", priority=1)

def play_color(name: str):
    """Say the color name aloud, e.g. play_color('Red') """
    play_sound(f"{SOUNDS_DIR}/color_{name.lower()}.mp3", priority=1)


# ── gTTS auto-generation ──────────────────────────────────────────────────────
def generate_missing_audio(verbose: bool = True):
    """
    Generate any missing MP3 files using gTTS (Google Text-to-Speech).
    Safe to call at startup — skips files that already exist.
    Requires:  py -m pip install gtts
    """
    try:
        from gtts import gTTS
    except ImportError:
        if verbose:
            print("[Sound] gTTS not installed — skipping audio generation.")
            print("        Run:  py -m pip install gtts")
        return

    os.makedirs(SOUNDS_DIR, exist_ok=True)

    # Build full generation manifest
    items: dict[str, str] = {}

    # Feedback phrases
    items.update({
        "correct":   "That's correct!",
        "wrong":     "Try again",
        "well_done": "Well done!",
        "welcome":   "Let's learn!",
        "level_up":  "Amazing, you levelled up!",
        "streak":    "Fantastic streak!",
    })

    # Letters A-Z
    import string
    for ch in string.ascii_uppercase:
        items[f"letter_{ch.lower()}"] = ch

    # Numbers 0-20
    words = [
        "Zero","One","Two","Three","Four","Five","Six","Seven","Eight","Nine",
        "Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen",
        "Seventeen","Eighteen","Nineteen","Twenty",
    ]
    for i, w in enumerate(words):
        items[f"number_{i}"] = w

    # Shapes
    for name in ["Circle","Square","Triangle","Rectangle",
                 "Pentagon","Hexagon","Star","Diamond"]:
        items[f"shape_{name.lower()}"] = name

    # Colors
    for name in ["Red","Blue","Green","Yellow","Purple","Orange","Pink","White"]:
        items[f"color_{name.lower()}"] = name

    # Generate only missing files
    generated = 0
    for filename, text in items.items():
        path = os.path.join(SOUNDS_DIR, f"{filename}.mp3")
        if os.path.exists(path):
            continue
        try:
            if verbose:
                print(f"  Generating {filename}.mp3 …")
            tts = gTTS(text=text, lang=VOICE_LANG, slow=False)
            tts.save(path)
            generated += 1
        except Exception as e:
            if verbose:
                print(f"  [!] Failed {filename}: {e}")

    if verbose:
        if generated:
            print(f"[Sound] Generated {generated} audio file(s) in {SOUNDS_DIR}/")
        else:
            print(f"[Sound] All audio files present in {SOUNDS_DIR}/")
