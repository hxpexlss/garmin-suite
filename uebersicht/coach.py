"""Regelbasierte Trainingsvorschläge aus Belastung, Schlaf und HRV.

Bewusst einfach und nachvollziehbar: Jeder Vorschlag nennt seine Gründe. Kein
Ersatz für Trainer oder Arzt – bei Schmerzen, Krankheit oder Unwohlsein gilt das
Körpergefühl, nicht die Zahl.

Bausteine:
- Belastung je Training: Garmins ``activityTrainingLoad``, sonst Banister-TRIMP
  aus Dauer und Herzfrequenzreserve, sonst grob aus der Dauer.
- Akut (7 Tage) zu chronisch (28 Tage, als Wochenschnitt): ACWR. 0,8–1,3 gilt als
  günstiger Bereich, über 1,5 steigt das Überlastungsrisiko.
- HRV der letzten Nacht im Vergleich zum eigenen 28-Tage-Schnitt.
- Sleep Score bzw. Schlafdauer der letzten Nacht.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import mean, median

DISCLAIMER = ("Automatischer Vorschlag aus deinen Garmin-Daten, kein ärztlicher oder trainerischer Rat. "
              "Fühlst du dich krank oder hast Schmerzen, lass das Training aus.")

ZONES = [("Z1", 0.50, 0.60, "sehr locker"), ("Z2", 0.60, 0.70, "Grundlage"), ("Z3", 0.70, 0.80, "zügig"),
         ("Z4", 0.80, 0.90, "Schwelle"), ("Z5", 0.90, 1.00, "maximal")]


def sport_of(type_key: str | None) -> str:
    t = (type_key or "").lower()
    if "run" in t:
        return "run"
    if any(k in t for k in ("cycl", "bik", "ride")):
        return "bike"
    if "swim" in t:
        return "swim"
    if "strength" in t or "hiit" in t:
        return "strength"
    return "other"


SPORT_NAMES = {"run": "Laufen", "bike": "Radfahren", "swim": "Schwimmen", "strength": "Krafttraining", "other": "Training"}


def _de(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def _d(s: str) -> date:
    return date.fromisoformat(s)


def activity_load(a: dict, max_hr: float, rest_hr: float) -> float:
    if a.get("trainingLoad"):
        return float(a["trainingLoad"])
    minutes = (a.get("durationS") or 0) / 60
    hr = a.get("avgHr")
    if hr and max_hr > rest_hr:
        hrr = min(1.0, max(0.0, (hr - rest_hr) / (max_hr - rest_hr)))
        return minutes * hrr * 0.64 * math.exp(1.92 * hrr)
    return minutes * 0.5


def is_hard(a: dict, max_hr: float) -> bool:
    if (a.get("trainingEffect") or 0) >= 3.5:
        return True
    return bool(a.get("avgHr") and a["avgHr"] >= 0.82 * max_hr)


def _scale(v: float, lo: float, hi: float) -> float:
    return max(0.0, min(100.0, (v - lo) / (hi - lo) * 100))


def suggest(acts: list[dict], nights: list[dict], today: date | None = None,
            max_hr: float | None = None, resting_hr: float | None = None) -> dict:
    today = today or date.today()
    acts = [a for a in acts if a.get("date") and _d(a["date"]) <= today]
    recent = [a for a in acts if _d(a["date"]) > today - timedelta(days=180)]
    by_night = {n["date"]: n for n in nights}

    # --- Kenngrößen -------------------------------------------------------------
    observed_max = max((a.get("maxHr") or 0 for a in recent), default=0)
    if max_hr:
        hf_max, hf_max_src = float(max_hr), "Einstellung"
    elif observed_max >= 140:
        hf_max, hf_max_src = float(observed_max), "höchster Wert der letzten 180 Tage"
    else:
        hf_max, hf_max_src = 190.0, "Annahme – bitte in der Konfiguration setzen"
    rests = [n["restingHr"] for d, n in by_night.items() if n.get("restingHr") and _d(d) > today - timedelta(days=14)]
    hf_rest = float(resting_hr or (median(rests) if rests else 60))

    daily: dict[date, float] = {}
    for a in acts:
        daily[_d(a["date"])] = daily.get(_d(a["date"]), 0) + activity_load(a, hf_max, hf_rest)
    acute = sum(v for d, v in daily.items() if d > today - timedelta(days=7))
    chronic = sum(v for d, v in daily.items() if d > today - timedelta(days=28)) / 4
    history_days = (today - min(daily)).days + 1 if daily else 0
    acwr = round(acute / chronic, 2) if chronic > 0 and history_days >= 21 else None

    last_night = next((by_night[k] for k in (today.isoformat(), (today - timedelta(days=1)).isoformat())
                       if k in by_night and by_night[k].get("totalS")), None)
    hrv_hist = [n["hrv"] for d, n in by_night.items()
                if n.get("hrv") and today - timedelta(days=28) <= _d(d) < today]
    hrv_now = (by_night.get(today.isoformat()) or {}).get("hrv")
    hrv_base = round(mean(hrv_hist), 1) if len(hrv_hist) >= 7 else None
    hrv_ratio = round(hrv_now / hrv_base, 2) if hrv_now and hrv_base else None

    hard_dates = sorted({_d(a["date"]) for a in acts if is_hard(a, hf_max)})
    days_since_hard = (today - hard_dates[-1]).days if hard_dates else None
    streak, d = 0, today - timedelta(days=1)
    trained_dates = {_d(a["date"]) for a in acts}
    while d in trained_dates:
        streak += 1; d -= timedelta(days=1)
    done_today = [a for a in acts if a["date"] == today.isoformat()]

    # --- Bereitschaft -----------------------------------------------------------
    if last_night and last_night.get("score") is not None:
        p_sleep = float(last_night["score"])
    elif last_night:
        p_sleep = _scale(last_night["totalS"] / 3600, 4.5, 8.0)
    else:
        p_sleep = 70.0
    p_hrv = _scale(hrv_ratio, 0.80, 1.05) if hrv_ratio else 70.0
    if acwr is None:
        p_load = 75.0
    elif acwr > 1.5:
        p_load = 25.0
    elif acwr > 1.3:
        p_load = 55.0
    elif acwr < 0.8:
        p_load = 85.0
    else:
        p_load = 95.0
    readiness = round(0.40 * p_sleep + 0.35 * p_hrv + 0.25 * p_load)
    r_label = "hoch" if readiness >= 75 else "mittel" if readiness >= 55 else "niedrig"

    # --- Hauptsportart & Bezugsgrößen -------------------------------------------
    last28 = [a for a in acts if _d(a["date"]) > today - timedelta(days=28)]
    counts: dict[str, int] = {}
    for a in last28:
        s = sport_of(a.get("type"))
        if s in ("run", "bike", "swim"):
            counts[s] = counts.get(s, 0) + 1
    sport = max(counts, key=counts.get) if counts else "run"
    of_sport = [a for a in last28 if sport_of(a.get("type")) == sport]
    longest_min = max(((a.get("durationS") or 0) / 60 for a in of_sport), default=0)
    long_recent = any(sport_of(a.get("type")) == sport and (a.get("durationS") or 0) / 60 >= max(60, 0.8 * longest_min)
                      and _d(a["date"]) > today - timedelta(days=6) for a in acts)

    # --- Entscheidung -------------------------------------------------------------
    reasons: list[str] = []
    if last_night:
        reasons.append(f"Letzte Nacht {_de(last_night['totalS'] / 3600)} h Schlaf"
                       + (f", Sleep Score {last_night['score']:.0f}" if last_night.get("score") is not None else ""))
    if hrv_ratio:
        reasons.append(f"HRV {hrv_now:.0f} ms, {round((hrv_ratio - 1) * 100):+d} % zu deinem 28-Tage-Schnitt ({hrv_base:.0f} ms)")
    if acwr is not None:
        reasons.append(f"Belastung 7 Tage zu 28 Tagen: {_de(acwr, 2)}"
                       + (" (hoch)" if acwr > 1.3 else " (niedrig)" if acwr < 0.8 else " (im grünen Bereich)"))
    if days_since_hard is not None:
        reasons.append("Letzte harte Einheit " + ("heute" if days_since_hard == 0 else "gestern" if days_since_hard == 1
                                                   else f"vor {days_since_hard} Tagen"))
    if streak >= 3:
        reasons.append(f"{streak} Trainingstage in Folge")

    if readiness < 40 or (hrv_ratio and hrv_ratio < 0.85) or (acwr and acwr > 1.5) or streak >= 6:
        kind = "rest"
    elif readiness < 60 or (acwr and acwr > 1.3) or (days_since_hard is not None and days_since_hard <= 1) or streak >= 4:
        kind = "easy"
    elif today.weekday() >= 5 and not long_recent and readiness >= 60 and longest_min >= 30:
        kind = "long"
    elif readiness >= 70 and (days_since_hard is None or days_since_hard >= 2):
        kind = "hard"
    else:
        kind = "moderate"

    zones = [{"zone": z, "label": lbl, "from": round(lo * hf_max), "to": round(hi * hf_max)} for z, lo, hi, lbl in ZONES]
    zr = {z["zone"]: (z["from"], z["to"]) for z in zones}
    workout = _workout(kind, sport, longest_min, zr, today)

    # --- Woche -----------------------------------------------------------------
    wk_start = today - timedelta(days=today.weekday())
    done_week = sum((a.get("durationS") or 0) for a in acts if _d(a["date"]) >= wk_start) / 60
    prev = [sum((a.get("durationS") or 0) for a in acts
                if wk_start - timedelta(days=7 * (i + 1)) <= _d(a["date"]) < wk_start - timedelta(days=7 * i)) / 60
            for i in range(4)]
    base = mean(prev) if any(prev) else 0
    factor = 0.9 if (acwr and acwr > 1.5) else 1.0 if (acwr and acwr > 1.3) else 1.05
    target = round(base * factor)

    hints: list[str] = []
    strength_recent = [a for a in acts if sport_of(a.get("type")) == "strength" and _d(a["date"]) > today - timedelta(days=10)]
    if not strength_recent and acts:
        hints.append("Seit über einer Woche kein Krafttraining – 2× pro Woche 20–30 min stabilisieren Sehnen und Gelenke.")
    if acwr is not None and acwr < 0.8 and readiness >= 60:
        hints.append("Deine Belastung liegt unter deinem Schnitt – du kannst den Umfang behutsam steigern (max. ~10 % pro Woche).")
    if hf_max_src.startswith("Annahme"):
        hints.append("Maximalpuls unbekannt – trage ihn in der Server-Konfiguration ein, damit die Pulszonen stimmen.")
    if acwr is None:
        hints.append("Für die Belastungssteuerung braucht es mindestens drei Wochen Trainingsdaten.")
    if done_today:
        hints.append("Heute bereits trainiert: " + ", ".join(a.get("name") or a.get("typeLabel") or "Training" for a in done_today)
                     + ". Der Vorschlag gilt dann eher für morgen.")

    return {
        "date": today.isoformat(),
        "readiness": {"score": readiness, "label": r_label,
                      "parts": {"sleep": round(p_sleep), "hrv": round(p_hrv), "load": round(p_load)}},
        "today": {**workout, "kind": kind, "sport": sport, "sportLabel": SPORT_NAMES[sport], "reasons": reasons},
        "week": {"doneMin": round(done_week), "targetMin": target, "remainingMin": max(0, target - round(done_week)),
                 "previousWeeksMin": [round(p) for p in prev]},
        "metrics": {"acuteLoad": round(acute), "chronicLoad": round(chronic), "acwr": acwr,
                    "hrvLastNight": hrv_now, "hrvBaseline": hrv_base, "hrvRatio": hrv_ratio,
                    "sleepScore": (last_night or {}).get("score"), "sleepS": (last_night or {}).get("totalS"),
                    "restingHr": round(hf_rest), "maxHr": round(hf_max), "maxHrSource": hf_max_src,
                    "daysSinceHard": days_since_hard, "streakDays": streak},
        "zones": zones,
        "hints": hints,
        "disclaimer": DISCLAIMER,
    }


def _rng(zr: dict, z: str) -> str:
    lo, hi = zr[z]
    return f"{z} ({lo}–{hi} bpm)"


def _workout(kind: str, sport: str, longest_min: float, zr: dict, today: date) -> dict:
    variant = today.isocalendar().week % 2
    if kind == "rest":
        return {"title": "Ruhetag", "durationMin": [0, 30],
                "details": ["Kein strukturiertes Training.", "Optional 20–30 min Spaziergang, Mobilität oder Dehnen.",
                            "Früh schlafen gehen hilft am meisten."]}
    if sport == "bike":
        table = {
            "easy": ("Lockere Ausfahrt", [45, 60], [f"Gleichmäßig in {_rng(zr, 'Z2')}, hohe Trittfrequenz (85–95/min)."]),
            "moderate": ("Grundlagenausfahrt", [60, 90], [f"Überwiegend {_rng(zr, 'Z2')}.", "Hügel ruhig hochfahren, nicht über Z3."]),
            "hard": (("Schwellenintervalle", [60, 75], ["15 min einfahren in Z1–Z2.", f"4 × 8 min in {_rng(zr, 'Z4')}, je 4 min locker.", "10 min ausfahren."])
                     if variant else
                     ("Sweet-Spot", [60, 75], ["15 min einfahren.", f"3 × 12 min oberes Z3 bis unteres Z4 ({zr['Z3'][1] - 5}–{zr['Z4'][0] + 5} bpm), je 5 min locker.", "10 min ausfahren."])),
        }
    elif sport == "swim":
        table = {
            "easy": ("Technikschwimmen", [25, 35], ["Locker einschwimmen, dann 8 × 50 m Technikübungen.", "Ruhig ausschwimmen."]),
            "moderate": ("Ausdauerschwimmen", [35, 45], ["300 m einschwimmen.", "3 × 400 m gleichmäßig, 30 s Pause.", "200 m locker."]),
            "hard": ("Intervalle", [40, 50], ["300 m einschwimmen.", "10 × 100 m zügig, 20 s Pause.", "200 m locker."]),
        }
    else:
        table = {
            "easy": ("Lockerer Dauerlauf", [30, 45], [f"Ruhig in {_rng(zr, 'Z2')} – du solltest dich unterhalten können."]),
            "moderate": ("Grundlagenlauf", [45, 60], [f"Gleichmäßig in {_rng(zr, 'Z2')}.", "Am Ende 4–6 Steigerungen über 80 m."]),
            "hard": (("Intervalle", [50, 60], ["15 min einlaufen in Z2.", f"5 × 4 min in {_rng(zr, 'Z4')}, je 3 min Trabpause.", "10 min auslaufen."])
                     if variant else
                     ("Tempodauerlauf", [50, 60], ["15 min einlaufen.", f"2 × 12 min in {_rng(zr, 'Z3')} bis unteres Z4, 3 min Trabpause.", "10 min auslaufen."])),
        }
    if kind == "long":
        base = max(longest_min, 45)
        lo, hi = round(base), round(min(base * 1.1, base + 15))
        name = {"bike": "Lange Ausfahrt", "swim": "Langes Ausdauerschwimmen"}.get(sport, "Langer Lauf")
        return {"title": name, "durationMin": [lo, hi],
                "details": [f"Ruhig in {_rng(zr, 'Z2')}, keine Tempospitzen.",
                            f"Höchstens etwas länger als deine längste Einheit der letzten 4 Wochen ({round(longest_min)} min).",
                            "Bei über 75 min: Trinken und etwas Kohlenhydrate mitnehmen."]}
    title, dur, details = table[kind]
    return {"title": title, "durationMin": dur, "details": details}
