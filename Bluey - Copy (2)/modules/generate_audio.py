# generate_audio.py  — run once from project root
from gtts import gTTS
import os

os.makedirs("assets/sounds", exist_ok=True)

items = {}

# Letters
for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    items[f"letter_{ch.lower()}"] = ch

# Numbers
words = ["Zero","One","Two","Three","Four","Five","Six","Seven","Eight","Nine"]
for i, w in enumerate(words):
    items[f"number_{i}"] = w

# Shapes
for name in ["Circle","Square","Triangle","Rectangle",
             "Pentagon","Hexagon","Star","Diamond"]:
    items[f"shape_{name.lower()}"] = name

# Colors
for name in ["Red","Blue","Green","Yellow","Purple","Orange","Pink","White"]:
    items[f"color_{name.lower()}"] = name

# Feedback phrases
phrases = {
    "well_done":  "Well done!",
    "correct":    "That's correct!",
    "wrong":      "Try again",
    "welcome":    "Let's learn",
    "level_up":   "Amazing, you levelled up!",
    "streak":     "Fantastic streak!",
}
items.update(phrases)

for filename, text in items.items():
    path = f"assets/sounds/{filename}.mp3"
    if not os.path.exists(path):
        print(f"Generating {path}...")
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(path)
        print(f"  ✓ saved")

print("Done! All audio files generated.")
