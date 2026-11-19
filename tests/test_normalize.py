import unittest

from uebersicht.__main__ import build_dataset, render
from uebersicht.demo import demo_raw
from uebersicht.normalize import merge_hrv, normalize_activities, normalize_hrv, normalize_sleep


class NormalizeTest(unittest.TestCase):
    def test_activity_fields(self):
        raw = [{"activityId": 1, "activityName": "Lauf", "startTimeLocal": "2026-11-01 07:30:00",
                "activityType": {"typeKey": "running"}, "duration": 1800.0, "distance": 5000.0, "averageHR": 150}]
        (a,) = normalize_activities(raw)
        self.assertEqual((a["date"], a["time"], a["typeLabel"]), ("2026-11-01", "07:30", "Laufen"))
        self.assertEqual((a["durationS"], a["distanceM"], a["avgHr"]), (1800.0, 5000.0, 150.0))

    def test_activities_deduplicated_and_sorted(self):
        raw = [{"activityId": 1, "startTimeLocal": "2026-11-01 07:00:00"},
               {"activityId": 2, "startTimeLocal": "2026-11-03 07:00:00"},
               {"activityId": 1, "startTimeLocal": "2026-11-01 07:00:00"}]
        self.assertEqual([a["id"] for a in normalize_activities({"activities": raw})], [2, 1])

    def test_sleep_wrapped_dto_uses_parent_context(self):
        raw = {"dailySleepDTO": {"calendarDate": "2026-11-02", "sleepTimeSeconds": 27000,
                                 "deepSleepSeconds": 5000, "sleepScores": {"overall": {"value": 81}}},
               "restingHeartRate": 49, "avgOvernightHrv": 57}
        (s,) = normalize_sleep([raw])
        self.assertEqual((s["totalS"], s["deepS"], s["score"], s["restingHr"], s["avgHrv"]),
                         (27000.0, 5000.0, 81.0, 49.0, 57.0))

    def test_sleep_summary_list(self):
        raw = [{"calendarDate": "2026-11-01", "sleepTimeSeconds": 25000},
               {"calendarDate": "2026-11-02", "durationInSeconds": 26000, "deepSleepDurationInSeconds": 4000}]
        nights = normalize_sleep([raw])
        self.assertEqual([n["date"] for n in nights], ["2026-11-01", "2026-11-02"])
        self.assertEqual(nights[1]["deepS"], 4000.0)

    def test_hrv_merge(self):
        hrv = normalize_hrv([{"hrvSummaries": [{"calendarDate": "2026-11-02", "lastNightAvg": 60, "weeklyAvg": 55}]}])
        merged = merge_hrv([{"date": "2026-11-01", "totalS": 1, "avgHrv": 50}], hrv)
        self.assertEqual([(m["date"], m["hrv"]) for m in merged], [("2026-11-01", 50), ("2026-11-02", 60)])

    def test_demo_renders(self):
        import tempfile
        from pathlib import Path

        ds = build_dataset(demo_raw(30), "demo")
        self.assertTrue(ds["activities"] and len(ds["sleep"]) == 30)
        with tempfile.TemporaryDirectory() as d:
            html = render(ds, Path(d) / "x.html").read_text()
        self.assertNotIn("/*__DATA__*/null", html)


if __name__ == "__main__":
    unittest.main()
