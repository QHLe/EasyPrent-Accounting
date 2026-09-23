#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi
if [[ "$#" -ne 0 ]]; then
  echo "Usage: $0 [--dry-run]" >&2
  exit 2
fi

PROJECT_OWNER="$(stat -c '%U' "$PROJECT_DIR")"
PROJECT_OWNER_UID="$(stat -c '%u' "$PROJECT_DIR")"
if [[ "$PROJECT_OWNER" == "UNKNOWN" || "$PROJECT_OWNER_UID" -eq 0 ]]; then
  echo "Fehler: Der Installationspfad muss einem nicht privilegierten Unix-Benutzer gehören." >&2
  exit 1
fi
if [[ "$(id -u)" -ne 0 && "$(id -u)" != "$PROJECT_OWNER_UID" ]]; then
  echo "Fehler: Installation muss vom Installationspfad-Eigentümer oder root gestartet werden." >&2
  exit 1
fi

OWNER_COMMAND=()
if [[ "$(id -u)" -eq 0 ]]; then
  if ! command -v runuser >/dev/null 2>&1; then
    echo "Fehler: runuser ist für die Installation als $PROJECT_OWNER erforderlich." >&2
    exit 1
  fi
  OWNER_COMMAND=(runuser -u "$PROJECT_OWNER" --)
fi

for executable in python3 npm; do
  if ! command -v "$executable" >/dev/null 2>&1; then
    echo "Fehler: $executable ist zum Bauen des Installationspakets erforderlich." >&2
    exit 1
  fi
done

VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
CREATED_DRY_RUN_VENV=0
cleanup() {
  if [[ "$CREATED_DRY_RUN_VENV" -eq 1 ]]; then
    rm -rf -- "$PROJECT_DIR/.venv"
  fi
}
trap cleanup EXIT

if [[ ! -x "$VENV_PYTHON" ]]; then
  if [[ -e "$PROJECT_DIR/.venv" ]]; then
    echo "Fehler: .venv existiert, enthält aber keine nutzbare Python-Umgebung." >&2
    exit 1
  fi
  echo "Erstelle virtuelle Python-Umgebung …"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    CREATED_DRY_RUN_VENV=1
  fi
  "${OWNER_COMMAND[@]}" python3 -m venv "$PROJECT_DIR/.venv"
fi
if [[ "$(stat -c '%u' "$PROJECT_DIR/.venv")" != "$PROJECT_OWNER_UID" ]]; then
  echo "Fehler: .venv gehört nicht dem Installationspfad-Eigentümer; bitte Eigentum prüfen." >&2
  exit 1
fi

echo "Prüfe Laufzeitbenutzer, ASGI-Unit und Datenbankschema …"
PREFLIGHT_ARGS=(
  preflight
  --project-root "$PROJECT_DIR"
  --runtime-user "$PROJECT_OWNER"
)
if [[ "$DRY_RUN" -eq 0 ]]; then
  PREFLIGHT_ARGS+=(--require-ready)
fi
"${OWNER_COMMAND[@]}" "$VENV_PYTHON" -m easyprent_accounting.deployment "${PREFLIGHT_ARGS[@]}"
"${OWNER_COMMAND[@]}" "$VENV_PYTHON" -m easyprent_accounting.packaging preflight-install

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Baue und prüfe das Python-Paket mit Vite-Artefakten …"
  "${OWNER_COMMAND[@]}" "$VENV_PYTHON" -m easyprent_accounting.packaging build "$PROJECT_DIR"
  echo "Trockenlauf abgeschlossen; Paket und systemd-Unit wurden nicht installiert."
  exit 0
fi

echo "Installiere EasyPrent Accounting …"
"${OWNER_COMMAND[@]}" "$VENV_PYTHON" -m easyprent_accounting.packaging install "$PROJECT_DIR"
"${OWNER_COMMAND[@]}" "$VENV_PYTHON" -I -c 'from importlib import resources; import odf, reportlab; package = resources.files("easyprent_accounting"); assert package.joinpath("templates", "utility_settlement.ods").is_file(); assert package.joinpath("static_dist", "index.html").is_file(); print("ODS-, PDF- und Vite-Artefakte verfügbar.")'

DEPLOY_COMMAND=(
  "$VENV_PYTHON"
  -m easyprent_accounting.deployment install
  --project-root "$PROJECT_DIR"
  --runtime-user "$PROJECT_OWNER"
)
if [[ "$(id -u)" -eq 0 ]]; then
  "${DEPLOY_COMMAND[@]}"
elif command -v sudo >/dev/null 2>&1; then
  sudo "${DEPLOY_COMMAND[@]}"
else
  echo "Fehler: Zum Einrichten der systemd-Unit sind root-Rechte oder sudo erforderlich." >&2
  exit 1
fi

"${OWNER_COMMAND[@]}" "$VENV_PYTHON" -m easyprent_accounting.packaging retire-legacy

echo
echo "Installation abgeschlossen. Starten mit:"
echo "  systemctl status easyprent-accounting.service"
echo
echo "Die Anwendung ist anschließend unter http://localhost:8020 erreichbar."
