# EasyPrent Accounting

EasyPrent Accounting ist ein webbasiertes MVP zur Verwaltung von Mietimmobilien.
Die erste Version deckt vier Kernbereiche ab:

- Verwaltung von Immobilien, Gebäuden und Einheiten
- Verwaltung von Mietern und Mietverträgen
- Nebenkostenabrechnung auf Basis konfigurierbarer Verteilerschlüssel
- Abschreibungsberechnung als vorbereiteter steuerlicher Baustein mit linearer AfA

## Installation und Start

Für einen lokalen Start aus dem Checkout mit Python 3.11+ und installierten
Python-Abhängigkeiten:

```bash
python3 -m easyprent_accounting.cli start
```

Danach ist die Anwendung unter `http://localhost:8020` erreichbar. Für den
Produktionsbetrieb baut `install.sh` den Vite-Produktionsstand in ein
Python-Wheel und richtet einen systemd-Dienst mit Uvicorn ein:

```bash
./install.sh --dry-run
./install.sh
```

Der Checkout muss einem nicht privilegierten Unix-Benutzer gehören.
`--dry-run` prüft Wheel-Bau, Pfade, Laufzeitrechte, systemd-Unit und
Datenbankschema ohne Paket- oder Dienstinstallation. Bei einem Legacy-Schema
führt er eine vollständige Migrationsprobe durch und schreibt JSON-Bericht
sowie verifizierte Sicherung. Vor `./install.sh` muss der explizite
[Migrations-Cutover](docs/migration-and-restore.md) abgeschlossen sein.
Node.js/npm sind zum Bauen nötig, nicht für den installierten Dienst.
Weitere Voraussetzungen und Update-Schritte stehen in der
[Wartungsanleitung](docs/maintenance.md).

Ein bestehender systemd-Dienst wird mit diesen Befehlen verwaltet:

```bash
systemctl status easyprent-accounting.service
systemctl restart easyprent-accounting.service
journalctl -u easyprent-accounting.service -n 100 --no-pager
```

Für einen direkt gestarteten CLI-Server stehen `start`, `stop` und
`restart` zur Verfügung. Nicht parallel zum systemd-Dienst starten.
`easyprent-accounting migrate --dry-run`, `migrate --cutover` und
`restore --backup` sind die öffentlichen Datenbankbefehle; die
[Migrationsanleitung](docs/migration-and-restore.md) beschreibt Bericht,
Sicherung, Cutover und Wiederherstellung.

## API und Frontend

FastAPI erzeugt den API-Vertrag unter `/openapi.json` und die interaktive
Dokumentation unter `/docs`. Der Health-Endpunkt ist
`GET /api/v1/health`. Fachliche Endpunkte unter `/api/v1/` decken
Anlagen, Mieter, Zähler, Kosten, Abrechnungen, Dokumente, Einstellungen,
Abschreibung und Dashboard ab. Die React-Anwendung wird unter `/` aus dem
Python-Paket ausgeliefert. [Architektur](Structure.md) und
[Wartung](docs/maintenance.md) beschreiben die Modulgrenzen und
Typgenerierung.

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

Der Qualitätslauf benötigt Python, Node.js und npm; er installiert die
Node-Abhängigkeiten reproduzierbar mit `npm ci --ignore-scripts`, prüft
TypeScript, Vitest und den Vite-Build, gleicht generierte API-Typen ab und
führt die Python-Tests aus. Der installierte Server benötigt Node.js nicht.
