"""Kennzahlen für einen Zeitraum – dieselben Werte, die Web-Seite und App anzeigen."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Iterable


def _avg(values: Iterable) -> float | None:
    v = [x for x in values if x is not None]
    return round(mean(v), 1) if v else None


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def overview(acts: list[dict], nights: list[dict], start: date, end: date) -> dict:
    days = (end - start).days + 1
    weeks = max(1.0, days / 7)
    acts = [a for a in acts if a.get("date") and start.isoformat() <= a["date"] <= end.isoformat()]
    nights = [n for n in nights if start.isoformat() <= n["date"] <= end.isoformat()]
    dur = sum(a.get("durationS") or 0 for a in acts)
    dist = sum(a.get("distanceM") or 0 for a in acts)

    weekly: dict[date, dict] = {}
    w = monday(start)
    while w <= end:
        weekly[w] = {"weekStart": w.isoformat(), "hours": 0.0, "count": 0, "km": 0.0}
        w += timedelta(days=7)
    sports: dict[str, dict] = {}
    for a in acts:
        wk = weekly.get(monday(date.fromisoformat(a["date"])))
        h = (a.get("durationS") or 0) / 3600
        km = (a.get("distanceM") or 0) / 1000
        if wk:
            wk["hours"] += h; wk["count"] += 1; wk["km"] += km
        s = sports.setdefault(a.get("typeLabel") or "Sonstiges", {"label": a.get("typeLabel") or "Sonstiges", "hours": 0.0, "count": 0, "km": 0.0})
        s["hours"] += h; s["count"] += 1; s["km"] += km
    for row in [*weekly.values(), *sports.values()]:
        row["hours"] = round(row["hours"], 2); row["km"] = round(row["km"], 1)

    with_total = [n for n in nights if n.get("totalS")]
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "training": {
            "count": len(acts),
            "durationS": round(dur),
            "distanceM": round(dist),
            "avgHr": _avg(a.get("avgHr") for a in acts),
            "perWeek": {"count": round(len(acts) / weeks, 1), "durationS": round(dur / weeks), "distanceM": round(dist / weeks)},
            "weekly": list(weekly.values()),
            "sports": sorted(sports.values(), key=lambda s: -s["hours"]),
        },
        "sleep": {
            "nights": len(with_total),
            "avgTotalS": _avg(n.get("totalS") for n in with_total),
            "avgScore": _avg(n.get("score") for n in nights),
            "avgHrv": _avg(n.get("hrv") for n in nights),
            "avgRestingHr": _avg(n.get("restingHr") for n in nights),
            "lastNight": with_total[-1] if with_total else None,
        },
    }
