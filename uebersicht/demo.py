"""Erzeugt plausible Beispieldaten im Format der Garmin-Antworten (ohne API-Schlüssel)."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone


def _ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def demo_raw(days: int = 120, seed: int = 7) -> dict[str, list]:
    rng = random.Random(seed)
    end = date.today()
    activities, sleep, hrv = [], [], []
    plan = {0: "strength_training", 1: "running", 3: "running", 4: "yoga", 5: "road_biking", 6: "running"}

    for i in range(days):
        day = end - timedelta(days=days - 1 - i)
        wd = day.weekday()

        # Schlaf der Nacht, die an diesem Tag endet
        total = rng.gauss(7.2 if wd < 5 else 7.9, 0.6) * 3600
        deep = total * rng.uniform(0.14, 0.22)
        rem = total * rng.uniform(0.18, 0.25)
        awake = rng.uniform(5, 40) * 60
        bed = datetime.combine(day - timedelta(days=1), datetime.min.time()) + timedelta(
            hours=22, minutes=rng.randint(30, 110)
        )
        night_hrv = rng.gauss(52, 6) + (i / days) * 4
        sleep.append(
            {
                "dailySleepDTO": {
                    "calendarDate": day.isoformat(),
                    "sleepTimeSeconds": round(total),
                    "deepSleepSeconds": round(deep),
                    "remSleepSeconds": round(rem),
                    "lightSleepSeconds": round(total - deep - rem),
                    "awakeSleepSeconds": round(awake),
                    "sleepStartTimestampLocal": _ms(bed),
                    "sleepEndTimestampLocal": _ms(bed + timedelta(seconds=total + awake)),
                    "averageRespirationValue": round(rng.gauss(14.5, 0.6), 1),
                    "sleepScores": {"overall": {"value": max(40, min(98, round(55 + total / 3600 * 3 + rng.gauss(0, 6))))}},
                },
                "restingHeartRate": round(rng.gauss(52, 2)),
                "avgOvernightHrv": round(night_hrv),
            }
        )
        hrv.append({"calendarDate": day.isoformat(), "lastNightAvg": round(night_hrv), "weeklyAvg": round(52 + (i / days) * 4), "status": "BALANCED"})

        kind = plan.get(wd)
        if kind is None or rng.random() < 0.15:
            continue
        start = datetime.combine(day, datetime.min.time()) + timedelta(hours=rng.choice([7, 12, 18]), minutes=rng.randint(0, 50))
        if kind == "running":
            dur = rng.uniform(30, 75 if wd == 6 else 55) * 60
            speed = rng.uniform(2.7, 3.2)
            dist, name, hr = dur * speed, rng.choice(["Morgenlauf", "Lauf am Abend", "Lockerer Lauf", "Intervalle"]), rng.gauss(148, 7)
        elif kind == "road_biking":
            dur = rng.uniform(60, 150) * 60
            speed = rng.uniform(7.0, 8.5)
            dist, name, hr = dur * speed, "Radausfahrt", rng.gauss(132, 8)
        else:
            dur = rng.uniform(30, 60) * 60
            speed, dist, hr = None, None, rng.gauss(110 if kind == "yoga" else 120, 8)
            name = "Yoga" if kind == "yoga" else "Krafttraining"
        activities.append(
            {
                "activityId": 10_000_000 + i,
                "activityName": name,
                "startTimeLocal": start.strftime("%Y-%m-%d %H:%M:%S"),
                "activityType": {"typeKey": kind},
                "duration": round(dur, 1),
                "distance": round(dist, 1) if dist else None,
                "averageSpeed": speed,
                "averageHR": round(hr),
                "maxHR": round(hr + rng.uniform(12, 30)),
                "calories": round(dur / 60 * rng.uniform(7, 12)),
                "elevationGain": round(rng.uniform(20, 600)) if dist else None,
                "aerobicTrainingEffect": round(rng.uniform(1.8, 4.2), 1),
            }
        )
    return {"activities": activities, "sleep": sleep, "hrv": [{"hrvSummaries": hrv}]}
