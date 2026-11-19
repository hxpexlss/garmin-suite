import json
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.server import ThreadingHTTPServer

from uebersicht import coach
from uebersicht.demo import demo_raw
from uebersicht.server import App, Config, SyncService, demo_fetcher, make_handler, next_run
from uebersicht.store import Store


def act(day: date, minutes=45, hr=140, te=2.5, typ="running", max_hr=175, i=0):
    return {"id": f"{day}-{i}", "date": day.isoformat(), "time": "07:00", "type": typ, "typeLabel": typ,
            "durationS": minutes * 60, "avgHr": hr, "maxHr": max_hr, "trainingEffect": te}


def night(day: date, score=80, hrv=55, total=7.5):
    return {"date": day.isoformat(), "totalS": total * 3600, "score": score, "hrv": hrv, "restingHr": 50}


class CoachTest(unittest.TestCase):
    today = date(2026, 11, 19)  # Donnerstag

    def history(self, weeks=5):
        acts = []
        for w in range(weeks):
            for off in (1, 3, 5):
                acts.append(act(self.today - timedelta(days=7 * w + off), i=off))
        nights = [night(self.today - timedelta(days=d)) for d in range(30)]
        return acts, nights

    def test_rest_when_hrv_drops(self):
        acts, nights = self.history()
        nights[0] = night(self.today, score=45, hrv=40)
        r = coach.suggest(acts, nights, self.today)
        self.assertEqual(r["today"]["kind"], "rest")
        self.assertTrue(any("HRV" in x for x in r["today"]["reasons"]))

    def test_hard_when_rested(self):
        acts, nights = self.history()
        nights[0] = night(self.today, score=90, hrv=60)
        r = coach.suggest(acts, nights, self.today)
        self.assertEqual(r["today"]["kind"], "hard")
        self.assertEqual(r["today"]["sport"], "run")
        self.assertGreaterEqual(r["readiness"]["score"], 70)

    def test_easy_after_hard_yesterday(self):
        acts, nights = self.history()
        acts.append(act(self.today - timedelta(days=1), te=4.2, hr=165, i=9))
        r = coach.suggest(acts, nights, self.today)
        self.assertEqual(r["today"]["kind"], "easy")

    def test_rest_on_load_spike(self):
        acts, nights = self.history()
        for d in range(1, 7):
            acts.append(act(self.today - timedelta(days=d), minutes=150, hr=160, i=20 + d))
        r = coach.suggest(acts, nights, self.today)
        self.assertGreater(r["metrics"]["acwr"], 1.5)
        self.assertEqual(r["today"]["kind"], "rest")

    def test_without_data(self):
        r = coach.suggest([], [], self.today)
        self.assertIn(r["today"]["kind"], {"hard", "moderate"})
        self.assertIsNone(r["metrics"]["acwr"])
        self.assertTrue(r["hints"])

    def test_long_on_weekend(self):
        acts, nights = self.history()
        saturday = self.today + timedelta(days=2)
        acts = [a for a in acts if a["date"] < (saturday - timedelta(days=6)).isoformat()]
        acts.append(act(saturday - timedelta(days=10), minutes=80, i=99))
        nights = [night(saturday - timedelta(days=d)) for d in range(30)]
        r = coach.suggest(acts, nights, saturday)
        self.assertEqual(r["today"]["kind"], "long")
        self.assertGreaterEqual(r["today"]["durationMin"][0], 80)


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store(":memory:")
        cls.cfg = Config(token="t0k", demo=True)
        cls.sync = SyncService(cls.store, cls.cfg, demo_fetcher())
        cls.sync.run_once()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(cls.store, cls.cfg, cls.sync)))
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def get(self, path, token="t0k"):
        req = urllib.request.Request(self.base + path, headers={"Authorization": f"Bearer {token}"} if token else {})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def test_auth(self):
        self.assertTrue(self.get("/api/health", token=None)["ok"])
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get("/api/status", token="falsch")
        self.assertEqual(e.exception.code, 401)

    def test_endpoints(self):
        st = self.get("/api/status")
        self.assertTrue(st["lastSync"]["ok"])
        self.assertEqual(st["data"]["nights"], 365)
        ov = self.get("/api/overview?days=28")
        self.assertEqual(len(ov["training"]["weekly"]), 5)  # 28 Tage berühren 5 Kalenderwochen
        self.assertGreater(ov["training"]["count"], 10)
        self.assertEqual(ov["sleep"]["nights"], 28)
        self.assertTrue(self.get("/api/activities?days=7")["activities"])
        self.assertEqual(len(self.get("/api/sleep?days=7")["nights"]), 7)
        self.assertIn(self.get("/api/coach")["today"]["kind"], {"rest", "easy", "moderate", "hard", "long"})

    def test_resync_does_not_duplicate(self):
        before = self.store.counts()["activities"]
        self.sync.run_once()
        self.assertEqual(self.store.counts()["activities"], before)


class StoreTest(unittest.TestCase):
    def test_merge_keeps_existing_values(self):
        s = Store(":memory:")
        s.ingest({"sleep": [{"calendarDate": "2026-11-01", "sleepTimeSeconds": 25000, "deepSleepSeconds": 4000}]})
        s.ingest({"sleep": [{"calendarDate": "2026-11-01", "sleepTimeSeconds": 25100}],
                  "hrv": [{"calendarDate": "2026-11-01", "lastNightAvg": 61}]})
        (n,) = s.sleep()
        self.assertEqual((n["totalS"], n["deepS"], n["hrv"]), (25100.0, 4000.0, 61.0))

    def test_demo_ingest(self):
        s = Store(":memory:")
        got = s.ingest(demo_raw(14))
        self.assertEqual(got["nights"], 14)


class ScheduleTest(unittest.TestCase):
    def test_next_run(self):
        from datetime import datetime
        times = ["06:30", "22:30"]
        self.assertEqual(next_run(times, datetime(2026, 11, 19, 7, 0)), datetime(2026, 11, 19, 22, 30))
        self.assertEqual(next_run(times, datetime(2026, 11, 19, 23, 0)), datetime(2026, 11, 20, 6, 30))


if __name__ == "__main__":
    unittest.main()
