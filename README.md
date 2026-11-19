# Garmin-Übersicht

Deine Garmin-Daten zu **Trainings** und **Schlaf**, abgeholt über die offizielle
[Garmin Connect Personal API](https://developer.garmin.com/gc-developer-program/personal/personal-api).

Das Projekt besteht aus drei Teilen:

| Teil | Wozu |
| --- | --- |
| **Server** (`uebersicht/`, `deploy/`) | Läuft headless auf einem Linux-Server, holt mehrmals täglich die Daten bei Garmin, speichert sie in SQLite, erstellt Trainingsvorschläge und stellt alles per HTTP-API bereit. |
| **Android-App** (`android/`) | Fragt den Server über Tailscale ab: Vorschlag für heute, Trainings, Schlaf. |
| **HTML-Übersicht** | Dieselben Diagramme im Browser – vom Server unter `/` ausgeliefert oder einmalig als Datei erzeugt. |

```
Garmin Personal API ──(mehrmals täglich)──▶ Server (127.0.0.1:8765)
                                              │  tailscale serve (HTTPS)
                                              ▼
                              Tailnet ───▶ Android-App / Browser
```

## Server einrichten

Voraussetzungen: Linux mit systemd, Python 3.12 oder neuer mit `python3-venv`, Tailscale.

```shell
git clone <dieses Repository> && cd <Ordner>
sudo ./deploy/install.sh
```

Das Skript
- legt den Systembenutzer `garmin-uebersicht` an,
- installiert den Server nach `/opt/garmin-uebersicht` (mit eigener Python-Umgebung),
- legt die Konfiguration unter `/etc/garmin-uebersicht/` an,
- erzeugt ein zufälliges App-Token (`/etc/garmin-uebersicht/app-token`),
- fragt nach deinem Garmin Personal-API-Schlüssel
  ([hier erstellen](https://connect.garmin.com/app/settings/personalApiToken)),
- richtet den systemd-Dienst `garmin-uebersicht` ein und startet ihn.

Beim ersten Start lädt der Server die letzten 365 Tage. Danach holt er zu festen Uhrzeiten
(Standard 06:30, 09:30, 13:00, 18:00, 22:30) die letzten drei Tage neu. Das fängt auch
Nachträge und spät synchronisierte Schlafdaten auf.

### Über Tailscale erreichbar machen

**Empfohlen:** Der Server lauscht nur auf `127.0.0.1`, und Tailscale stellt ihn per HTTPS
im Tailnet bereit:

```shell
sudo tailscale serve --bg 8765
tailscale serve status        # zeigt die Adresse, z. B. https://server.tailnet-xyz.ts.net
```

Dafür müssen in der Tailscale-Admin-Konsole MagicDNS und HTTPS-Zertifikate aktiviert sein.
Nicht verwechseln mit `tailscale funnel`: Funnel würde den Dienst öffentlich ins Internet stellen.

**Alternative:** In `/etc/garmin-uebersicht/config.toml` als `host` die Tailscale-IP
(`tailscale ip -4`) eintragen. Die App nutzt dann `http://100.x.y.z:8765`. Der Verkehr läuft
trotzdem verschlüsselt durch den WireGuard-Tunnel von Tailscale.

Mit Tailscale-ACLs kannst du zusätzlich festlegen, dass nur dein Handy den Server erreicht.

### Betrieb

```shell
journalctl -u garmin-uebersicht -f          # Log
sudo systemctl restart garmin-uebersicht    # nach Änderungen an der Konfiguration
sudo ./deploy/install.sh                    # Update nach git pull (Konfiguration bleibt erhalten)
```

In der Konfiguration kannst du die Abrufzeiten, Maximal- und Ruhepuls (für genauere
Pulszonen) und den Zeitraum für den ersten Abruf einstellen. Siehe `deploy/config.example.toml`.

### API

Alle Pfade unter `/api/` außer `/api/health` brauchen den Header `Authorization: Bearer <App-Token>`.

| Methode | Pfad | Inhalt |
| --- | --- | --- |
| GET | `/api/health` | Lebenszeichen |
| GET | `/api/status` | letzter und nächster Abgleich, letzter Fehler, Datenumfang |
| GET | `/api/overview?days=30` | Kennzahlen, Stunden pro Woche, Sportarten, Schlafschnitte |
| GET | `/api/activities?days=90` | Trainings |
| GET | `/api/sleep?days=30` | Nächte mit Phasen, Score, HRV, Ruhepuls |
| GET | `/api/coach` | Bereitschaft und Trainingsvorschlag für heute |
| POST | `/api/sync` | Abgleich mit Garmin sofort starten |
| GET | `/?token=…` | HTML-Übersicht im Browser |

## Trainingsvorschläge

Die Vorschläge folgen einfachen, nachvollziehbaren Regeln. Jeder Vorschlag nennt seine Gründe.

- **Belastung:** Garmins Training Load je Einheit, sonst ein TRIMP-Wert aus Dauer und
  Herzfrequenzreserve. Die letzten 7 Tage werden mit dem Wochenschnitt der letzten 28 Tage
  verglichen (ACWR). 0,8–1,3 gilt als günstig, über 1,5 als Überlastungsrisiko.
- **Erholung:** HRV der letzten Nacht im Vergleich zum eigenen 28-Tage-Schnitt, dazu Sleep
  Score bzw. Schlafdauer.
- **Daraus ergibt sich** eine Bereitschaft von 0–100 und eine Einheit für heute:
  Ruhetag, locker, moderat, intensiv (Intervalle/Tempo) oder lang (am Wochenende).
  Die Einheit passt zu deiner häufigsten Ausdauersportart (Laufen, Rad, Schwimmen),
  inklusive Pulsbereichen.
- **Dazu:** Wochenumfang im Vergleich zu den Vorwochen und Hinweise, etwa auf fehlendes
  Krafttraining.

Die Vorschläge ersetzen keinen Trainer und keinen Arzt. Bei Krankheit oder Schmerzen gilt
das Körpergefühl.

## Android-App

Die APK baut GitHub Actions bei jedem Push (Workflow **Build**, Artefakt
`garmin-uebersicht-apk`). Herunterladen, auf dem Handy installieren (Installation aus
unbekannten Quellen erlauben), dann in der App unter **Einstellungen** eintragen:

- **Server-Adresse:** `https://<server>.<tailnet>.ts.net` bzw. `http://100.x.y.z:8765`
- **App-Token:** Inhalt von `/etc/garmin-uebersicht/app-token`

Auf dem Handy muss die Tailscale-App verbunden sein.

Die App hat vier Bereiche:
- **Heute:** Bereitschaft, Vorschlag mit Begründung, Woche, Hinweise, Pulszonen
- **Training:** Kennzahlen, Stunden pro Woche, Sportarten, Liste der Trainings
- **Schlaf:** Kennzahlen, Schlafphasen, Sleep Score, HRV, Liste der Nächte
- **Einstellungen**

Über das Sync-Symbol oben stößt du einen Abgleich mit Garmin sofort an.

Selbst bauen: Android Studio oder `cd android && ./gradlew assembleRelease` (Android SDK nötig).
Ohne eigenen Signaturschlüssel wird die Release-APK mit dem Debug-Schlüssel signiert. Für
einen eigenen Schlüssel die Umgebungsvariablen `APK_KEYSTORE_FILE`, `APK_KEYSTORE_PASSWORD`,
`APK_KEY_ALIAS` und `APK_KEY_PASSWORD` setzen.

## Ohne Server ausprobieren

```shell
python3 -m uebersicht demo                         # HTML-Übersicht mit Beispieldaten → ausgabe/
python3 -m uebersicht server --demo --port 8765    # Server mit Beispieldaten
```

Einmalig echte Daten als HTML-Datei (ohne Server):

```shell
pip install -r requirements.txt
python -m uebersicht abrufen --tage 90
```

## Gut zu wissen

- Der Python-Client von Garmin dokumentiert die Endpunkte, aber nicht die Felder der
  Antworten. `uebersicht/normalize.py` liest die von Garmin Connect bekannten Feldnamen und
  akzeptiert gängige Alternativen. Die letzten Rohantworten liegen in der Tabelle `raw` der
  Datenbank (`/var/lib/garmin-uebersicht/garmin.sqlite`). Bleibt in der App etwas leer,
  sieh dort nach, wie das Feld heißt.
- Liefert der Sammelabruf für Schlaf keine Schlafphasen, lädt der Server jede Nacht einzeln
  nach. Beim ersten Abruf von 365 Tagen sind das 365 Abfragen.
- Tests: `python3 -m unittest`

## Aufbau

| Datei | Aufgabe |
| --- | --- |
| `uebersicht/fetch.py` | Abruf über `garmin-connect-personal-api-python` |
| `uebersicht/normalize.py` | Antworten in flache Datensätze umwandeln |
| `uebersicht/store.py` | SQLite-Speicher |
| `uebersicht/stats.py` | Kennzahlen für einen Zeitraum |
| `uebersicht/coach.py` | Bereitschaft und Trainingsvorschläge |
| `uebersicht/server.py` | Zeitgesteuerter Abgleich und HTTP-API |
| `uebersicht/template.html` | HTML-Übersicht (SVG-Diagramme, ohne externe Bibliotheken) |
| `deploy/` | systemd-Dienst, Installationsskript, Beispielkonfiguration |
| `android/` | Android-App (Kotlin, Jetpack Compose) |
