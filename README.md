# Garmin-Übersicht

Eine persönliche Übersicht für **Trainings** und **Schlaf**. Die Daten kommen über die
offizielle [Garmin Connect Personal API](https://developer.garmin.com/gc-developer-program/personal/personal-api).
Heraus kommt eine einzelne HTML-Datei, die du im Browser öffnest, auch offline.

**Trainings:** Anzahl, Trainingszeit, Distanz, Ø Herzfrequenz, Stunden pro Woche,
Verteilung nach Sportart und eine Tabelle der letzten Trainings mit Tempo und Trainingseffekt.

**Schlaf:** Ø Schlafdauer, Sleep Score, HRV und Ruhepuls, Schlafphasen pro Nacht
(Tief, Leicht, REM, Wach), Verlauf von Sleep Score und HRV sowie eine Tabelle aller Nächte.

Du kannst den Zeitraum wählen (7 Tage bis alles) und zwischen hell und dunkel umschalten.

## Einrichtung

Du brauchst Python 3.12 oder neuer.

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ausprobieren ohne Garmin-Konto

```shell
python -m uebersicht demo
```

Öffne danach `ausgabe/uebersicht.html`.

## Mit deinen echten Daten

1. Erstelle einen Personal-API-Schlüssel in Garmin Connect:
   <https://connect.garmin.com/app/settings/personalApiToken>
2. Speichere ihn in der Standarddatei, die der offizielle Client liest:

   ```shell
   mkdir -p ~/.config/garmin
   printf '%s' 'DEIN-SCHLÜSSEL' > ~/.config/garmin/connect-personal-api-key
   chmod 600 ~/.config/garmin/connect-personal-api-key
   ```

   Alternativ setzt du die Umgebungsvariable `GARMIN_PERSONAL_API_KEY`.
3. Daten abrufen und die Übersicht erzeugen:

   ```shell
   python -m uebersicht abrufen --tage 90
   ```

Die Rohantworten landen in `daten/roh/`. Mit `python -m uebersicht bauen` erzeugst du die
Seite daraus neu, ohne Garmin noch einmal abzufragen. `daten/` und `ausgabe/` stehen in
`.gitignore`, damit deine Gesundheitsdaten nicht im Repository landen.

## Gut zu wissen

- Der Python-Client von Garmin dokumentiert die Endpunkte, aber nicht die Felder der
  Antworten. `uebersicht/normalize.py` liest die von Garmin Connect bekannten Feldnamen und
  akzeptiert gängige Alternativen. Fehlt etwas in der Übersicht, sieh in `daten/roh/` nach,
  wie das Feld heißt, und ergänze es dort.
- Liefert der Sammelabruf für Schlaf keine Schlafphasen, lädt das Skript jede Nacht
  einzeln nach. Bei 365 Tagen sind das 365 Abfragen.
- Der Zugriffstoken gilt 24 Stunden und wird vom offiziellen Client automatisch
  zwischengespeichert und erneuert.

## Aufbau

| Datei | Aufgabe |
| --- | --- |
| `uebersicht/fetch.py` | Abruf über `garmin-connect-personal-api-python` |
| `uebersicht/normalize.py` | Antworten in flache Datensätze umwandeln |
| `uebersicht/demo.py` | Beispieldaten |
| `uebersicht/template.html` | Die Seite selbst (SVG-Diagramme, ohne externe Bibliotheken) |
| `uebersicht/__main__.py` | Befehle `demo`, `abrufen`, `bauen` |

Tests: `python -m unittest`
