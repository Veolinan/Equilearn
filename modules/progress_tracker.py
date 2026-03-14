# modules/progress_tracker.py
"""
Persists lesson results across sessions.
Lessons call tracker.record() after each question.
Progress screen reads the JSON file directly.

JSON structure
──────────────
{
  "_streak":     3,            // consecutive days played
  "_last_played": "2026-03-14",
  "A": {                       // letter
    "stage": 3,
    "history": [{"stage":1,"accuracy":0.92,"ts":1234567}]
  },
  "lesson_addition": {         // numeric lesson
    "correct_streak": 7,
    "total_attempts": 12,
    "total_correct":  9,
    "history": [{"correct":true,"ts":1234567}]
  }
}
"""
import json, os, time
from datetime import date

DATA_DIR  = "data"
DATA_PATH = os.path.join(DATA_DIR, "progress.json")


class ProgressTracker:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._data = {}
        self._load()
        self._update_streak()

    # ── I/O ───────────────────────────────────────────────────────────────
    def _load(self):
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH) as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        try:
            with open(DATA_PATH, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    # ── Streak ────────────────────────────────────────────────────────────
    def _update_streak(self):
        today      = str(date.today())
        last_played= self._data.get("_last_played", "")
        streak     = self._data.get("_streak", 0)

        if last_played == today:
            return   # already recorded today
        elif last_played == str(date.fromordinal(date.today().toordinal()-1)):
            streak += 1   # played yesterday → extend streak
        else:
            streak = 1    # gap → reset

        self._data["_streak"]      = streak
        self._data["_last_played"] = today
        self._save()

    # ── Letter progress ───────────────────────────────────────────────────
    def record_letter(self, letter: str, stage: int, accuracy: float):
        entry = self._data.setdefault(letter, {"stage": 1, "history": []})
        entry["history"].append({
            "stage":    stage,
            "accuracy": round(accuracy, 3),
            "ts":       time.time(),
        })
        self._save()

    def get_letter_stage(self, letter: str) -> int:
        return self._data.get(letter, {}).get("stage", 1)

    def set_letter_stage(self, letter: str, stage: int):
        self._data.setdefault(letter, {})["stage"] = stage
        self._save()

    # ── Lesson (arithmetic / shapes) progress ────────────────────────────
    def record_lesson(self, lesson_id: str, correct: bool):
        """
        Call after every question in a numeric or shapes lesson.
        lesson_id examples: "addition", "subtraction", "shapes", "colors"
        """
        key   = f"lesson_{lesson_id}"
        entry = self._data.setdefault(key, {
            "correct_streak": 0,
            "total_attempts": 0,
            "total_correct":  0,
            "history":        [],
        })
        entry["total_attempts"] += 1
        if correct:
            entry["total_correct"]  += 1
            entry["correct_streak"] += 1
        else:
            entry["correct_streak"]  = 0

        entry["history"].append({
            "correct": correct,
            "ts":      time.time(),
        })
        # Cap history at 200 entries to keep file small
        if len(entry["history"]) > 200:
            entry["history"] = entry["history"][-200:]

        self._save()

    def get_lesson_stats(self, lesson_id: str) -> dict:
        return self._data.get(f"lesson_{lesson_id}", {
            "correct_streak": 0,
            "total_attempts": 0,
            "total_correct":  0,
        })

    # ── Summary ───────────────────────────────────────────────────────────
    def summary(self) -> dict:
        """Return a flat summary for the progress screen."""
        return {
            "streak":    self._data.get("_streak", 0),
            "last_played": self._data.get("_last_played", ""),
        }
