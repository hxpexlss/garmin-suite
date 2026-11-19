"""Garmin-Übersicht: Trainings und Schlaf als HTML-Seite.

    python -m uebersicht demo                 # Beispieldaten, kein Schlüssel nötig
    python -m uebersicht abrufen --tage 90    # echte Daten über die Personal API
    python -m uebersicht bauen                # Seite aus gespeicherten Rohdaten neu bauen
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .normalize import merge_hrv, normalize_activities, normalize_hrv, normalize_sleep

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template.html"
DEFAULT_RAW = Path("daten/roh")
DEFAULT_OUT = Path("ausgabe/uebersicht.html")


def build_dataset(raw: dict, source: str) -> dict:
    sleep = merge_hrv(normalize_sleep(raw.get("sleep", [])), normalize_hrv(raw.get("hrv", [])))
    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": source,
        "activities": normalize_activities(raw.get("activities", [])),
        "sleep": sleep,
    }


def render(dataset: dict, out: Path) -> Path:
    payload = json.dumps(dataset, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def load_raw(raw_dir: Path) -> dict:
    raw = {}
    for name in ("activities", "sleep", "hrv"):
        f = raw_dir / f"{name}.json"
        raw[name] = json.loads(f.read_text()) if f.exists() else []
    return raw


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m uebersicht", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-o", "--ausgabe", type=Path, default=DEFAULT_OUT, help="Ziel der HTML-Datei")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="Übersicht mit Beispieldaten erzeugen")
    d.add_argument("--tage", type=int, default=120)
    a = sub.add_parser("abrufen", help="Daten von Garmin holen und Übersicht erzeugen")
    a.add_argument("--tage", type=int, default=90, help="Zeitraum in Tagen (Standard 90)")
    a.add_argument("--schluessel-datei", help="Datei mit dem Personal-API-Schlüssel")
    a.add_argument("--roh", type=Path, default=DEFAULT_RAW, help="Ordner für Rohdaten")
    b = sub.add_parser("bauen", help="Übersicht aus gespeicherten Rohdaten erzeugen")
    b.add_argument("--roh", type=Path, default=DEFAULT_RAW)
    s = sub.add_parser("server", help="Headless-Server mit regelmäßigem Abruf und HTTP-API")
    s.add_argument("--config", help="Pfad zur config.toml")
    s.add_argument("--demo", action="store_true", help="Beispieldaten statt Garmin verwenden")
    s.add_argument("--host", help="Adresse überschreiben (z. B. 0.0.0.0 zum Testen)")
    s.add_argument("--port", type=int)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
                        if args.cmd == "server" else "%(message)s")

    if args.cmd == "server":
        from .server import Config, serve

        cfg = Config.load(args.config)
        cfg.demo = cfg.demo or args.demo
        cfg.host = args.host or cfg.host
        cfg.port = args.port or cfg.port
        serve(cfg)
        return 0

    if args.cmd == "demo":
        from .demo import demo_raw

        raw, source = demo_raw(args.tage), "demo"
    elif args.cmd == "abrufen":
        from .fetch import fetch_all

        raw, source = fetch_all(args.tage, args.roh, args.schluessel_datei), "garmin"
    else:
        raw, source = load_raw(args.roh), "garmin"

    dataset = build_dataset(raw, source)
    out = render(dataset, args.ausgabe)
    print(f"{len(dataset['activities'])} Trainings, {len(dataset['sleep'])} Nächte → {out}")
    if not dataset["activities"] and not dataset["sleep"]:
        print("Hinweis: Keine Daten erkannt. Prüfe die Rohdaten im Ordner daten/roh.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
