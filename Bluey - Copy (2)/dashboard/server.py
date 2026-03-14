# dashboard/server.py
"""
Touchless Tutor — Local Web Dashboard
Sections: Parent | Teacher | Technical
Run via:  py main.py  → visit http://localhost:5000
"""
import json, os, sys, time, threading, string, csv, io, platform
from datetime import date, timedelta, datetime
from flask import (Flask, jsonify, render_template, request,
                   redirect, url_for, send_file, abort)

# ── paths ─────────────────────────────────────────────────────────────────────
_HERE            = os.path.dirname(os.path.abspath(__file__))
_ROOT            = os.path.dirname(_HERE)
DATA_PATH        = os.path.join(_ROOT, "data", "progress.json")
CUSTOM_PATH      = os.path.join(_ROOT, "data", "custom_exercises.json")
PROFILE_PATH     = os.path.join(_ROOT, "data", "profile.json")
CURRICULUM_PATH  = os.path.join(_ROOT, "data", "curriculum.json")
CUSTOM_LESSONS_PATH = os.path.join(_ROOT, "data", "custom_lessons.json")
PORT             = 5000

# ── constants ──────────────────────────────────────────────────────────────────
LESSONS = ["addition","subtraction","multiplication","division",
           "counting","odd_even","fill_missing","shapes","colors"]
SHORT   = {
    "addition":"Addition","subtraction":"Subtraction",
    "multiplication":"Multiplication","division":"Division",
    "counting":"Counting","odd_even":"Odd / Even",
    "fill_missing":"Fill Missing","shapes":"Shapes","colors":"Colors",
}
LESSON_GROUPS = {
    "Numbers": ["addition","subtraction","multiplication","division",
                "counting","odd_even","fill_missing"],
    "Shapes & Colors": ["shapes","colors"],
}

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__,
            root_path=_ROOT,
            template_folder=os.path.join(_HERE, "templates"),
            static_folder=os.path.join(_HERE, "static"))

# ── data I/O ───────────────────────────────────────────────────────────────────
def _load() -> dict:
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Dashboard] Load error: {e}")
    return {}

def _save(data: dict):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DATA_PATH)

def _load_custom() -> dict:
    if os.path.exists(CUSTOM_PATH):
        try:
            with open(CUSTOM_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_custom(data: dict):
    os.makedirs(os.path.dirname(CUSTOM_PATH), exist_ok=True)
    with open(CUSTOM_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ── data helpers ───────────────────────────────────────────────────────────────
def _lesson_status(e: dict) -> str:
    att  = e.get("total_attempts", 0)
    cor  = e.get("total_correct", 0)
    best = e.get("best_streak", 0)
    if att == 0: return "untouched"
    if best >= 10 or (att >= 10 and cor / att >= 0.80): return "mastered"
    return "started"

def _letter_status(e: dict) -> str:
    hist  = e.get("history", [])
    stage = e.get("stage", 1)
    if not hist: return "untouched"
    if stage >= 5 and any(h.get("accuracy",0) >= 0.80
                          for h in hist if h.get("stage",0) >= 5):
        return "mastered"
    return "started"

def _rolling(history, window, key, transform=None):
    """Generic rolling-window series → [{x, y}]"""
    hist = [h for h in history if h.get(key) is not None]
    result = []
    for i in range(len(hist)):
        chunk = hist[max(0, i-window+1): i+1]
        vals  = [h[key] for h in chunk if h.get(key) is not None]
        if not vals: continue
        val = sum(vals) / len(vals)
        if transform: val = transform(val)
        ts  = hist[i].get("ts", 0)
        result.append({
            "x": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
            "y": round(val, 2),
        })
    return result

def _rolling_acc(history, window=10):
    hist = list(history)
    result = []
    for i in range(len(hist)):
        chunk = hist[max(0, i-window+1): i+1]
        acc   = sum(1 for h in chunk if h.get("correct")) / len(chunk) * 100
        ts    = hist[i].get("ts", 0)
        result.append({"x": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
                        "y": round(acc, 1)})
    return result

def _rolling_rt(history, window=10):
    hist = [h for h in history if h.get("response_time_s", 0) > 0]
    result = []
    for i in range(len(hist)):
        chunk = hist[max(0, i-window+1): i+1]
        avg   = sum(h["response_time_s"] for h in chunk) / len(chunk)
        ts    = hist[i].get("ts", 0)
        result.append({"x": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
                        "y": round(avg, 2)})
    return result

def _heatmap_cells(sessions, days=28):
    activity = {}
    for s in sessions:
        d = s.get("date","")
        activity[d] = activity.get(d, 0) + s.get("questions", 0)
    today = date.today()
    return [{"date": str(today-timedelta(days=days-1-i)),
             "questions": activity.get(str(today-timedelta(days=days-1-i)),0)}
            for i in range(days)]

def _lesson_bundle(lid: str, e: dict) -> dict:
    """Full metrics bundle for one lesson."""
    att  = e.get("total_attempts", 0)
    cor  = e.get("total_correct", 0)
    hist = e.get("history", [])
    rts  = [h["response_time_s"] for h in hist if h.get("response_time_s",0) > 0]
    fa   = [h for h in hist if h.get("attempt_number",1) == 1]
    # Improvement rate: compare first 20% vs last 20% accuracy
    if len(hist) >= 10:
        q = max(1, len(hist)//5)
        old_acc = sum(1 for h in hist[:q] if h.get("correct")) / q
        new_acc = sum(1 for h in hist[-q:] if h.get("correct")) / q
        improvement = round((new_acc - old_acc) * 100, 1)
    else:
        improvement = 0
    return {
        "id":           lid,
        "name":         SHORT.get(lid, lid),
        "status":       _lesson_status(e),
        "attempts":     att,
        "correct":      cor,
        "accuracy_pct": round(cor / max(att,1) * 100, 1),
        "best_streak":  e.get("best_streak", 0),
        "cur_streak":   e.get("correct_streak", 0),
        "avg_rt":       round(sum(rts)/len(rts), 1) if rts else 0,
        "fa_rate_pct":  round(sum(1 for h in fa if h.get("correct"))/len(fa)*100) if fa else 0,
        "improvement":  improvement,
        "sessions":     e.get("sessions", 0),
    }

def _summary_data(days=30) -> dict:
    """Full summary bundle used by multiple API endpoints."""
    data     = _load()
    cutoff   = time.time() - days * 86400
    sessions = sorted([s for s in data.get("_sessions",[])
                        if s.get("ts",0) >= cutoff],
                       key=lambda s: -s.get("ts",0))

    lessons_out = [_lesson_bundle(lid, data.get(f"lesson_{lid}",{}))
                   for lid in LESSONS]

    letters_out = {}
    for lt in string.ascii_uppercase:
        e = data.get(f"letter_{lt}", {})
        letters_out[lt] = {
            "status": _letter_status(e),
            "stage":  e.get("stage", 0),
            "attempts": e.get("attempts", 0),
        }

    total_q = sum(l["attempts"] for l in lessons_out)
    total_c = sum(l["correct"]  for l in lessons_out)
    all_rts = [l["avg_rt"] for l in lessons_out if l["avg_rt"] > 0]
    fa_rates= [l["fa_rate_pct"] for l in lessons_out if l["fa_rate_pct"] > 0]
    days_act= len({s["date"] for s in sessions})
    n_master= sum(1 for l in lessons_out if l["status"]=="mastered")
    n_letter_master = sum(1 for v in letters_out.values() if v["status"]=="mastered")

    # Best and most-improved lesson
    best_imp = max(lessons_out, key=lambda l: l["improvement"], default=None)
    struggling = [l for l in lessons_out if l["accuracy_pct"] < 60 and l["attempts"] > 5]

    return {
        "streak":          data.get("_streak", 0),
        "total_stars":     data.get("_total_stars", 0),
        "overall_acc":     round(total_c / max(total_q,1) * 100, 1),
        "total_questions": total_q,
        "days_active":     days_act,
        "mastered_lessons":n_master,
        "total_lessons":   len(LESSONS),
        "mastered_letters":n_letter_master,
        "avg_rt":          round(sum(all_rts)/len(all_rts),1) if all_rts else 0,
        "avg_fa_rate":     round(sum(fa_rates)/len(fa_rates)) if fa_rates else 0,
        "lessons":         lessons_out,
        "letters":         letters_out,
        "sessions":        sessions,
        "heatmap":         _heatmap_cells(sessions, 28),
        "best_improved":   best_imp["name"] if best_imp and best_imp["improvement"] > 5 else None,
        "struggling":      [l["name"] for l in struggling],
        "last_played":     data.get("_last_played","—"),
    }

# ══ PAGE ROUTES ════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html", show_nav=False)

@app.route("/parent")
def parent():
    return render_template("parent.html", show_nav=True, active="parent")

@app.route("/teacher")
def teacher():
    return render_template("teacher.html", show_nav=True, active="teacher")

# ── Technical — password protected ────────────────────────────────────────────
TECH_SESSION_KEY = "tech_auth"

def _tech_password() -> str:
    """Returns configured PIN, default '1234'. Store in profile.json."""
    return _load_profile().get("tech_password", "1234")

def _tech_authenticated() -> bool:
    from flask import session
    return session.get(TECH_SESSION_KEY) == True

@app.route("/technical")
def technical():
    if not _tech_authenticated():
        return render_template("tech_login.html", show_nav=False,
                               error=None)
    return render_template("technical.html", show_nav=True, active="technical")

@app.route("/technical/login", methods=["POST"])
def technical_login():
    from flask import session
    pin = request.form.get("pin","").strip()
    if pin == _tech_password():
        session[TECH_SESSION_KEY] = True
        session.permanent = False
        return redirect("/technical")
    return render_template("tech_login.html", show_nav=False,
                           error="Incorrect PIN. Try again.")

@app.route("/technical/logout", methods=["POST"])
def technical_logout():
    from flask import session
    session.pop(TECH_SESSION_KEY, None)
    return redirect("/")

@app.route("/api/technical/set-password", methods=["POST"])
def api_set_tech_password():
    from flask import session
    if not _tech_authenticated():
        abort(403)
    body        = request.get_json(force=True)
    current_pin = str(body.get("current_pin","")).strip()
    new_pin     = str(body.get("pin","")).strip()
    if current_pin != _tech_password():
        return jsonify({"error": "Current PIN is incorrect"}), 400
    if not new_pin.isdigit() or not 4 <= len(new_pin) <= 8:
        return jsonify({"error": "New PIN must be 4–8 digits"}), 400
    p = _load_profile()
    p["tech_password"] = new_pin
    _save_profile(p)
    return jsonify({"ok": True})

# Give Flask a secret key for sessions (generated once per process)
import secrets as _secrets
app.secret_key = _secrets.token_hex(32)

# ── Model & AI info API ────────────────────────────────────────────────────────
MODEL_PATH_GAME = os.path.join(_ROOT, "hand_landmarker.task")

@app.route("/api/model-info")
def api_model_info():
    """MediaPipe model details and training information."""
    model_exists = os.path.exists(MODEL_PATH_GAME)
    model_size   = (round(os.path.getsize(MODEL_PATH_GAME)/1024/1024, 2)
                    if model_exists else 0)

    return jsonify({
        "model": {
            "name":        "MediaPipe Hand Landmarker",
            "variant":     "float16 (quantised)",
            "version":     "1.0",
            "file":        "hand_landmarker.task",
            "file_exists": model_exists,
            "size_mb":     model_size,
            "source":      "Google MediaPipe Model Zoo",
            "url":         "https://storage.googleapis.com/mediapipe-models/hand_landmarker/",
            "license":     "Apache 2.0",
            "runtime":     "TensorFlow Lite (XNNPACK delegate)",
            "format":      "TFLite Task bundle (.task)",
        },
        "architecture": {
            "type":          "Two-stage CNN pipeline",
            "stage_1":       "Palm detector — SSD MobileNet, detects bounding boxes",
            "stage_2":       "Hand landmark model — regression CNN, 21 keypoints",
            "output":        "21 3D landmarks (x, y, z) normalised to image size",
            "inference_mode":"VIDEO (temporal tracking — lower CPU, fewer dropouts)",
        },
        "training_data": {
            "dataset":       "Proprietary Google dataset + augmentation",
            "hand_images":   "~30,000 real hand images",
            "annotations":   "21 keypoints per hand, manually annotated",
            "augmentation":  "Rotation, scale, occlusion, lighting variation",
            "demographics":  "Multi-ethnic, multi-age, multiple viewpoints",
            "backgrounds":   "Indoor, outdoor, cluttered and clean backgrounds",
            "note":          "Full dataset not publicly released; model weights are open-source under Apache 2.0",
        },
        "performance": {
            "latency_cpu_ms":   "~10–20ms per frame on modern CPU",
            "accuracy_mp":      "Mean Per-Joint Position Error < 5mm on benchmark",
            "landmarks":        21,
            "hands_supported":  2,
            "confidence_threshold": 0.5,
            "tracking_threshold":   0.4,
        },
        "game_config": {
            "pinch_threshold":  0.28,
            "smoothing_open":   0.18,
            "smoothing_pinch":  0.10,
            "ghost_seconds":    0.18,
            "safe_zone_margin": 0.15,
            "target_fps":       30,
            "gestures":         ["POINTING","PINCHING","OPEN_PALM","FIST",
                                 "THUMBS_UP","FINGERS_N","IDLE"],
        },
    })

@app.route("/api/operational")
def api_operational():
    """Operational metrics derived from collected session data."""
    data     = _load()
    sessions = data.get("_sessions", [])

    # Response time distribution across all lessons
    all_rt = []
    for lid in LESSONS:
        hist = data.get(f"lesson_{lid}",{}).get("history",[])
        all_rt += [h["response_time_s"] for h in hist
                   if h.get("response_time_s",0) > 0]

    all_rt.sort()
    rt_median = all_rt[len(all_rt)//2]          if all_rt else 0
    rt_p25    = all_rt[len(all_rt)//4]          if all_rt else 0
    rt_p75    = all_rt[int(len(all_rt)*0.75)]   if all_rt else 0
    rt_p90    = all_rt[int(len(all_rt)*0.90)]   if all_rt else 0

    # First-attempt vs retry breakdown
    first_att  = sum(1 for lid in LESSONS
                     for h in data.get(f"lesson_{lid}",{}).get("history",[])
                     if h.get("attempt_number",1)==1)
    retry_att  = sum(1 for lid in LESSONS
                     for h in data.get(f"lesson_{lid}",{}).get("history",[])
                     if h.get("attempt_number",1)>1)

    # Session duration stats
    durations = [s["duration_min"] for s in sessions if s.get("duration_min",0)>0]
    avg_dur   = round(sum(durations)/len(durations),1) if durations else 0

    # Accuracy over time — last 30 sessions
    recent = sorted(sessions, key=lambda s: s.get("ts",0))[-30:]
    acc_series = [{"date":s["date"],"accuracy":round(s.get("accuracy",0)*100,1)}
                  for s in recent]

    # Questions per session over time
    q_series = [{"date":s["date"],"questions":s.get("questions",0)}
                for s in recent]

    # Daily distribution
    from collections import Counter
    weekday_counts = Counter()
    for s in sessions:
        try:
            wd = datetime.fromtimestamp(s["ts"]).strftime("%a")
            weekday_counts[wd] += s.get("questions",0)
        except Exception:
            pass
    weekdays = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    daily_dist = [{"day":d,"questions":weekday_counts.get(d,0)} for d in weekdays]

    return jsonify({
        "response_time": {
            "total_answers": len(all_rt),
            "median_s":      round(rt_median, 2),
            "p25_s":         round(rt_p25, 2),
            "p75_s":         round(rt_p75, 2),
            "p90_s":         round(rt_p90, 2),
            "mean_s":        round(sum(all_rt)/len(all_rt),2) if all_rt else 0,
        },
        "attempts": {
            "first_attempt": first_att,
            "retry":         retry_att,
            "total":         first_att + retry_att,
            "retry_rate_pct":round(retry_att/max(first_att+retry_att,1)*100,1),
        },
        "sessions": {
            "total":       len(sessions),
            "avg_duration_min": avg_dur,
            "total_questions":  sum(s.get("questions",0) for s in sessions),
            "acc_series":       acc_series,
            "q_series":         q_series,
            "daily_distribution": daily_dist,
        },
    })

# ══ SHARED API ═════════════════════════════════════════════════════════════════

@app.route("/api/summary")
def api_summary():
    days = int(request.args.get("days", 30))
    return jsonify(_summary_data(days))

@app.route("/api/lesson/<lesson_id>/charts")
def api_lesson_charts(lesson_id):
    if lesson_id not in LESSONS:
        abort(404)
    data  = _load()
    hist  = data.get(f"lesson_{lesson_id}", {}).get("history", [])
    hist.sort(key=lambda h: h.get("ts", 0))
    cutoff= time.time() - 28 * 86400
    recent= [h for h in hist if h.get("ts",0) >= cutoff]
    return jsonify({
        "accuracy_series": _rolling_acc(recent),
        "rt_series":       _rolling_rt(recent),
    })

@app.route("/api/milestones")
def api_milestones():
    """Return list of milestone events from history."""
    data = _load()
    events = []

    # First time each lesson was played
    for lid in LESSONS:
        hist = data.get(f"lesson_{lid}",{}).get("history",[])
        if hist:
            first = min(hist, key=lambda h: h.get("ts",0))
            events.append({
                "type": "first_lesson", "ts": first["ts"],
                "label": f"First played {SHORT.get(lid,lid)}",
                "icon": "🎮",
            })

    # Best streak milestones
    for lid in LESSONS:
        e = data.get(f"lesson_{lid}",{})
        bs = e.get("best_streak",0)
        if bs >= 5:
            icon = "🌟" if bs >= 10 else "⭐"
            events.append({
                "type": "streak", "ts": time.time(),
                "label": f"{SHORT.get(lid,lid)} — best streak of {bs}",
                "icon": icon,
            })

    # Letter mastery
    mastered_letters = [lt for lt in string.ascii_uppercase
                        if _letter_status(data.get(f"letter_{lt}",{})) == "mastered"]
    if mastered_letters:
        events.append({
            "type": "letters", "ts": time.time(),
            "label": f"Mastered letters: {', '.join(mastered_letters)}",
            "icon": "🔤",
        })

    # Streak
    streak = data.get("_streak", 0)
    if streak >= 3:
        events.append({
            "type": "streak_days", "ts": time.time(),
            "label": f"{streak}-day learning streak! 🔥",
            "icon": "🔥",
        })

    events.sort(key=lambda e: -e["ts"])
    return jsonify(events[:20])

# ══ PARENT API ═════════════════════════════════════════════════════════════════

def _load_profile() -> dict:
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"name": "", "age": "", "goals": {}, "notifications": {}}

def _save_profile(p: dict):
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2)

@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    return jsonify(_load_profile())

@app.route("/api/profile", methods=["POST"])
def api_save_profile():
    body = request.get_json(force=True)
    p    = _load_profile()
    for k in ("name", "age", "goals", "notifications"):
        if k in body:
            p[k] = body[k]
    _save_profile(p)
    return jsonify({"ok": True, "profile": p})

@app.route("/api/weekly-narrative")
def api_weekly_narrative():
    """Plain-English summary paragraph for parents."""
    data    = _load()
    profile = _load_profile()
    name    = profile.get("name") or "Your child"

    cutoff7  = time.time() - 7  * 86400
    cutoff14 = time.time() - 14 * 86400

    sessions7 = [s for s in data.get("_sessions", []) if s.get("ts",0) >= cutoff7]
    sessions14= [s for s in data.get("_sessions", []) if s.get("ts",0) >= cutoff7
                 and s.get("ts",0) < cutoff7 + 7*86400]

    total_q   = sum(s.get("questions",0) for s in sessions7)
    total_c   = sum(s.get("correct",0)   for s in sessions7)
    days_active = len({s["date"] for s in sessions7})
    acc_pct   = round(total_c / max(total_q, 1) * 100)
    avg_dur   = round(sum(s.get("duration_min",0) for s in sessions7)
                      / max(len(sessions7), 1), 1)

    # Week-over-week accuracy change
    prev_q = sum(s.get("questions",0) for s in sessions14)
    prev_c = sum(s.get("correct",0)   for s in sessions14)
    prev_acc = round(prev_c / max(prev_q, 1) * 100)
    acc_delta = acc_pct - prev_acc

    # Best and worst lessons this week
    lesson_accs = {}
    for lid in LESSONS:
        hist = [h for h in data.get(f"lesson_{lid}",{}).get("history",[])
                if h.get("ts",0) >= cutoff7]
        if hist:
            lesson_accs[lid] = round(sum(1 for h in hist if h.get("correct"))
                                     / len(hist) * 100)

    best_l  = max(lesson_accs, key=lesson_accs.get) if lesson_accs else None
    worst_l = min(lesson_accs, key=lesson_accs.get) if lesson_accs else None

    # Mastered letters this week
    new_master = []
    for lt in string.ascii_uppercase:
        e    = data.get(f"letter_{lt}", {})
        hist = [h for h in e.get("history",[]) if h.get("ts",0) >= cutoff7]
        if hist and _letter_status(e) == "mastered":
            new_master.append(lt)

    # Build narrative
    streak = data.get("_streak", 0)
    parts  = []

    if days_active == 0:
        return jsonify({"narrative": f"{name} hasn't played this week yet. "
                        "Try a short 10-minute session today!"})

    # Opening
    if days_active == 1:
        parts.append(f"{name} played 1 session this week")
    else:
        parts.append(f"{name} played {days_active} sessions this week")

    if total_q > 0:
        parts[-1] += f", answering {total_q} questions at {acc_pct}% accuracy"

    # Trend
    if acc_delta > 5:
        parts.append(f"That's up {acc_delta}% from last week — great progress!")
    elif acc_delta < -5:
        parts.append(f"Accuracy dipped {abs(acc_delta)}% from last week — "
                     "a bit more practice will turn that around.")
    elif prev_q > 0:
        parts.append("Accuracy is holding steady compared to last week.")

    # Best lesson
    if best_l and lesson_accs[best_l] >= 70:
        parts.append(f"{SHORT.get(best_l, best_l)} is going well "
                     f"({lesson_accs[best_l]}% this week).")

    # Struggling lesson
    if worst_l and lesson_accs[worst_l] < 60 and worst_l != best_l:
        parts.append(f"{SHORT.get(worst_l, worst_l)} needs more attention "
                     f"({lesson_accs[worst_l]}% — try 5 minutes daily).")

    # Letters
    if new_master:
        lts = ", ".join(new_master[:3])
        parts.append(f"New letter milestone: {lts} mastered this week! 🎉")

    # Streak
    if streak >= 3:
        parts.append(f"Keep the {streak}-day streak going — consistency builds confidence.")

    narrative = " ".join(parts)
    return jsonify({
        "narrative":    narrative,
        "days_active":  days_active,
        "total_q":      total_q,
        "acc_pct":      acc_pct,
        "acc_delta":    acc_delta,
        "avg_dur":      avg_dur,
        "best_lesson":  SHORT.get(best_l,"—") if best_l else "—",
        "worst_lesson": SHORT.get(worst_l,"—") if worst_l else "—",
        "new_letters":  new_master,
    })

@app.route("/api/time-of-day")
def api_time_of_day():
    """Accuracy and count by hour of day (0-23)."""
    data    = _load()
    cutoff  = time.time() - 28 * 86400
    buckets = {h: {"questions":0,"correct":0} for h in range(24)}

    for lid in LESSONS:
        for h in data.get(f"lesson_{lid}",{}).get("history",[]):
            if h.get("ts",0) < cutoff: continue
            hour = datetime.fromtimestamp(h["ts"]).hour
            buckets[hour]["questions"] += 1
            if h.get("correct"): buckets[hour]["correct"] += 1

    result = []
    for hour in range(24):
        b   = buckets[hour]
        acc = round(b["correct"] / b["questions"] * 100, 1) if b["questions"] else None
        result.append({"hour": hour, "questions": b["questions"], "accuracy": acc})
    return jsonify(result)

@app.route("/api/fatigue")
def api_fatigue():
    """Per-session first-half vs second-half response time (fatigue indicator)."""
    data    = _load()
    cutoff  = time.time() - 28 * 86400
    sessions= [s for s in data.get("_sessions",[]) if s.get("ts",0) >= cutoff]

    results = []
    for s in sorted(sessions, key=lambda x: x["ts"]):
        # Gather all history entries within that session's day ±2 hours
        sess_ts = s.get("ts", 0)
        window  = 3600 * 2
        all_hist = []
        for lid in (s.get("lessons_played") or LESSONS):
            for h in data.get(f"lesson_{lid}",{}).get("history",[]):
                if abs(h.get("ts",0) - sess_ts) < window and h.get("response_time_s",0) > 0:
                    all_hist.append(h)
        all_hist.sort(key=lambda h: h["ts"])
        if len(all_hist) < 6: continue
        mid    = len(all_hist) // 2
        first  = sum(h["response_time_s"] for h in all_hist[:mid]) / mid
        second = sum(h["response_time_s"] for h in all_hist[mid:]) / (len(all_hist)-mid)
        results.append({
            "date":      s["date"],
            "first_rt":  round(first, 2),
            "second_rt": round(second, 2),
            "delta":     round(second - first, 2),
        })
    return jsonify(results)

@app.route("/api/goals", methods=["GET"])
def api_get_goals():
    return jsonify(_load_profile().get("goals", {}))

@app.route("/api/goals", methods=["POST"])
def api_save_goals():
    body  = request.get_json(force=True)
    p     = _load_profile()
    p.setdefault("goals", {}).update(body)
    _save_profile(p)
    return jsonify({"ok": True, "goals": p["goals"]})

@app.route("/api/notifications", methods=["GET"])
def api_get_notifications():
    return jsonify(_load_profile().get("notifications", {}))

@app.route("/api/notifications", methods=["POST"])
def api_save_notifications():
    body = request.get_json(force=True)
    p    = _load_profile()
    p.setdefault("notifications", {}).update(body)
    _save_profile(p)
    return jsonify({"ok": True})

HOME_TIPS = {
    "addition":       "Try counting steps on a walk, or adding up fruit at breakfast.",
    "subtraction":    "Split snacks into groups and take some away — ask how many are left.",
    "multiplication": "Count items arranged in rows (e.g. tiles, books on a shelf).",
    "division":       "Share snacks equally between family members at meal times.",
    "counting":       "Count objects during daily routines — buttons, steps, spoons.",
    "odd_even":       "Sort socks into odd-one-out vs matching pairs after laundry.",
    "fill_missing":   "Sing number songs with a deliberate pause for the child to fill in.",
    "shapes":         "Spot shapes on walks — circles on wheels, rectangles in windows.",
    "colors":         "Name colours during meals, dressing, or sorting toys by colour.",
}

@app.route("/api/home-tips")
def api_home_tips():
    data       = _load()
    struggling = [lid for lid in LESSONS
                  if _lesson_bundle(lid, data.get(f"lesson_{lid}",{}))["accuracy_pct"] < 65
                  and data.get(f"lesson_{lid}",{}).get("total_attempts",0) > 5]
    tips = [{"lesson": SHORT.get(l,l), "tip": HOME_TIPS.get(l,"")}
            for l in struggling if l in HOME_TIPS]
    # Always include at least one tip if none flagged
    if not tips:
        for l in LESSONS:
            tips.append({"lesson": SHORT.get(l,l), "tip": HOME_TIPS[l]})
            if len(tips) >= 2: break
    return jsonify(tips)

# ══ TEACHER API ════════════════════════════════════════════════════════════════

@app.route("/api/custom-exercises", methods=["GET"])
def api_get_exercises():
    return jsonify(_load_custom())

@app.route("/api/custom-exercises", methods=["POST"])
def api_add_exercise():
    body = request.get_json(force=True)
    required = ["lesson_id", "question", "options", "correct", "difficulty"]
    for field in required:
        if field not in body:
            return jsonify({"error": f"Missing field: {field}"}), 400
    if body["lesson_id"] not in LESSONS:
        return jsonify({"error": "Unknown lesson_id"}), 400
    if body["correct"] not in body["options"]:
        return jsonify({"error": "correct must be one of options"}), 400
    if len(body["options"]) < 2 or len(body["options"]) > 4:
        return jsonify({"error": "options must have 2–4 items"}), 400

    custom = _load_custom()
    lid    = body["lesson_id"]
    custom.setdefault(lid, [])
    exercise = {
        "id":         f"{lid}_{int(time.time())}",
        "question":   body["question"],
        "options":    body["options"],
        "correct":    body["correct"],
        "difficulty": body["difficulty"],
        "created":    str(date.today()),
        "note":       body.get("note",""),
    }
    custom[lid].append(exercise)
    _save_custom(custom)
    return jsonify({"ok": True, "exercise": exercise})

@app.route("/api/custom-exercises/<ex_id>", methods=["DELETE"])
def api_delete_exercise(ex_id):
    custom = _load_custom()
    for lid in custom:
        custom[lid] = [e for e in custom[lid] if e.get("id") != ex_id]
    _save_custom(custom)
    return jsonify({"ok": True})

@app.route("/api/export/csv")
def api_export_csv():
    data  = _load()
    rows  = []
    for lid in LESSONS:
        hist = data.get(f"lesson_{lid}",{}).get("history",[])
        for h in hist:
            rows.append({
                "lesson":          SHORT.get(lid, lid),
                "date":            datetime.fromtimestamp(h.get("ts",0)).strftime("%Y-%m-%d"),
                "time":            datetime.fromtimestamp(h.get("ts",0)).strftime("%H:%M:%S"),
                "correct":         "Yes" if h.get("correct") else "No",
                "response_time_s": h.get("response_time_s",""),
                "attempt_number":  h.get("attempt_number",1),
            })
    rows.sort(key=lambda r: r["date"] + r["time"])
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    output.seek(0)
    buf = io.BytesIO(output.getvalue().encode())
    return send_file(buf, mimetype="text/csv",
                     download_name=f"touchless_tutor_{date.today()}.csv",
                     as_attachment=True)

# ══ TEACHER API (additional) ═══════════════════════════════════════════════════

def _load_custom_lessons() -> dict:
    if os.path.exists(CUSTOM_LESSONS_PATH):
        try:
            with open(CUSTOM_LESSONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_custom_lessons(data: dict):
    os.makedirs(os.path.dirname(CUSTOM_LESSONS_PATH), exist_ok=True)
    with open(CUSTOM_LESSONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

@app.route("/api/custom-lessons", methods=["GET"])
def api_get_custom_lessons():
    return jsonify(_load_custom_lessons())

@app.route("/api/custom-lessons", methods=["POST"])
def api_create_custom_lesson():
    body = request.get_json(force=True)
    for field in ("id", "name", "emoji", "category", "color"):
        if not body.get(field):
            return jsonify({"error": f"Missing field: {field}"}), 400

    lid = body["id"].strip().replace(" ", "_").lower()
    if not lid.replace("_","").isalnum():
        return jsonify({"error": "ID must be alphanumeric (underscores OK)"}), 400

    lessons = _load_custom_lessons()
    if lid in lessons:
        return jsonify({"error": f"Lesson '{lid}' already exists"}), 400

    lessons[lid] = {
        "id":          lid,
        "name":        body["name"],
        "emoji":       body.get("emoji", "❓"),
        "category":    body.get("category", "other"),
        "color":       body.get("color", "purple"),
        "description": body.get("description", ""),
        "active":      False,
        "created":     str(date.today()),
        "questions":   [],
    }
    _save_custom_lessons(lessons)
    return jsonify({"ok": True, "lesson": lessons[lid]})

@app.route("/api/custom-lessons/<lesson_id>", methods=["DELETE"])
def api_delete_custom_lesson(lesson_id):
    lessons = _load_custom_lessons()
    lessons.pop(lesson_id, None)
    _save_custom_lessons(lessons)
    return jsonify({"ok": True})

@app.route("/api/custom-lessons/<lesson_id>/questions", methods=["POST"])
def api_add_lesson_question(lesson_id):
    lessons = _load_custom_lessons()
    if lesson_id not in lessons:
        return jsonify({"error": "Lesson not found"}), 404
    body = request.get_json(force=True)
    for field in ("question", "options", "correct"):
        if not body.get(field):
            return jsonify({"error": f"Missing: {field}"}), 400
    if body["correct"] not in body["options"]:
        return jsonify({"error": "correct must be one of options"}), 400
    if not 2 <= len(body["options"]) <= 4:
        return jsonify({"error": "Need 2–4 options"}), 400

    q = {
        "id":         f"q_{int(time.time()*1000)}",
        "question":   body["question"],
        "options":    body["options"],
        "correct":    body["correct"],
        "difficulty": body.get("difficulty", "medium"),
        "hint":       body.get("hint", ""),
    }
    lessons[lesson_id]["questions"].append(q)
    _save_custom_lessons(lessons)
    return jsonify({"ok": True, "question": q})

@app.route("/api/custom-lessons/<lesson_id>/questions/<q_id>", methods=["DELETE"])
def api_delete_lesson_question(lesson_id, q_id):
    lessons = _load_custom_lessons()
    if lesson_id not in lessons:
        abort(404)
    lessons[lesson_id]["questions"] = [
        q for q in lessons[lesson_id]["questions"] if q["id"] != q_id
    ]
    _save_custom_lessons(lessons)
    return jsonify({"ok": True})

@app.route("/api/custom-lessons/<lesson_id>/activate", methods=["POST"])
def api_activate_lesson(lesson_id):
    lessons = _load_custom_lessons()
    if lesson_id not in lessons:
        abort(404)
    if len(lessons[lesson_id]["questions"]) < 4:
        return jsonify({"error": "Need at least 4 questions to activate"}), 400
    lessons[lesson_id]["active"] = True
    _save_custom_lessons(lessons)
    return jsonify({"ok": True})

@app.route("/api/custom-lessons/<lesson_id>/deactivate", methods=["POST"])
def api_deactivate_lesson(lesson_id):
    lessons = _load_custom_lessons()
    if lesson_id not in lessons:
        abort(404)
    lessons[lesson_id]["active"] = False
    _save_custom_lessons(lessons)
    return jsonify({"ok": True})

@app.route("/api/custom-lessons/import-questions", methods=["POST"])
def api_import_questions():
    """Copy template questions from built-in lesson into a custom lesson."""
    body      = request.get_json(force=True)
    target_id = body.get("target_lesson_id")
    source_id = body.get("source_lesson_id")
    count     = body.get("count", 4)

    lessons = _load_custom_lessons()
    if target_id not in lessons:
        return jsonify({"error": "Target lesson not found"}), 404

    # Generate template questions based on source lesson type
    templates = _generate_template_questions(source_id, count)
    for q in templates:
        q["id"] = f"q_{int(time.time()*1000)}_{templates.index(q)}"
        lessons[target_id]["questions"].append(q)

    _save_custom_lessons(lessons)
    return jsonify({"ok": True, "imported": len(templates),
                    "questions": lessons[target_id]["questions"]})

def _generate_template_questions(lesson_id: str, count) -> list:
    """Generate sample questions for a given lesson type as import templates."""
    import random as _r
    templates = []
    count_n   = 999 if count == "all" else int(count)

    if lesson_id == "addition":
        for _ in range(min(count_n, 12)):
            a, b    = _r.randint(1,9), _r.randint(1,9)
            correct = str(a+b)
            opts    = {correct}
            while len(opts) < 4:
                opts.add(str(_r.randint(1,18)))
            templates.append({"question":f"{a} + {b} = ?",
                               "options":list(opts),"correct":correct,"difficulty":"medium","hint":""})

    elif lesson_id == "subtraction":
        for _ in range(min(count_n, 12)):
            a, b    = _r.randint(3,12), _r.randint(1,5)
            correct = str(a-b)
            opts    = {correct}
            while len(opts) < 4:
                opts.add(str(max(0,a-b+_r.randint(-3,3))))
            templates.append({"question":f"{a} − {b} = ?",
                               "options":list(opts),"correct":correct,"difficulty":"medium","hint":""})

    elif lesson_id == "multiplication":
        for _ in range(min(count_n, 12)):
            a, b    = _r.randint(2,9), _r.randint(2,9)
            correct = str(a*b)
            opts    = {correct}
            while len(opts) < 4:
                opts.add(str(_r.randint(4,81)))
            templates.append({"question":f"{a} × {b} = ?",
                               "options":list(opts),"correct":correct,"difficulty":"medium","hint":""})

    elif lesson_id == "counting":
        for n in range(1, min(count_n+1, 13)):
            correct = str(n)
            opts    = {correct}
            while len(opts) < 4:
                opts.add(str(max(1, n+_r.randint(-2,2))))
            templates.append({"question":f"Count: {'⭐'*n}  How many stars?",
                               "options":list(opts),"correct":correct,"difficulty":"easy","hint":""})

    elif lesson_id == "shapes":
        shapes = ["Circle","Square","Triangle","Rectangle","Star"]
        for s in shapes[:min(count_n,5)]:
            others = [x for x in shapes if x!=s][:3]
            opts   = [s]+others
            _r.shuffle(opts)
            templates.append({"question":f"What shape is this? (A {s.lower()})",
                               "options":opts,"correct":s,"difficulty":"easy","hint":""})

    elif lesson_id == "colors":
        colors = ["Red","Blue","Green","Yellow","Orange","Purple"]
        for col in colors[:min(count_n,6)]:
            others = [x for x in colors if x!=col][:3]
            opts   = [col]+others
            _r.shuffle(opts)
            templates.append({"question":f"What color is this?",
                               "options":opts,"correct":col,"difficulty":"easy","hint":""})

    else:
        # Generic template
        for i in range(min(count_n, 4)):
            templates.append({
                "question": f"Question {i+1} — edit me",
                "options":  ["Answer A","Answer B","Answer C","Answer D"],
                "correct":  "Answer A",
                "difficulty":"medium","hint":""
            })

    return templates

# ══ TEACHER API (additional) ends ═════════════════════════════════════════════

def _load_curriculum() -> dict:
    if os.path.exists(CURRICULUM_PATH):
        try:
            with open(CURRICULUM_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"targets": {}, "focus": [], "notes": {}}

def _save_curriculum(c: dict):
    os.makedirs(os.path.dirname(CURRICULUM_PATH), exist_ok=True)
    with open(CURRICULUM_PATH, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2)

@app.route("/api/curriculum", methods=["GET"])
def api_get_curriculum():
    return jsonify(_load_curriculum())

@app.route("/api/curriculum", methods=["POST"])
def api_save_curriculum():
    body = request.get_json(force=True)
    cur  = _load_curriculum()
    for k in ("targets", "focus", "notes"):
        if k in body:
            cur[k] = body[k]
    _save_curriculum(cur)
    return jsonify({"ok": True, "curriculum": cur})

@app.route("/api/teacher/performance")
def api_teacher_performance():
    """Detailed per-lesson performance table for teacher view."""
    data = _load()
    cur  = _load_curriculum()
    rows = []
    for lid in LESSONS:
        e    = data.get(f"lesson_{lid}", {})
        b    = _lesson_bundle(lid, e)
        hist = e.get("history", [])

        # Week-over-week change
        cutoff7  = time.time() - 7  * 86400
        cutoff14 = time.time() - 14 * 86400
        hist7    = [h for h in hist if h.get("ts",0) >= cutoff7]
        hist14   = [h for h in hist if cutoff14 <= h.get("ts",0) < cutoff7]
        acc7     = (sum(1 for h in hist7  if h.get("correct")) / len(hist7)  * 100) if hist7  else None
        acc14    = (sum(1 for h in hist14 if h.get("correct")) / len(hist14) * 100) if hist14 else None
        wow      = round(acc7 - acc14, 1) if (acc7 is not None and acc14 is not None) else None

        # Error pattern: which question types are failing (attempt_number > 1)
        retries    = [h for h in hist if h.get("attempt_number",1) > 1]
        retry_rate = round(len(retries) / max(len(hist),1) * 100, 1)

        # Response time trend (improving / worsening)
        rts = [h["response_time_s"] for h in hist[-20:] if h.get("response_time_s",0) > 0]
        if len(rts) >= 6:
            first_avg = sum(rts[:len(rts)//2]) / (len(rts)//2)
            last_avg  = sum(rts[len(rts)//2:]) / (len(rts) - len(rts)//2)
            rt_trend  = round(last_avg - first_avg, 2)
        else:
            rt_trend  = None

        target = cur["targets"].get(lid)
        on_focus = lid in cur.get("focus", [])

        rows.append({
            **b,
            "wow":        wow,
            "retry_rate": retry_rate,
            "rt_trend":   rt_trend,
            "target":     target,
            "on_focus":   on_focus,
            "note":       cur["notes"].get(lid, ""),
            "acc_7d":     round(acc7, 1) if acc7 is not None else None,
        })
    return jsonify(rows)

@app.route("/api/teacher/response-analysis")
def api_response_analysis():
    """Per-lesson response time distribution buckets."""
    data   = _load()
    result = {}
    for lid in LESSONS:
        hist = data.get(f"lesson_{lid}", {}).get("history", [])
        rts  = [h["response_time_s"] for h in hist if h.get("response_time_s",0) > 0]
        if not rts: continue
        buckets = {"<3s":0, "3-6s":0, "6-10s":0, ">10s":0}
        for rt in rts:
            if   rt < 3:  buckets["<3s"]  += 1
            elif rt < 6:  buckets["3-6s"] += 1
            elif rt < 10: buckets["6-10s"]+= 1
            else:         buckets[">10s"] += 1
        result[lid] = {
            "buckets": buckets,
            "median":  sorted(rts)[len(rts)//2],
            "p90":     sorted(rts)[int(len(rts)*.9)],
            "count":   len(rts),
        }
    return jsonify(result)

@app.route("/api/teacher/letter-analysis")
def api_letter_analysis():
    """Per-letter attempt counts and stage breakdown."""
    data = _load()
    rows = []
    for lt in string.ascii_uppercase:
        e     = data.get(f"letter_{lt}", {})
        hist  = e.get("history", [])
        stage = e.get("stage", 0)
        if not hist:
            rows.append({"letter":lt,"status":"untouched","stage":0,"attempts":0,"avg_acc":None})
            continue
        accs = [h.get("accuracy",0) for h in hist if "accuracy" in h]
        rows.append({
            "letter":   lt,
            "status":   _letter_status(e),
            "stage":    stage,
            "attempts": e.get("attempts", 0),
            "avg_acc":  round(sum(accs)/len(accs)*100, 1) if accs else None,
        })
    return jsonify(rows)

@app.route("/api/teacher/note", methods=["POST"])
def api_save_note():
    body = request.get_json(force=True)
    lid  = body.get("lesson_id")
    note = body.get("note","")
    if lid not in LESSONS:
        return jsonify({"error":"unknown lesson"}), 400
    cur = _load_curriculum()
    cur.setdefault("notes", {})[lid] = note
    _save_curriculum(cur)
    return jsonify({"ok": True})

# ══ TECHNICAL API ══════════════════════════════════════════════════════════════

@app.route("/api/system")
def api_system():
    data      = _load()
    file_size = os.path.getsize(DATA_PATH) if os.path.exists(DATA_PATH) else 0
    file_mod  = (datetime.fromtimestamp(os.path.getmtime(DATA_PATH))
                 .strftime("%Y-%m-%d %H:%M:%S")
                 if os.path.exists(DATA_PATH) else "—")

    lesson_records  = sum(len(data.get(f"lesson_{lid}",{}).get("history",[]))
                          for lid in LESSONS)
    letter_records  = sum(len(data.get(f"letter_{lt}",{}).get("history",[]))
                          for lt in string.ascii_uppercase)
    session_records = len(data.get("_sessions", []))
    total_records   = lesson_records + letter_records + session_records

    def pkg_ver(name):
        try:
            import importlib.metadata
            return importlib.metadata.version(name)
        except Exception:
            return "—"

    data_files = []
    for fname, label in [
        ("progress.json",        "Progress data"),
        ("profile.json",         "Child profile"),
        ("curriculum.json",      "Curriculum plan"),
        ("custom_exercises.json","Custom exercises"),
        ("custom_lessons.json",  "Custom lessons"),
    ]:
        fpath  = os.path.join(_ROOT, "data", fname)
        exists = os.path.exists(fpath)
        data_files.append({
            "name":     fname,
            "label":    label,
            "exists":   exists,
            "size_kb":  round(os.path.getsize(fpath)/1024, 1) if exists else 0,
            "modified": (datetime.fromtimestamp(os.path.getmtime(fpath))
                         .strftime("%Y-%m-%d %H:%M") if exists else "—"),
        })

    return jsonify({
        "python":          platform.python_version(),
        "platform":        platform.system() + " " + platform.release(),
        "machine":         platform.machine(),
        "pygame":          pkg_ver("pygame"),
        "mediapipe":       pkg_ver("mediapipe"),
        "flask":           pkg_ver("flask"),
        "opencv":          pkg_ver("opencv-python"),
        "numpy":           pkg_ver("numpy"),
        "data_file":       DATA_PATH,
        "file_size_kb":    round(file_size / 1024, 1),
        "last_modified":   file_mod,
        "lesson_records":  lesson_records,
        "letter_records":  letter_records,
        "session_records": session_records,
        "total_records":   total_records,
        "custom_exercises":sum(len(v) for v in _load_custom().values()),
        "custom_lessons":  len(_load_custom_lessons()),
        "data_keys":       sorted(data.keys()),
        "streak":          data.get("_streak", 0),
        "last_played":     data.get("_last_played", "—"),
        "data_files":      data_files,
    })

@app.route("/api/data-integrity")
def api_data_integrity():
    data   = _load()
    issues = []
    stats  = {"checked": 0, "warnings": 0, "errors": 0}

    for lid in LESSONS:
        hist = data.get(f"lesson_{lid}", {}).get("history", [])
        stats["checked"] += len(hist)

        ts_list = [h.get("ts", 0) for h in hist]
        for i in range(1, len(ts_list)):
            if ts_list[i] < ts_list[i-1] - 1:
                issues.append({"level":"warning","type":"timestamp_order",
                    "msg":f"{SHORT.get(lid,lid)}: out-of-order timestamps at index {i}"})
                stats["warnings"] += 1
                break

        bad_rt = [h for h in hist
                  if h.get("response_time_s",0) > 120 or
                     (h.get("response_time_s") is not None and h.get("response_time_s",1) < 0)]
        if bad_rt:
            issues.append({"level":"warning","type":"bad_rt",
                "msg":f"{SHORT.get(lid,lid)}: {len(bad_rt)} response times outside 0-120s"})
            stats["warnings"] += 1

        e = data.get(f"lesson_{lid}", {})
        if e.get("correct_streak",0) > e.get("best_streak",0):
            issues.append({"level":"error","type":"streak_inconsistency",
                "msg":f"{SHORT.get(lid,lid)}: correct_streak > best_streak"})
            stats["errors"] += 1

        if e.get("total_correct",0) > e.get("total_attempts",0):
            issues.append({"level":"error","type":"count_inconsistency",
                "msg":f"{SHORT.get(lid,lid)}: correct > attempts"})
            stats["errors"] += 1

    for i, s in enumerate(data.get("_sessions", [])):
        if s.get("correct",0) > s.get("questions",1):
            issues.append({"level":"error","type":"session_count",
                "msg":f"Session {i} ({s.get('date','?')}): correct > questions"})
            stats["errors"] += 1
        if s.get("accuracy",0) > 1.0:
            issues.append({"level":"warning","type":"bad_accuracy",
                "msg":f"Session {i}: accuracy > 1.0"})
            stats["warnings"] += 1

    return jsonify({"issues":issues, "stats":stats, "healthy":stats["errors"]==0})

@app.route("/api/storage-breakdown")
def api_storage_breakdown():
    data    = _load()
    details = []

    for lid in LESSONS:
        e    = data.get(f"lesson_{lid}", {})
        hist = e.get("history", [])
        details.append({
            "category":   "Lesson",
            "label":      SHORT.get(lid, lid),
            "key":        f"lesson_{lid}",
            "rows":       len(hist),
            "size_bytes": len(json.dumps(e)),
        })

    for lt in string.ascii_uppercase:
        e = data.get(f"letter_{lt}", {})
        if not e: continue
        details.append({
            "category":   "Letter",
            "label":      f"Letter {lt}",
            "key":        f"letter_{lt}",
            "rows":       len(e.get("history",[])),
            "size_bytes": len(json.dumps(e)),
        })

    sessions = data.get("_sessions", [])
    details.append({
        "category":   "Meta",
        "label":      "Session snapshots",
        "key":        "_sessions",
        "rows":       len(sessions),
        "size_bytes": len(json.dumps(sessions)),
    })

    total_bytes = sum(d["size_bytes"] for d in details)
    return jsonify({"details":details, "total_bytes":total_bytes,
                    "total_kb":round(total_bytes/1024,1)})

@app.route("/api/session-log")
def api_session_log():
    data     = _load()
    sessions = sorted(data.get("_sessions", []), key=lambda s: -s.get("ts",0))
    for s in sessions:
        ts = s.get("ts", 0)
        s["datetime"] = (datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                         if ts else "—")
    return jsonify(sessions)

@app.route("/api/reset/lesson/<lesson_id>", methods=["POST"])
def api_reset_lesson(lesson_id):
    if lesson_id not in LESSONS:
        abort(404)
    data = _load()
    data.pop(f"lesson_{lesson_id}", None)
    _save(data)
    return jsonify({"ok": True, "reset": lesson_id})

@app.route("/api/reset/letters", methods=["POST"])
def api_reset_letters():
    data = _load()
    for lt in string.ascii_uppercase:
        data.pop(f"letter_{lt}", None)
    _save(data)
    return jsonify({"ok": True})

@app.route("/api/reset/all", methods=["POST"])
def api_reset_all():
    _save({})
    return jsonify({"ok": True})

@app.route("/api/backup")
def api_backup():
    if not os.path.exists(DATA_PATH):
        abort(404)
    return send_file(DATA_PATH,
                     download_name=f"progress_backup_{date.today()}.json",
                     as_attachment=True)

@app.route("/api/restore", methods=["POST"])
def api_restore():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    try:
        content = json.loads(f.read().decode("utf-8"))
        _save(content)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ══ SERVER LAUNCH ══════════════════════════════════════════════════════════════

def start_dashboard_server():
    """Start Flask in a background daemon thread."""
    def _run():
        import logging
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print(f"[Dashboard] http://localhost:{PORT}")

if __name__ == "__main__":
    # Allow running standalone: python dashboard/server.py
    os.chdir(_ROOT)
    print(f"[Dashboard] Starting standalone at http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True, use_reloader=False)
