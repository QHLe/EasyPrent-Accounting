# EasyPrent Accounting

EasyPrent Accounting ist ein webbasiertes MVP zur Verwaltung von Mietimmobilien.
Die erste Version deckt vier Kernbereiche ab:

- Verwaltung von Immobilien, Gebäuden und Einheiten
- Verwaltung von Mietern und Mietverträgen
- Nebenkostenabrechnung auf Basis konfigurierbarer Verteilerschlüssel
- Abschreibungsberechnung als vorbereiteter steuerlicher Baustein mit linearer AfA

## CLI

```bash
pip install .
easy-rem start
```

Oder direkt aus dem Checkout:

```bash
./easy-rem start
```

Danach ist die Anwendung unter `http://localhost:8020` erreichbar.

Verfuegbare Befehle:

- `./easy-rem start`
- `./easy-rem stop`
- `./easy-rem restart`
- `./easy-rem update`

`update` fuehrt `git pull --ff-only` aus, installiert bei Bedarf Node-Abhaengigkeiten neu und startet einen laufenden Server anschliessend automatisch neu.

Logs und PID-Datei liegen unter `.easyprent/`.

## Tests

```bash
python3 -m unittest discover -s tests
```

## API-Ueberblick

- `GET /` HTML-Dashboard mit Demo-Daten
- `GET /api/overview` Zusammenfassung und Listen
- `POST /api/properties` Immobilie anlegen
- `POST /api/buildings` Gebäude anlegen
- `POST /api/units` Einheit anlegen
- `POST /api/tenants` Mieter anlegen
- `POST /api/leases` Mietvertrag anlegen
- `POST /api/expenses` Nebenkostenposition anlegen
- `POST /api/depreciation-assets` Abschreibungsobjekt anlegen
- `GET /api/settlements?property_id=...&period_start=...&period_end=...`
- `GET /api/depreciation-schedule?year=...`

## Annahmen im MVP

- Mehrbenutzerfähigkeit wird fachlich über Organisationen, Nutzer und Rollen vorbereitet.
- Authentifizierung ist noch nicht implementiert.
- Die Abschreibungslogik ist als fachlicher Startpunkt modelliert und rechnet aktuell linear und monatsgenau.
