#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
PROJECT_OWNER="$(stat -c '%U' "$PROJECT_DIR")"
PROJECT_OWNER_UID="$(stat -c '%u' "$PROJECT_DIR")"
if [[ "$PROJECT_OWNER" == "UNKNOWN" ]]; then
  echo "Fehler: Der Checkout-Eigentümer besitzt kein Unix-Benutzerkonto." >&2
  exit 1
fi
if [[ "$(id -u)" -ne 0 && "$(id -u)" != "$PROJECT_OWNER_UID" ]]; then
  echo "Fehler: Installation muss vom Checkout-Eigentümer oder root gestartet werden." >&2
  exit 1
fi
OWNER_COMMAND=()
if [[ "$(id -u)" -eq 0 && "$PROJECT_OWNER_UID" -ne 0 ]]; then
  if ! command -v runuser >/dev/null 2>&1; then
    echo "Fehler: runuser ist für den benutzereigenen Checkout erforderlich." >&2
    exit 1
  fi
  OWNER_COMMAND=(runuser -u "$PROJECT_OWNER" --)
fi

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
  "${OWNER_COMMAND[@]}" python3 -m venv "$PROJECT_DIR/.venv"
fi
if [[ "$(stat -c '%u' "$PROJECT_DIR/.venv")" != "$PROJECT_OWNER_UID" ]]; then
  echo "Fehler: .venv gehört nicht dem Checkout-Eigentümer; bitte Eigentum prüfen." >&2
  exit 1
fi

ACTUAL_USER="$PROJECT_OWNER"
if [[ "$(id -u)" -eq 0 ]]; then
  "$PROJECT_DIR/.venv/bin/python" -m easyprent_accounting.deployment validate \
    --project-root "$PROJECT_DIR" --runtime-user "$ACTUAL_USER"
else
  sudo "$PROJECT_DIR/.venv/bin/python" -m easyprent_accounting.deployment validate \
    --project-root "$PROJECT_DIR" --runtime-user "$ACTUAL_USER"
fi

echo "Installiere EasyPrent Accounting …"
"${OWNER_COMMAND[@]}" "$PROJECT_DIR/.venv/bin/python" -m easyprent_accounting.packaging preflight-install
"${OWNER_COMMAND[@]}" "$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip
"${OWNER_COMMAND[@]}" "$PROJECT_DIR/.venv/bin/python" -m easyprent_accounting.packaging install "$PROJECT_DIR"
"${OWNER_COMMAND[@]}" "$PROJECT_DIR/.venv/bin/python" -c 'from importlib import resources; import odf, reportlab; assert resources.files("easyprent_accounting").joinpath("templates").joinpath("utility_settlement.ods").is_file(); print("ODS-Vorlage sowie ODS- und PDF-Abhängigkeiten verfügbar.")'

echo "Richte Autostart ein …"
DEPLOY_COMMAND=(
  "$PROJECT_DIR/.venv/bin/python"
  -m easyprent_accounting.deployment install
  --project-root "$PROJECT_DIR"
  --runtime-user "$ACTUAL_USER"
)

if [[ "$(id -u)" -eq 0 ]]; then
  "${DEPLOY_COMMAND[@]}"
else
  sudo "${DEPLOY_COMMAND[@]}"
fi

"${OWNER_COMMAND[@]}" "$PROJECT_DIR/.venv/bin/python" -m easyprent_accounting.packaging retire-legacy

echo
echo "Installation abgeschlossen. Starten mit:"
echo "  systemctl status easyprent-accounting.service"
echo
echo "Die Anwendung ist anschließend unter http://localhost:8020 erreichbar."
