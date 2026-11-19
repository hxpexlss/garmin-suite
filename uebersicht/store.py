"""SQLite-Speicher für normalisierte Trainings- und Schlafdaten."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .normalize import merge_hrv, normalize_activities, normalize_hrv, normalize_sleep

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (id TEXT PRIMARY KEY, date TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS activities_date ON activities(date);
CREATE TABLE IF NOT EXISTS sleep (date TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS raw (kind TEXT NOT NULL, fetched_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
RAW_KEEP = 30  # so viele Rohantworten je Art aufbewahren (zur Fehlersuche)


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.execute("PRAGMA journal_mode=WAL")

    # --- Meta -------------------------------------------------------------------
    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_meta(self, key: str, value: Any) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, json.dumps(value)))

    # --- Import -----------------------------------------------------------------
    def ingest(self, raw: dict[str, list[Any]]) -> dict[str, int]:
        """Rohantworten normalisieren und zusammenführen. Vorhandene Werte bleiben,
        wenn eine neue Antwort für ein Feld nichts liefert."""
        acts = normalize_activities(raw.get("activities", []))
        nights = merge_hrv(normalize_sleep(raw.get("sleep", [])), normalize_hrv(raw.get("hrv", [])))
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock, self._db:
            for a in acts:
                self._db.execute("INSERT OR REPLACE INTO activities(id, date, data) VALUES (?, ?, ?)",
                                 (str(a["id"]), a["date"], json.dumps(a, ensure_ascii=False)))
            for n in nights:
                row = self._db.execute("SELECT data FROM sleep WHERE date=?", (n["date"],)).fetchone()
                merged = json.loads(row["data"]) if row else {}
                merged.update({k: v for k, v in n.items() if v is not None})
                self._db.execute("INSERT OR REPLACE INTO sleep(date, data) VALUES (?, ?)",
                                 (n["date"], json.dumps(merged, ensure_ascii=False)))
            for kind, payloads in raw.items():
                if payloads:
                    self._db.execute("INSERT INTO raw(kind, fetched_at, payload) VALUES (?, ?, ?)",
                                     (kind, now, json.dumps(payloads, ensure_ascii=False)))
                    self._db.execute(
                        "DELETE FROM raw WHERE kind=? AND rowid NOT IN "
                        "(SELECT rowid FROM raw WHERE kind=? ORDER BY rowid DESC LIMIT ?)", (kind, kind, RAW_KEEP))
        return {"activities": len(acts), "nights": len(nights)}

    # --- Abfragen ---------------------------------------------------------------
    def activities(self, since: str | None = None, until: str | None = None) -> list[dict]:
        q, args = "SELECT data FROM activities WHERE 1=1", []
        if since:
            q += " AND date>=?"; args.append(since)
        if until:
            q += " AND date<=?"; args.append(until)
        with self._lock:
            rows = self._db.execute(q, args).fetchall()
        acts = [json.loads(r["data"]) for r in rows]
        acts.sort(key=lambda a: (a.get("date") or "", a.get("time") or ""), reverse=True)
        return acts

    def sleep(self, since: str | None = None, until: str | None = None) -> list[dict]:
        q, args = "SELECT data FROM sleep WHERE 1=1", []
        if since:
            q += " AND date>=?"; args.append(since)
        if until:
            q += " AND date<=?"; args.append(until)
        with self._lock:
            rows = self._db.execute(q + " ORDER BY date", args).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def counts(self) -> dict[str, Any]:
        with self._lock:
            a = self._db.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM activities").fetchone()
            s = self._db.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM sleep").fetchone()
        return {"activities": a[0], "activitiesFrom": a[1], "activitiesTo": a[2],
                "nights": s[0], "nightsFrom": s[1], "nightsTo": s[2]}

    def close(self) -> None:
        with self._lock:
            self._db.close()
