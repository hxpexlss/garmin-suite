#!/usr/bin/env bash
# Installiert den Garmin-Übersicht-Server als systemd-Dienst.
# Aufruf aus dem Repository-Ordner:  sudo ./deploy/install.sh
set -euo pipefail

APP_DIR=/opt/garmin-uebersicht
CONF_DIR=/etc/garmin-uebersicht
DATA_DIR=/var/lib/garmin-uebersicht
USER_NAME=garmin-uebersicht
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "Bitte mit sudo ausführen." >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 fehlt (mind. 3.12)." >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' \
  || { echo "Python 3.12 oder neuer nötig (gefunden: $(python3 -V))." >&2; exit 1; }
python3 -c 'import venv, ensurepip' 2>/dev/null \
  || { echo "python3-venv fehlt. Debian/Ubuntu: apt install python3-venv" >&2; exit 1; }

id "$USER_NAME" >/dev/null 2>&1 || useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$USER_NAME"

install -d -m 755 "$APP_DIR"
cp -r "$SRC_DIR/uebersicht" "$SRC_DIR/requirements.txt" "$APP_DIR/"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

install -d -m 750 -o root -g "$USER_NAME" "$CONF_DIR"
install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "$DATA_DIR"
[ -f "$CONF_DIR/config.toml" ] || install -m 640 -o root -g "$USER_NAME" "$SRC_DIR/deploy/config.example.toml" "$CONF_DIR/config.toml"
if [ ! -f "$CONF_DIR/app-token" ]; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$CONF_DIR/app-token"
  chown root:"$USER_NAME" "$CONF_DIR/app-token"; chmod 640 "$CONF_DIR/app-token"
fi

if [ ! -s "$CONF_DIR/api-key" ]; then
  echo
  echo "Garmin Personal-API-Schlüssel (erstellen unter connect.garmin.com/app/settings/personalApiToken)."
  read -r -s -p "Schlüssel einfügen (Eingabe bleibt unsichtbar, leer = später): " KEY; echo
  if [ -n "$KEY" ]; then
    printf '%s' "$KEY" > "$CONF_DIR/api-key"
    chown root:"$USER_NAME" "$CONF_DIR/api-key"; chmod 640 "$CONF_DIR/api-key"
  fi
fi

install -m 644 "$SRC_DIR/deploy/garmin-uebersicht.service" /etc/systemd/system/garmin-uebersicht.service
systemctl daemon-reload
systemctl enable --now garmin-uebersicht.service
sleep 2
systemctl --no-pager --lines=5 status garmin-uebersicht.service || true

echo
echo "Fertig. Nächste Schritte:"
[ -s "$CONF_DIR/api-key" ] || echo "  • API-Schlüssel in $CONF_DIR/api-key ablegen, dann: systemctl restart garmin-uebersicht"
echo "  • Über Tailscale freigeben:  tailscale serve --bg 8765"
echo "    (danach erreichbar unter https://<servername>.<tailnet>.ts.net)"
echo "  • App-Token für die Android-App:  sudo cat $CONF_DIR/app-token"
echo "  • Log ansehen:  journalctl -u garmin-uebersicht -f"
