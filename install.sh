#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ "$(id -u)" -eq 0 ]]; then
  APT=(apt-get)
elif command -v sudo >/dev/null 2>&1; then
  APT=(sudo apt-get)
else
  echo "Fehler: Bitte als root ausführen oder sudo installieren." >&2
  exit 1
fi

echo "Installiere Python-Voraussetzungen …"
"${APT[@]}" update
"${APT[@]}" install -y python3-full python3-venv

if [[ ! -x ".venv/bin/python" ]]; then
  if [[ -e ".venv" ]]; then
    echo "Fehler: .venv existiert, enthält aber keine nutzbare Python-Umgebung." >&2
    echo "Bitte prüfen oder entfernen Sie .venv anschließend erneut ausführen." >&2
    exit 1
  fi
  echo "Erstelle virtuelle Python-Umgebung …"
  python3 -m venv .venv
fi

echo "Installiere EasyPrent Accounting …"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .

echo "Richte Autostart ein …"
SERVICE_FILE="/etc/systemd/system/easy-prent.service"
if [[ "$(id -u)" -eq 0 ]]; then
  install -m 0644 "$PROJECT_DIR/easy-prent.service" "$SERVICE_FILE"
  systemctl daemon-reload
  systemctl enable --now easy-prent.service
else
  sudo install -m 0644 "$PROJECT_DIR/easy-prent.service" "$SERVICE_FILE"
  sudo systemctl daemon-reload
  sudo systemctl enable --now easy-prent.service
fi

echo
echo "Installation abgeschlossen. Starten mit:"
echo "  systemctl status easy-prent.service"
echo
echo "Die Anwendung ist anschließend unter http://localhost:8020 erreichbar."
