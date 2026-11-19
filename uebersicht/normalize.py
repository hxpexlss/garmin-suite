"""Bringt Antworten der Garmin Personal API in ein einheitliches, flaches Format.

Garmin hat für die Personal API keine festen Antwort-Schemas im Python-Client
dokumentiert. Die Felder unten entsprechen den Namen, die Garmin Connect intern
verwendet; zusätzlich werden gängige Alternativnamen akzeptiert. Fehlt ein Wert,
bleibt er ``None`` und die Übersicht zeigt "–".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Iterator


def _walk(obj: Any) -> Iterator[dict]:
    """Liefert alle Dicts in einer beliebig verschachtelten JSON-Struktur."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _first(d: dict, *keys: str) -> Any:
    """Erster vorhandene Wert; Punkte trennen verschachtelte Schlüssel."""
    for key in keys:
        cur: Any = d
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                cur = None
                break
        if cur is not None:
            return cur
    return None


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_date(value: Any) -> str | None:
    """Datum als YYYY-MM-DD aus String oder Millisekunden-Zeitstempel."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
    text = str(value)
    return text[:10] if len(text) >= 10 else None


def _local_time(value: Any) -> str | None:
    """Uhrzeit HH:MM. Garmins *Local*-Zeitstempel sind Ortszeit, als UTC kodiert."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%H:%M")
    if isinstance(value, str) and len(value) >= 16:
        return value[11:16]
    return None


# --- Trainings -----------------------------------------------------------------

ACTIVITY_LABELS = {
    "running": "Laufen",
    "trail_running": "Trailrun",
    "treadmill_running": "Laufband",
    "track_running": "Bahnlauf",
    "cycling": "Radfahren",
    "road_biking": "Rennrad",
    "mountain_biking": "Mountainbike",
    "gravel_cycling": "Gravel",
    "indoor_cycling": "Indoor-Rad",
    "virtual_ride": "Virtuelles Radfahren",
    "lap_swimming": "Schwimmen (Becken)",
    "open_water_swimming": "Freiwasser",
    "swimming": "Schwimmen",
    "walking": "Gehen",
    "hiking": "Wandern",
    "strength_training": "Krafttraining",
    "indoor_cardio": "Cardio",
    "hiit": "HIIT",
    "yoga": "Yoga",
    "pilates": "Pilates",
    "elliptical": "Crosstrainer",
    "indoor_rowing": "Rudergerät",
    "rowing": "Rudern",
    "resort_skiing_snowboarding_ws": "Ski/Snowboard",
    "backcountry_skiing": "Skitour",
    "cross_country_skiing_ws": "Langlauf",
    "multi_sport": "Multisport",
}


def activity_label(type_key: str | None) -> str:
    if not type_key:
        return "Sonstiges"
    return ACTIVITY_LABELS.get(type_key, type_key.replace("_", " ").capitalize())


def normalize_activities(raw: Any) -> list[dict]:
    """Aktivitätsliste (search_activities) → flache Datensätze, neueste zuerst."""
    seen: set = set()
    out: list[dict] = []
    for d in _walk(raw):
        act_id = _first(d, "activityId", "activityID", "summaryId")
        start = _first(d, "startTimeLocal", "startTimeGMT", "startTimeInSeconds")
        if act_id is None or start is None or act_id in seen:
            continue
        seen.add(act_id)
        if isinstance(start, (int, float)) and start < 10**11:  # Sekunden statt ms
            start = start * 1000
        type_key = _first(d, "activityType.typeKey", "activityTypeDTO.typeKey", "activityType")
        if isinstance(type_key, dict):
            type_key = type_key.get("typeKey")
        out.append(
            {
                "id": act_id,
                "name": _first(d, "activityName", "name") or activity_label(type_key),
                "date": _iso_date(start),
                "time": _local_time(start),
                "type": type_key or "other",
                "typeLabel": activity_label(type_key),
                "durationS": _num(_first(d, "duration", "durationInSeconds", "elapsedDuration")),
                "distanceM": _num(_first(d, "distance", "distanceInMeters")),
                "avgHr": _num(_first(d, "averageHR", "averageHeartRateInBeatsPerMinute")),
                "maxHr": _num(_first(d, "maxHR", "maxHeartRateInBeatsPerMinute")),
                "calories": _num(_first(d, "calories", "activeKilocalories")),
                "elevationM": _num(_first(d, "elevationGain", "totalElevationGainInMeters")),
                "avgSpeedMs": _num(_first(d, "averageSpeed", "averageSpeedInMetersPerSecond")),
                "trainingEffect": _num(_first(d, "aerobicTrainingEffect")),
                "trainingLoad": _num(_first(d, "activityTrainingLoad")),
            }
        )
    out.sort(key=lambda a: (a["date"] or "", a["time"] or ""), reverse=True)
    return out


# --- Schlaf --------------------------------------------------------------------

_SLEEP_TOTAL = ("sleepTimeSeconds", "durationInSeconds", "totalSleepSeconds")


def _sleep_record(d: dict, parent: dict | None) -> dict | None:
    date = _iso_date(_first(d, "calendarDate", "sleepDate"))
    total = _num(_first(d, *_SLEEP_TOTAL))
    if not date or total is None:
        return None
    ctx = parent or {}
    score = _first(d, "sleepScores.overall.value", "overallSleepScore.value", "sleepScore", "overallScore")
    if score is None:
        score = _first(ctx, "sleepScores.overall.value", "sleepScore")
    return {
        "date": date,
        "totalS": total,
        "deepS": _num(_first(d, "deepSleepSeconds", "deepSleepDurationInSeconds")),
        "lightS": _num(_first(d, "lightSleepSeconds", "lightSleepDurationInSeconds")),
        "remS": _num(_first(d, "remSleepSeconds", "remSleepInSeconds", "remSleepDurationInSeconds")),
        "awakeS": _num(_first(d, "awakeSleepSeconds", "awakeDurationInSeconds")),
        "score": _num(score.get("value") if isinstance(score, dict) else score),
        "start": _local_time(_first(d, "sleepStartTimestampLocal", "startTimeLocal")),
        "end": _local_time(_first(d, "sleepEndTimestampLocal", "endTimeLocal")),
        "restingHr": _num(_first(d, "restingHeartRate") or _first(ctx, "restingHeartRate")),
        "avgHrv": _num(_first(d, "avgOvernightHrv") or _first(ctx, "avgOvernightHrv")),
        "avgRespiration": _num(_first(d, "averageRespirationValue", "avgSleepRespirationValue")),
    }


def normalize_sleep(raws: Iterable[Any]) -> list[dict]:
    """Schlafantworten (einzelne Tage oder Zusammenfassungen) → ein Datensatz pro Nacht."""
    by_date: dict[str, dict] = {}
    for raw in raws:
        for parent in _walk(raw):
            for d in [parent, *[v for v in parent.values() if isinstance(v, dict)]]:
                rec = _sleep_record(d, parent if d is not parent else None)
                if rec is None:
                    continue
                prev = by_date.get(rec["date"], {})
                # Vorhandene Werte nicht mit None überschreiben.
                by_date[rec["date"]] = {**prev, **{k: v for k, v in rec.items() if v is not None or k not in prev}}
    return [by_date[k] for k in sorted(by_date)]


def normalize_hrv(raws: Iterable[Any]) -> dict[str, dict]:
    """HRV-Zusammenfassungen → {Datum: {lastNightAvg, weeklyAvg, status}}."""
    out: dict[str, dict] = {}
    for raw in raws:
        for d in _walk(raw):
            date = _iso_date(_first(d, "calendarDate"))
            night = _num(_first(d, "lastNightAvg", "lastNightAverage"))
            if not date or night is None:
                continue
            out[date] = {
                "lastNightAvg": night,
                "weeklyAvg": _num(_first(d, "weeklyAvg", "weeklyAverage")),
                "status": _first(d, "status"),
            }
    return out


def merge_hrv(sleep: list[dict], hrv: dict[str, dict]) -> list[dict]:
    """HRV-Werte in die Schlafdatensätze übernehmen; Nächte nur mit HRV ergänzen."""
    by_date = {s["date"]: dict(s) for s in sleep}
    for date, h in hrv.items():
        rec = by_date.setdefault(date, {"date": date})
        rec["hrv"] = h["lastNightAvg"]
        rec["hrvWeekly"] = h["weeklyAvg"]
        rec["hrvStatus"] = h["status"]
    for rec in by_date.values():
        rec.setdefault("hrv", rec.get("avgHrv"))
    return [by_date[k] for k in sorted(by_date)]
