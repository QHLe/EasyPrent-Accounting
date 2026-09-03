# Projektstruktur

## Verzeichnisse

- `src/easyprent_accounting/`
  Python-Anwendung mit Webserver, Datenbankzugriff, Domänenlogik und HTML-Dashboard
- `tests/`
  Unit- und API-Tests für Berechnung, Web-Anwendung und ODS-Ausgabe
- `templates/`
  Bearbeitbare Master-Vorlagen, insbesondere `utility_settlement.ods`
- `scripts/`
  Hilfsprogramme zur Vorbereitung und Synchronisierung der ODS-Vorlage

## Wichtige Module

- `db.py`
  SQLite-Schema, Initialisierung und Demo-Daten
- `services.py`
  Fachlogik für CRUD-nahe Abläufe und Auswertungen
- `calculations.py`
  Nebenkosten- und Abschreibungsberechnungen
- `expense_math.py`
  Tagesgenaue Kostenperioden und Verbrauchsinterpolation
- `ods_template.py`
  Vorbereitung und Befüllung der editierbaren ODS-Abrechnung
- `web.py`
  HTTP-Routing, JSON-API und HTML-Ausgabe
- `server.py`
  Lokaler Startpunkt für den Webserver

## Domänenstruktur

- Organisation -> Nutzer -> Rollen
- Immobilie -> Gebäude -> Einheit
- Mieter -> Mietvertrag -> Einheit
- Abrechnungszeitraum -> Vertragsüberschneidung -> Kostenart -> Position ->
  Verteilerschlüssel/Verbrauch -> Mieteranteil -> editierbares ODS
- Mietvertrag -> vereinbarte Vorauszahlung; spätere Zahlungsbuchungen -> Saldo
- Abschreibungsobjekt -> Anschaffungsdaten -> Regel -> Jahreswerte
