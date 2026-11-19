"""Holt Trainings- und Schlafdaten über die offizielle Garmin Personal API."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterator

log = logging.getLogger(__name__)

ACTIVITY_PAGE_SIZE = 100
RANGE_CHUNK_DAYS = 28  # Zeiträume in Stücken abfragen, falls die API Bereiche begrenzt


def _chunks(start: date, end: date, days: int):
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=days - 1), end)
        yield cur, stop
        cur = stop + timedelta(days=1)


def _safe(label: str, fn: Callable[[], Any]) -> Any:
    """Einzelne fehlgeschlagene Abfragen protokollieren statt alles abzubrechen."""
    try:
        return fn()
    except Exception as err:  # noqa: BLE001 – HttpError des Garmin-Clients und Netzwerkfehler
        status = getattr(err, "status_code", None)
        if status == 401:
            raise
        log.warning("%s fehlgeschlagen: %s %s", label, status or type(err).__name__,
                    str(getattr(err, "response_text", err))[:200])
        return None


@contextmanager
def garmin_client(api_key_file: str | None = None, token_cache_file: str | None = None) -> Iterator[Any]:
    """Authentifizierter Client des offiziellen Pakets ``garmin-connect-personal-api-python``."""
    from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator, resolve_api_key

    kwargs = {"bearer_token_cache_file": token_cache_file} if token_cache_file else {}
    with PersonalApiAuthenticator(**kwargs) as auth:
        key = resolve_api_key(key_file=api_key_file) if api_key_file else resolve_api_key()
        token = auth.obtain_token(key)
    with GarminPersonalApiClient(token.access_token) as client:
        yield client


def fetch_range(client: Any, start: date, end: date) -> dict[str, list[Any]]:
    """Rohdaten für Trainings, Schlaf und HRV im Zeitraum ``start``–``end``."""
    from .normalize import normalize_sleep

    raw: dict[str, list[Any]] = {"activities": [], "sleep": [], "hrv": []}

    # Trainings: seitenweise, bis eine Seite nicht mehr voll ist.
    offset = 0
    while True:
        page = client.search_activities(start=offset, limit=ACTIVITY_PAGE_SIZE, start_date=start, end_date=end)
        items = page if isinstance(page, list) else (page or {}).get("activities", [])
        raw["activities"].extend(items)
        if len(items) < ACTIVITY_PAGE_SIZE:
            break
        offset += ACTIVITY_PAGE_SIZE
    log.info("Trainings %s–%s: %d", start, end, len(raw["activities"]))

    for a, b in _chunks(start, end, RANGE_CHUNK_DAYS):
        s = _safe(f"Schlaf {a}–{b}", lambda: client.get_daily_sleep_summaries(a, b))
        if s is not None:
            raw["sleep"].append(s)
        h = _safe(f"HRV {a}–{b}", lambda: client.get_daily_hrv_summaries(a, b))
        if h is not None:
            raw["hrv"].append(h)

    # Liefern die Zusammenfassungen keine Schlafphasen, Nacht für Nacht nachladen.
    if not any(n.get("deepS") is not None for n in normalize_sleep(raw["sleep"])):
        log.info("Keine Schlafphasen in den Zusammenfassungen – lade Nächte einzeln")
        day = start
        while day <= end:
            d = _safe(f"Schlaf {day}", lambda: client.get_daily_sleep(day))
            if d is not None:
                raw["sleep"].append(d)
            day += timedelta(days=1)
    return raw


def fetch_all(days: int, raw_dir: Path, api_key_file: str | None = None) -> dict[str, list[Any]]:
    """Lädt die Rohdaten der letzten ``days`` Tage und speichert sie in ``raw_dir``."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    with garmin_client(api_key_file) as client:
        raw = fetch_range(client, start, end)
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in raw.items():
        (raw_dir / f"{name}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    log.info("Rohdaten gespeichert in %s", raw_dir)
    return raw
