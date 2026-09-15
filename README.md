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
easyprent-accounting start
```

Oder direkt aus dem Checkout:

```bash
python3 -m easyprent_accounting.cli start
```

Danach ist die Anwendung unter `http://localhost:8020` erreichbar.

Verfügbare Befehle für einen direkt aus dem Checkout gestarteten Server:

- `python3 -m easyprent_accounting.cli start`
- `python3 -m easyprent_accounting.cli stop`
- `python3 -m easyprent_accounting.cli restart`
- `python3 -m easyprent_accounting.cli update`

`update` führt `git pull --ff-only` aus, installiert das Python-Paket aus dem
aktualisierten Checkout neu und startet einen laufenden Server anschließend
automatisch neu. Node.js ist keine Laufzeitabhängigkeit.

Logs und PID-Datei liegen unter `.easyprent/`.

Die einmalige Migration des bekannten unversionierten SQLite-Schemas wird
explizit über `migrate --dry-run` geprüft und erst mit `migrate --cutover`
aktiviert. `restore --backup` stellt die datierte Sicherung wieder her. Die
[Migrations- und Restore-Anleitung](docs/migration-and-restore.md) beschreibt
die Befehle, Prüfberichte und den aktuell noch ausstehenden Anwendungscutover.

Wurde die Anwendung mit `install.sh` als systemd-Dienst eingerichtet, wird der
Server von `easyprent-accounting.service` verwaltet. In diesem Fall dürfen nicht parallel
die direkten `start`- oder `restart`-Befehle verwendet werden, da sonst Port
8020 bereits belegt ist. Für den installierten Dienst gelten stattdessen:

```bash
systemctl status easyprent-accounting.service
systemctl restart easyprent-accounting.service
journalctl -u easyprent-accounting.service -n 100 --no-pager
```

Für eine systemd-Installation wird `update` mit root-Rechten ausgeführt:

```bash
sudo .venv/bin/python -m easyprent_accounting.cli update
```

Der Befehl ersetzt eine vorhandene alte `easy-prent.service`-Unit erst nach
erfolgreichem Preflight und kanonischem Dienststart. Bei einem Fehler bleibt
die Legacy-Unit für einen Rollback erhalten. Beim einmaligen Wechsel von
einem Checkout vor dieser Update-Logik zuerst `git pull --ff-only` ausführen
und danach `install.sh` aus dem aktualisierten Checkout erneut starten; bereits
geladener alter CLI-Code kann sich nicht nachträglich selbst aktualisieren.

`install.sh` und `update` ändern weder Besitzer noch Inhalte einer vorhandenen
Datenbank. Ist `easyprent_accounting.db` aus einem alten root-Dienst nicht für
den neuen Laufzeitbenutzer schreibbar oder enthält `.venv` fremde Besitzer,
stoppt der Preflight mit dem betroffenen Pfad. Vor einer manuellen Korrektur
die Datenbank sichern und Besitzer sowie Rechte gezielt prüfen.

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

Die Umlageschlüssel-Tabelle verwendet eine eigene Prototypzeile mit den
Markern `{{UMLAGE_NR}}`, `{{UMLAGE_ART}}`, `{{UMLAGE_ZEITRAUM}}`,
`{{UMLAGE_TAGE}}`, `{{UMLAGE_GESAMT}}` und `{{UMLAGE_ANTEIL}}`. In den
Kostenzeilen verweisen `{{UMLAGE_REF}}` beziehungsweise
`{{POSITION_UMLAGE_REF}}` auf die automatisch nummerierten Schlüssel. Auch
diese Marker müssen bei Layoutänderungen erhalten bleiben.

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

Der Server verwendet in einem verifizierten Checkout automatisch die
Master-Vorlage. Außerhalb eines Checkouts wird ausschließlich die im
Python-Paket enthaltene Vorlage verwendet; eine zufällig gleichnamige Datei im
Arbeitsverzeichnis wird ignoriert. Alternativ kann über
`EASYPRENT_SETTLEMENT_TEMPLATE` ein anderer Vorlagenpfad angegeben werden.
Absenderdaten können optional über `EASYPRENT_SENDER_NAME`,
`EASYPRENT_SENDER_STREET` und `EASYPRENT_SENDER_CITY` gesetzt werden. Ohne
eigene Absenderkonfiguration wird nur der gespeicherte Organisationsname
eingetragen, da das Datenmodell derzeit keine Organisationsanschrift enthält.

## Annahmen im MVP

- Mehrbenutzerfähigkeit wird fachlich über Organisationen, Nutzer und Rollen vorbereitet.
- Authentifizierung ist noch nicht implementiert.
- Die Abschreibungslogik ist als fachlicher Startpunkt modelliert und rechnet aktuell linear und monatsgenau.

## Qualitätsprüfungen

Lokal läuft derselbe Befehl wie in CI:

```bash
python3 scripts/quality.py
```

Der kanonische Qualitätslauf benötigt Python, Node.js und npm. Er installiert
die Node-Abhängigkeiten reproduzierbar mit `npm ci --ignore-scripts`; die
Produktionsinstallation und der laufende Server benötigen Node.js nicht.
