# Entwicklung und Wartung

## Lokaler Qualitätslauf

Aus dem Checkout mit Python 3.11+, Node.js und npm:

```bash
python3 scripts/quality.py
```

Der Befehl installiert JavaScript-Abhängigkeiten mit `npm ci --ignore-scripts`,
führt Typecheck, Vitest, Vite-Build, OpenAPI-/TypeScript-Abgleich,
Python-Tests, JavaScript-Syntaxprüfung und Paketimporte aus. CI verwendet
denselben Befehl. Bei einer HTTP-Vertragsänderung
`python3 scripts/export_openapi.py` und `npm run generate-api` ausführen und
beide generierten Dateien einchecken.

## Fachliche Änderungen

Geschäftsregeln, SQL und Validierung liegen im zuständigen Python-Fachmodul.
`http_*.py` enthält nur Transportmodelle, Routing und Fehlerabbildung.
Frontend-Zustand und Darstellung liegen unter `src/features/<fachbereich>/`;
`src/app/AppShell.tsx` komponiert Navigation und Meldungen. Für eine neue
Schemaänderung eine nummerierte Migration in `schema_runner.py` ergänzen
und Erfolg sowie Rollback mit einer temporären SQLite-Datenbank prüfen.
Legacy-Fingerprints nur nach eigener Datenmigrationsentscheidung erweitern.

## Paket und Installation

Das Python-Wheel wird aus einem isolierten Snapshot gebaut; ein vorhandenes
`static_dist` wird nicht als Build-Eingabe verwendet. Der Builder installiert
Node-Abhängigkeiten mit dem Lockfile und prüft das erzeugte HTML und die
referenzierten Assets im Wheel:

```bash
.venv/bin/python -m easyprent_accounting.packaging build "$PWD"
./install.sh --dry-run
```

`build` prüft das Wheel ohne Installation. `install.sh --dry-run` prüft
zusätzlich Laufzeitbenutzer, systemd-Unit und die konfigurierte Datenbank.
Bei Legacy-Daten führt es eine vollständige Migrationsprobe durch und
behält deren verifizierte Sicherung und JSON-Bericht; es aktiviert keine
Datenbank und installiert keinen Dienst. Anschließend die
[Migrationsanleitung](migration-and-restore.md) befolgen. `./install.sh`
installiert erst, wenn die Datenbank neu oder v1 ist.

Der Checkout muss einem nicht privilegierten Unix-Benutzer gehören; er ist
zugleich Laufzeitbenutzer und Eigentümer von `.venv` und der Standarddatenbank
im Checkout. Der Pfad darf Leerzeichen enthalten. `install.sh` benötigt
`python3`, `python3-venv`, Node.js/npm, `systemd-analyze` und zum
Aktivieren des Dienstes root oder `sudo`. Es verwendet den tatsächlichen
Checkout-Pfad für `WorkingDirectory` und `.venv/bin/python`; es installiert
keine Betriebssystempakete. Bei abweichendem Installationsort den Checkout
dorthin legen, bevor `install.sh` ausgeführt wird.

Der installierte Dienst benötigt kein Node.js:

```bash
systemctl status easyprent-accounting.service
journalctl -u easyprent-accounting.service -n 100 --no-pager
```

Uvicorn startet `easyprent_accounting.asgi:app` auf
`127.0.0.1:8020`. Bei einer Paketaktualisierung den Qualitätslauf und
Migrations-Preflight wiederholen, dann `sudo .venv/bin/python -m
easyprent_accounting.cli update` ausführen. Der Dienst wird vor dem
Entfernen einer alten Unit auf HTTP-Gesundheit geprüft.

## Wiederherstellung und Diagnose

Datenbankänderungen nie durch manuelles Löschen von WAL-Dateien erzwingen.
Die [Migrations- und Restore-Anleitung](migration-and-restore.md) enthält
Dry-Run, Cutover, Berichtsprüfung und Restore. Ein laufender Dienst muss für
Cutover und Restore gestoppt sein. `/api/v1/health` prüft den HTTP-Einstieg;
`/openapi.json` ist der aktuelle API-Vertrag. Logs eines lokalen CLI-Starts
liegen unter `.easyprent/`, Dienstlogs im Journal.
