# Features

## Bereits umgesetzt

- Browserbasierter Einstiegspunkt mit Dashboard und fachlicher Übersicht
- Datenmodell für Organisationen, Rollen, Immobilien, Gebäude, Einheiten, Mieter und Mietverträge
- SQLite-Persistenz mit automatischer Demo-Datenbefüllung
- Nebenkostenabrechnung für frei definierte Zeiträume und einzelne
  Immobilien oder eigenständige Wohnungen
- Verteilerschlüssel:
  `area`, `unit_count`, `occupants`
- Tagesgenaue Berücksichtigung der tatsächlichen Vertragsüberschneidung sowie
  periodenbezogene Verbrauchsermittlung aus Zählerständen
- Editierbarer ODS-Export auf Basis von `templates/utility_settlement.ods`
  mit dynamischen Kostenarten, Unterpositionen und zusammengefassten Summen
- Alternative Mieteranschrift für bereits ausgezogene Mieter
- Vertragsfeld für die Nebenkostenvorauszahlung und leere, manuell
  ausfüllbare Vorauszahlungs-/Saldostruktur im ODS
- Abschreibungsobjekte mit monatsgenauer linearer AfA
- JSON-API zum Anlegen und Auslesen zentraler Stammdaten

## Bewusste MVP-Grenzen

- Keine Benutzeranmeldung
- Keine echte Finanzbuchhaltung
- Keine Erfassung tatsächlich geleisteter Vorauszahlungen und deshalb noch
  keine automatische Berechnung von Nachzahlung oder Guthaben
- Keine automatischen Mahn- oder Zahlungsprozesse

## Fachliche Leitplanken

- Fokus auf saubere Objekt- und Vertragsstruktur
- Nebenkosten zuerst funktionsfähig, bevor Sonderfälle ergänzt werden
- Abschreibung bereits fachlich sichtbar, aber bewusst schlanker als eine vollständige Steuerlösung
