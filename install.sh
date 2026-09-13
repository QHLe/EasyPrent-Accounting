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

rm -rf build dist *.egg-info
.venv/bin/python -m pip uninstall -y easy-rem 2>/dev/null || true

WHEEL_DIR="$(mktemp -d)"
trap 'rm -rf "$WHEEL_DIR"' EXIT
.venv/bin/python -m pip wheel --no-deps --no-build-isolation -w "$WHEEL_DIR" .
WHEEL_FILE="$(ls "$WHEEL_DIR"/easyprent_accounting-*.whl | head -n 1)"

if python3 -c '
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    bad = [n for n in z.namelist() if n.startswith("src/") or n.startswith("build/")]
    if bad:
        sys.exit(1)
' "$WHEEL_FILE"; then
  :
else
  echo "Fehler: Wheel enthält unerlaubte src/-Dateien." >&2
  exit 1
fi

.venv/bin/python -m pip install --upgrade "$WHEEL_FILE"
.venv/bin/python -c 'from importlib import resources; import odf, reportlab; assert resources.files("easyprent_accounting").joinpath("templates").joinpath("utility_settlement.ods").is_file(); print("ODS-Vorlage sowie ODS- und PDF-Abhängigkeiten verfügbar.")'

if command -v npm >/dev/null 2>&1 && [[ -f "package-lock.json" ]]; then
  echo "Prüfe und installiere Node-Abhängigkeiten via Lockfile …"
  npm ci
fi

echo "Richte Autostart ein …"
SERVICE_FILE="/etc/systemd/system/easy-prent.service"
CANONICAL_SERVICE_FILE="/etc/systemd/system/easyprent-accounting.service"
ACTUAL_USER="${SUDO_USER:-$(id -un)}"
TMP_SERVICE="$(mktemp)"
sed \
  -e "s|^User=.*|User=${ACTUAL_USER}|" \
  -e "s|^WorkingDirectory=.*|WorkingDirectory=${PROJECT_DIR}|" \
  -e "s|^ExecStart=.*|ExecStart=${PROJECT_DIR}/.venv/bin/python -m easyprent_accounting.server|" \
  "$PROJECT_DIR/easy-prent.service" > "$TMP_SERVICE"

if [[ "$(id -u)" -eq 0 ]]; then
  install -m 0644 "$TMP_SERVICE" "$SERVICE_FILE"
  ln -sf "$SERVICE_FILE" "$CANONICAL_SERVICE_FILE"
  rm -f "$TMP_SERVICE"
  systemctl daemon-reload
  systemctl enable --now easy-prent.service
else
  sudo install -m 0644 "$TMP_SERVICE" "$SERVICE_FILE"
  sudo ln -sf "$SERVICE_FILE" "$CANONICAL_SERVICE_FILE"
  rm -f "$TMP_SERVICE"
  sudo systemctl daemon-reload
  sudo systemctl enable --now easy-prent.service
fi

echo
echo "Installation abgeschlossen. Starten mit:"
echo "  systemctl status easy-prent.service"
echo
echo "Die Anwendung ist anschließend unter http://localhost:8020 erreichbar."
