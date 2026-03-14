# modules/progress_tracker.py
"""
PT singleton — import everywhere, never instantiate directly.

Metrics tracked per question
────────────────────────────
  correct          bool
  response_time_s  float  — seconds from question shown to answer selected
  attempt_number   int    — 1 = first attempt at this question, 2 = retry
  ts               float  — unix timestamp

Metrics tracked per session
────────────────────────────
  date, ts, duration_min, lessons_played,
  questions, correct, accuracy, avg_response_s
"""
import json, os, time, string
from datetime import date

DATA_DIR  = "data"
DATA_PATH = os.path.join(DATA_DIR, "progress.json")
MASTERY_STREAK = 10


class ProgressTracker:

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._data: dict = {}
        self._load()
        self._update_streak()

    # ── I/O ───────────────────────────────────────────────────────────────
    def _load(self):
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                print(f"[Progress] Load error: {e}")
                self._data = {}

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = DATA_PATH + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, DATA_PATH)
        except Exception as e:
            print(f"[Progress] Save error: {e}")

    # ── streak ────────────────────────────────────────────────────────────
    def _update_streak(self):
        today = str(date.today())
        last  = self._data.get("_last_played", "")
        if last == today:
            return
        streak    = self._data.get("_streak", 0)
        yesterday = str(date.fromordinal(date.today().toordinal() - 1))
        self._data["_streak"]      = streak + 1 if last == yesterday else 1
        self._data["_last_played"] = today
        self._save()

    # ── lesson question recording ──────────────────────────────────────────
    def record_lesson(self, lesson_id: str, correct: bool,
                      response_time_s: float = 0.0,
                      attempt_number: int = 1):
        key   = f"lesson_{lesson_id}"
        entry = self._data.setdefault(key, {
            "best_streak": 0, "correct_streak": 0,
            "total_attempts": 0, "total_correct": 0,
            "sessions": 0, "history": [],
        })
        entry["total_attempts"] += 1
        if correct:
            entry["total_correct"]  += 1
            entry["correct_streak"] += 1
            if entry["correct_streak"] > entry.get("best_streak", 0):
                entry["best_streak"] = entry["correct_streak"]
                if entry["best_streak"] in (5, 10, 20):
                    self._data["_total_stars"] = \
                        self._data.get("_total_stars", 0) + 1
        else:
            entry["correct_streak"] = 0

        entry["history"].append({
            "correct":          correct,
            "response_time_s":  round(response_time_s, 2),
            "attempt_number":   attempt_number,
            "ts":               time.time(),
        })
        if len(entry["history"]) > 400:
            entry["history"] = entry["history"][-400:]
        self._save()

    def start_lesson(self, lesson_id: str):
        key = f"lesson_{lesson_id}"
        e   = self._data.setdefault(key, {
            "best_streak": 0, "correct_streak": 0,
            "total_attempts": 0, "total_correct": 0,
            "sessions": 0, "history": [],
        })
        e["sessions"] = e.get("sessions", 0) + 1
        self._save()

    def get_lesson(self, lesson_id: str) -> dict:
        return self._data.get(f"lesson_{lesson_id}", {
            "best_streak": 0, "correct_streak": 0,
            "total_attempts": 0, "total_correct": 0, "sessions": 0,
            "history": [],
        })

    def lesson_status(self, lesson_id: str) -> str:
        e = self.get_lesson(lesson_id)
        if e["total_attempts"] == 0:
            return "untouched"
        if e.get("best_streak", 0) >= MASTERY_STREAK:
            return "mastered"
        total = e["total_attempts"]
        if total >= 10 and e["total_correct"] / total >= 0.80:
            return "mastered"
        return "started"

    # ── letter recording ───────────────────────────────────────────────────
    def record_letter(self, letter: str, stage: int, accuracy: float):
        key = f"letter_{letter}"
        e   = self._data.setdefault(key, {"stage": 1, "attempts": 0, "history": []})
        e["attempts"] = e.get("attempts", 0) + 1
        e["history"].append({"stage": stage, "accuracy": round(accuracy, 3),
                              "ts": time.time()})
        if len(e["history"]) > 100:
            e["history"] = e["history"][-100:]
        self._save()

    def get_letter_stage(self, letter: str) -> int:
        return self._data.get(f"letter_{letter}", {}).get("stage", 1)

    def set_letter_stage(self, letter: str, stage: int):
        key = f"letter_{letter}"
        self._data.setdefault(key, {"stage": 1, "attempts": 0,
                                    "history": []})["stage"] = stage
        self._save()

    def letter_status(self, letter: str) -> str:
        e    = self._data.get(f"letter_{letter}", {})
        hist = e.get("history", [])
        if not hist:
            return "untouched"
        stage = e.get("stage", 1)
        if stage >= 5 and any(h.get("accuracy", 0) >= 0.80
                              for h in hist if h.get("stage", 0) >= 5):
            return "mastered"
        return "started"

    # ── session snapshots ──────────────────────────────────────────────────
    def record_session(self, lesson_ids: list[str],
                       duration_min: float = 0.0):
        """Call when leaving a lesson set. Aggregates the last hour."""
        today   = str(date.today())
        cutoff  = time.time() - 3600
        total_q = correct_q = 0
        resp_times = []

        for lid in lesson_ids:
            for h in self.get_lesson(lid).get("history", []):
                if h.get("ts", 0) > cutoff:
                    total_q += 1
                    if h.get("correct"):
                        correct_q += 1
                    rt = h.get("response_time_s", 0)
                    if rt > 0:
                        resp_times.append(rt)

        acc      = round(correct_q / max(total_q, 1), 3)
        avg_resp = round(sum(resp_times) / len(resp_times), 2) if resp_times else 0.0

        sessions = self._data.setdefault("_sessions", [])
        sessions.append({
            "date":           today,
            "ts":             time.time(),
            "lessons_played": lesson_ids,
            "questions":      total_q,
            "correct":        correct_q,
            "accuracy":       acc,
            "avg_response_s": avg_resp,
            "duration_min":   round(duration_min, 1),
        })
        if len(sessions) > 180:
            self._data["_sessions"] = sessions[-180:]
        self._save()

    def get_sessions(self, days: int = 28) -> list[dict]:
        cutoff = time.time() - days * 86400
        return sorted(
            [s for s in self._data.get("_sessions", [])
             if s.get("ts", 0) >= cutoff],
            key=lambda s: s.get("ts", 0))

    # ── analytics series ───────────────────────────────────────────────────
    def get_accuracy_series(self, lesson_id: str,
                             days: int = 28) -> list[tuple]:
        """Rolling 10-answer accuracy series → [(ts, acc)]"""
        cutoff  = time.time() - days * 86400
        hist    = [h for h in self.get_lesson(lesson_id).get("history", [])
                   if h.get("ts", 0) >= cutoff]
        hist.sort(key=lambda h: h["ts"])
        result  = []
        window  = 10
        for i in range(len(hist)):
            chunk = hist[max(0, i-window+1): i+1]
            acc   = sum(1 for h in chunk if h.get("correct")) / len(chunk)
            result.append((hist[i]["ts"], round(acc, 3)))
        return result

    def get_response_time_series(self, lesson_id: str,
                                  days: int = 28) -> list[tuple]:
        """Rolling 10-answer avg response time → [(ts, secs)]"""
        cutoff = time.time() - days * 86400
        hist   = [h for h in self.get_lesson(lesson_id).get("history", [])
                  if h.get("ts", 0) >= cutoff and h.get("response_time_s", 0) > 0]
        hist.sort(key=lambda h: h["ts"])
        result = []
        window = 10
        for i in range(len(hist)):
            chunk = hist[max(0, i-window+1): i+1]
            avg   = sum(h["response_time_s"] for h in chunk) / len(chunk)
            result.append((hist[i]["ts"], round(avg, 2)))
        return result

    def get_first_attempt_rate(self, lesson_id: str,
                                days: int = 28) -> float:
        """Fraction of questions answered correctly on the first attempt."""
        cutoff  = time.time() - days * 86400
        hist    = [h for h in self.get_lesson(lesson_id).get("history", [])
                   if h.get("ts", 0) >= cutoff]
        first   = [h for h in hist if h.get("attempt_number", 1) == 1]
        if not first:
            return 0.0
        return round(sum(1 for h in first if h.get("correct")) / len(first), 3)

    # ── full stats bundle ──────────────────────────────────────────────────
    def all_stats(self) -> dict:
        lessons = ["addition","subtraction","multiplication","division",
                   "counting","odd_even","fill_missing"]
        shapes  = ["shapes","colors"]
        return {
            "streak":        self._data.get("_streak", 0),
            "total_stars":   self._data.get("_total_stars", 0),
            "letters":       {l: self.letter_status(l)
                              for l in string.ascii_uppercase},
            "lessons":       {l: self.lesson_status(l) for l in lessons},
            "shapes":        {l: self.lesson_status(l) for l in shapes},
            "lesson_detail": {l: self.get_lesson(l) for l in lessons + shapes},
        }

    @property
    def streak(self) -> int:
        return self._data.get("_streak", 0)

    @property
    def total_stars(self) -> int:
        return self._data.get("_total_stars", 0)


PT = ProgressTracker()
