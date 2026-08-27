# Projektstruktur

## Verzeichnisse

- `src/easyprent_accounting/`
  Python-Anwendung mit Webserver, Datenbankzugriff, Domänenlogik und HTML-Dashboard
- `tests/`
  Unit-Tests für Nebenkosten- und Abschreibungsberechnung

## Wichtige Module

- `db.py`
  SQLite-Schema, Initialisierung und Demo-Daten
- `services.py`
  Fachlogik für CRUD-nahe Abläufe und Auswertungen
- `calculations.py`
  Nebenkosten- und Abschreibungsberechnungen
- `web.py`
  HTTP-Routing, JSON-API und HTML-Ausgabe
- `server.py`
  Lokaler Startpunkt für den Webserver

## Domänenstruktur

- Organisation -> Nutzer -> Rollen
- Immobilie -> Gebäude -> Einheit
- Mieter -> Mietvertrag -> Einheit
- Abrechnungszeitraum -> Kostenposition -> Verteilerschlüssel -> Ergebnis je Vertrag
- Abschreibungsobjekt -> Anschaffungsdaten -> Regel -> Jahreswerte
