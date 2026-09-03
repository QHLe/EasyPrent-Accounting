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

Verfügbare Befehle für einen direkt aus dem Checkout gestarteten Server:

- `./easy-rem start`
- `./easy-rem stop`
- `./easy-rem restart`
- `./easy-rem update`

`update` führt `git pull --ff-only` aus, installiert bei Bedarf Node- und
Python-Abhängigkeiten neu und startet einen laufenden Server anschließend
automatisch neu.

Logs und PID-Datei liegen unter `.easyprent/`.

Wurde die Anwendung mit `install.sh` als systemd-Dienst eingerichtet, wird der
Server von `easy-prent.service` verwaltet. In diesem Fall dürfen nicht parallel
die direkten `start`- oder `restart`-Befehle verwendet werden, da sonst Port
8020 bereits belegt ist. Für den installierten Dienst gelten stattdessen:

```bash
systemctl status easy-prent.service
systemctl restart easy-prent.service
journalctl -u easy-prent.service -n 100 --no-pager
```

`./easy-rem update` erkennt einen laufenden systemd-Dienst und startet ihn nach
dem Update über systemd neu.

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
- `GET /api/settlements/document.ods?property_id=...&lease_id=...&period_start=...&period_end=...`
  befüllt die ODS-Vorlage und lädt die editierbare Abrechnung herunter. Für eine
  einzelne Wohnung ohne Objekt wird stattdessen `unit_id=...` übergeben.
- `GET /api/depreciation-schedule?year=...`

## ODS-Vorlage für Nebenkostenabrechnungen

Die bearbeitbare Master-Vorlage liegt unter
`templates/utility_settlement.ods`. Gestaltung, Spaltenbreiten und
zusammengeführte Zellen können dort mit LibreOffice angepasst werden. Die
Platzhalter in doppelten geschweiften Klammern müssen erhalten bleiben. Die
Zeile mit `{{KOSTENART}}` formatiert Kostenarten beziehungsweise deren
Summenzeilen; die direkt folgende Zeile mit `{{POSITION}}` formatiert
eingerückte Unterpositionen. Zu dieser Zeile gehören außerdem die Marker
`{{POSITION_JAHRESKOSTEN}}`, `{{POSITION_MIETERANTEIL}}` und
`{{POSITION_VERBRAUCH}}`. Gibt es zu einer Kostenart mehrere Positionen oder
weicht der Positionsname von der Kostenart ab, erzeugt der Export die
Unterteilung automatisch. Die Gesamtsumme berücksichtigt nur die
Kostenarten-Summenzeilen und zählt Unterpositionen daher nicht doppelt.
Jahreskosten und Mieteranteile werden linksbündig ausgegeben.

Der angezeigte Abrechnungszeitraum wird auf die tatsächliche Überschneidung
mit dem Mietvertrag begrenzt. Unterjährige und verbrauchsabhängige Kosten
werden mit den für diesen Zeitraum ermittelten Kosten- und Verbrauchswerten
berechnet; es erfolgt keine pauschale Aufteilung durch zwölf. Bei einer
vollständig gepflegten abweichenden Mieteranschrift verwendet die Abrechnung
diese Adresse, andernfalls die Anschrift der Wohnung.

Die im Mietvertrag gespeicherte Nebenkostenvorauszahlung ist nur eine
vertragliche Soll-Angabe und kein Nachweis tatsächlich geleisteter Zahlungen.
Sie wird daher nicht automatisch verrechnet und es wird kein Guthaben oder
keine Nachzahlung berechnet. Der Vorauszahlungs- und Saldoabschnitt bleibt im
ODS als leere, editierbare Struktur erhalten, damit er manuell ergänzt und
später um eine Zahlungsverwaltung erweitert werden kann.

Nach dem Austausch durch eine noch unvorbereitete ODS-Datei werden die Marker
einmalig eingefügt und die Installationskopie aktualisiert:

```bash
.venv/bin/python scripts/prepare_settlement_template.py /pfad/zur/vorlage.ods
```

Der Server verwendet im Checkout automatisch die Master-Vorlage. Alternativ
kann über `EASYPRENT_SETTLEMENT_TEMPLATE` ein anderer Vorlagenpfad angegeben
werden. Absenderdaten können optional über `EASYPRENT_SENDER_NAME`,
`EASYPRENT_SENDER_STREET` und `EASYPRENT_SENDER_CITY` gesetzt werden. Ohne
eigene Absenderkonfiguration wird nur der gespeicherte Organisationsname
eingetragen, da das Datenmodell derzeit keine Organisationsanschrift enthält.

## Annahmen im MVP

- Mehrbenutzerfähigkeit wird fachlich über Organisationen, Nutzer und Rollen vorbereitet.
- Authentifizierung ist noch nicht implementiert.
- Die Abschreibungslogik ist als fachlicher Startpunkt modelliert und rechnet aktuell linear und monatsgenau.
