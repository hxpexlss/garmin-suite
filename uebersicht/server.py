"""Headless-Server: holt mehrmals täglich Garmin-Daten und stellt sie per HTTP-API bereit.

Nur Python-Standardbibliothek plus der offizielle Garmin-Client. Gedacht für den
Betrieb hinter Tailscale (``tailscale serve``) oder gebunden an die Tailscale-IP.
"""

from __future__ import annotations

import hmac
import json
import logging
import threading
import time
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from . import coach, stats
from .store import Store

log = logging.getLogger("uebersicht.server")
VERSION = "1.0.0"


# --- Konfiguration ---------------------------------------------------------------

@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = ""
    data_dir: str = "./daten"
    api_key_file: str = ""
    sync_times: list[str] = field(default_factory=lambda: ["06:30", "09:30", "13:00", "18:00", "22:30"])
    backfill_days: int = 365
    refresh_days: int = 3
    max_hr: int = 0
    resting_hr: int = 0
    demo: bool = False

    @classmethod
    def load(cls, path: str | None) -> "Config":
        cfg = cls()
        if not path:
            return cfg
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        s, g, sy, c, st = (data.get(k, {}) for k in ("server", "garmin", "sync", "coach", "storage"))
        cfg.host = s.get("host", cfg.host)
        cfg.port = int(s.get("port", cfg.port))
        cfg.token = s.get("token", cfg.token)
        token_file = s.get("token_file")
        if token_file:
            try:
                cfg.token = Path(token_file).read_text().strip()
            except OSError as err:
                raise SystemExit(f"token_file {token_file} nicht lesbar: {err}") from err
            if not cfg.token:
                raise SystemExit(f"token_file {token_file} ist leer")
        cfg.api_key_file = g.get("api_key_file", cfg.api_key_file)
        cfg.sync_times = list(sy.get("times", cfg.sync_times))
        cfg.backfill_days = int(sy.get("backfill_days", cfg.backfill_days))
        cfg.refresh_days = int(sy.get("refresh_days", cfg.refresh_days))
        cfg.max_hr = int(c.get("max_hr", cfg.max_hr))
        cfg.resting_hr = int(c.get("resting_hr", cfg.resting_hr))
        cfg.data_dir = st.get("data_dir", cfg.data_dir)
        cfg.demo = bool(data.get("demo", cfg.demo))
        for t in cfg.sync_times:
            datetime.strptime(t, "%H:%M")  # früh mit klarer Meldung scheitern
        return cfg


# --- Abgleich mit Garmin -----------------------------------------------------------

Fetcher = Callable[[date, date], dict]


def garmin_fetcher(cfg: Config) -> Fetcher:
    from .fetch import fetch_range, garmin_client

    cache = str(Path(cfg.data_dir) / "bearer-token.json")

    def fetch(start: date, end: date) -> dict:
        with garmin_client(cfg.api_key_file or None, cache) as client:
            return fetch_range(client, start, end)
    return fetch


def demo_fetcher() -> Fetcher:
    from .demo import demo_raw

    def fetch(start: date, end: date) -> dict:
        return demo_raw((date.today() - start).days + 1)
    return fetch


def next_run(times: list[str], now: datetime) -> datetime:
    slots = sorted(datetime.combine(now.date(), datetime.strptime(t, "%H:%M").time()) for t in times)
    for s in slots:
        if s > now:
            return s
    return slots[0] + timedelta(days=1)


class SyncService:
    BACKFILL_CHUNK = 90

    def __init__(self, store: Store, cfg: Config, fetcher: Fetcher):
        self.store, self.cfg, self.fetcher = store, cfg, fetcher
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._running = threading.Lock()
        self.next_at: datetime | None = None

    @property
    def busy(self) -> bool:
        return self._running.locked()

    def run_once(self) -> dict:
        if not self._running.acquire(blocking=False):
            return {"started": False, "reason": "Abgleich läuft bereits"}
        started = datetime.now()
        try:
            today = date.today()
            if not self.store.get_meta("backfill_done"):
                start = today - timedelta(days=self.cfg.backfill_days - 1)
                log.info("Erster Abgleich: lade %d Tage", self.cfg.backfill_days)
            else:
                start = today - timedelta(days=self.cfg.refresh_days - 1)
            totals = {"activities": 0, "nights": 0}
            cur = start
            while cur <= today:  # in Blöcken, damit ein Fehler nicht alles verwirft
                stop = min(cur + timedelta(days=self.BACKFILL_CHUNK - 1), today)
                got = self.store.ingest(self.fetcher(cur, stop))
                totals = {k: totals[k] + got[k] for k in totals}
                cur = stop + timedelta(days=1)
            self.store.set_meta("backfill_done", True)
            result = {"ok": True, "at": started.isoformat(timespec="seconds"), "from": start.isoformat(),
                      "seconds": round((datetime.now() - started).total_seconds(), 1), **totals}
            self.store.set_meta("last_sync", result)
            self.store.set_meta("last_error", None)
            log.info("Abgleich fertig: %s", result)
            return {"started": True, **result}
        except Exception as err:  # noqa: BLE001
            status = getattr(err, "status_code", None)
            msg = ("Garmin lehnt den API-Schlüssel ab (401). Neuen Schlüssel erstellen und Datei ersetzen."
                   if status == 401 else f"{type(err).__name__}: {err}")
            self.store.set_meta("last_error", {"at": started.isoformat(timespec="seconds"), "message": msg[:500]})
            log.exception("Abgleich fehlgeschlagen")
            return {"started": True, "ok": False, "error": msg}
        finally:
            self._running.release()

    def trigger(self) -> None:
        self._wake.set()

    def loop(self) -> None:
        last = self.store.get_meta("last_sync") or {}
        stale = not last or datetime.fromisoformat(last["at"]) < datetime.now() - timedelta(hours=6)
        if stale:
            self.run_once()
        while not self._stop.is_set():
            self.next_at = next_run(self.cfg.sync_times, datetime.now())
            wait = max(1.0, (self.next_at - datetime.now()).total_seconds())
            self._wake.wait(timeout=min(wait, 300))  # alle 5 min neu planen (Uhrzeitsprünge, Ruhezustand)
            if self._stop.is_set():
                break
            if self._wake.is_set() or datetime.now() >= self.next_at:
                self._wake.clear()
                self.run_once()

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self.loop, name="sync", daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set(); self._wake.set()


# --- HTTP ------------------------------------------------------------------------

def _period(q: dict, default_days: int = 30) -> tuple[date, date]:
    end = date.today()
    try:
        days = int(q.get("days", [default_days])[0])
    except ValueError:
        days = default_days
    days = max(1, min(days, 3660))
    return end - timedelta(days=days - 1), end


class App:
    def __init__(self, store: Store, cfg: Config, sync: SyncService):
        self.store, self.cfg, self.sync = store, cfg, sync

    def status(self, q: dict) -> dict:
        return {"version": VERSION, "demo": self.cfg.demo, "syncing": self.sync.busy,
                "lastSync": self.store.get_meta("last_sync"), "lastError": self.store.get_meta("last_error"),
                "nextSync": self.sync.next_at.isoformat(timespec="minutes") if self.sync.next_at else None,
                "syncTimes": self.cfg.sync_times, "data": self.store.counts()}

    def overview(self, q: dict) -> dict:
        start, end = _period(q)
        return stats.overview(self.store.activities(start.isoformat()), self.store.sleep(start.isoformat()), start, end)

    def activities(self, q: dict) -> dict:
        start, end = _period(q, 90)
        return {"start": start.isoformat(), "end": end.isoformat(), "activities": self.store.activities(start.isoformat())}

    def sleep(self, q: dict) -> dict:
        start, end = _period(q, 30)
        return {"start": start.isoformat(), "end": end.isoformat(), "nights": self.store.sleep(start.isoformat())}

    def coach(self, q: dict) -> dict:
        since = (date.today() - timedelta(days=200)).isoformat()
        return coach.suggest(self.store.activities(since), self.store.sleep(since),
                             max_hr=self.cfg.max_hr or None, resting_hr=self.cfg.resting_hr or None)

    def dashboard_html(self) -> str:
        from .__main__ import TEMPLATE

        since = (date.today() - timedelta(days=365)).isoformat()
        ds = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "demo" if self.cfg.demo else "garmin",
              "activities": self.store.activities(since), "sleep": self.store.sleep(since)}
        payload = json.dumps(ds, ensure_ascii=False).replace("</", "<\\/")
        return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    routes: dict[str, Callable[[dict], dict]] = {
        "/api/status": app.status, "/api/overview": app.overview, "/api/activities": app.activities,
        "/api/sleep": app.sleep, "/api/coach": app.coach,
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = f"GarminUebersicht/{VERSION}"

        def log_message(self, fmt: str, *args: Any) -> None:
            log.debug("%s %s", self.address_string(), fmt % args)

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, obj: Any) -> None:
            self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _authorized(self, q: dict) -> bool:
            if not app.cfg.token:
                return True
            header = self.headers.get("Authorization", "")
            given = header[7:] if header.startswith("Bearer ") else q.get("token", [""])[0]
            return hmac.compare_digest(given.encode(), app.cfg.token.encode())

        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path == "/api/health":
                return self._json(200, {"ok": True, "version": VERSION})
            if not self._authorized(q):
                return self._json(401, {"error": "Token fehlt oder ist falsch"})
            if url.path in ("/", "/index.html"):
                return self._send(200, app.dashboard_html().encode(), "text/html; charset=utf-8")
            fn = routes.get(url.path)
            if not fn:
                return self._json(404, {"error": "Unbekannter Pfad"})
            try:
                self._json(200, fn(q))
            except Exception:  # noqa: BLE001
                log.exception("Fehler bei %s", url.path)
                self._json(500, {"error": "Interner Fehler – siehe Server-Log"})

        def do_POST(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            if not self._authorized(parse_qs(url.query)):
                return self._json(401, {"error": "Token fehlt oder ist falsch"})
            if url.path != "/api/sync":
                return self._json(404, {"error": "Unbekannter Pfad"})
            if app.sync.busy:
                return self._json(HTTPStatus.CONFLICT, {"started": False, "reason": "Abgleich läuft bereits"})
            app.sync.trigger()
            self._json(HTTPStatus.ACCEPTED, {"started": True})

    return Handler


def serve(cfg: Config) -> None:
    store = Store(Path(cfg.data_dir) / "garmin.sqlite")
    fetcher = demo_fetcher() if cfg.demo else garmin_fetcher(cfg)
    sync = SyncService(store, cfg, fetcher)
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(App(store, cfg, sync)))
    httpd.daemon_threads = True
    sync.start()
    log.info("Server läuft auf http://%s:%d (Abgleich um %s)%s", cfg.host, cfg.port,
             ", ".join(cfg.sync_times), " – DEMO-Modus" if cfg.demo else "")
    if not cfg.token:
        log.warning("Kein API-Token gesetzt – Zugriff nur über Tailscale-ACLs geschützt.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sync.stop(); httpd.server_close(); store.close()
        time.sleep(0.1)
