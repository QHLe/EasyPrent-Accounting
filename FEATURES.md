# Features

## Bereits umgesetzt

- Browserbasierter Einstiegspunkt mit Dashboard und fachlicher Übersicht
- Datenmodell für Organisationen, Rollen, Immobilien, Gebäude, Einheiten, Mieter und Mietverträge
- SQLite-Persistenz mit automatischer Demo-Datenbefüllung
- Nebenkostenabrechnung für definierte Zeiträume
- Verteilerschlüssel:
  `area`, `unit_count`, `occupants`
- Vorauszahlungslogik pro Mietvertrag und periodenbezogene Nachzahlung/Guthaben
- Abschreibungsobjekte mit monatsgenauer linearer AfA
- JSON-API zum Anlegen und Auslesen zentraler Stammdaten

## Bewusste MVP-Grenzen

- Keine Benutzeranmeldung
- Keine Dokumentenablage für Verträge
- Keine echte Finanzbuchhaltung
- Keine automatischen Mahn- oder Zahlungsprozesse

## Fachliche Leitplanken

- Fokus auf saubere Objekt- und Vertragsstruktur
- Nebenkosten zuerst funktionsfähig, bevor Sonderfälle ergänzt werden
- Abschreibung bereits fachlich sichtbar, aber bewusst schlanker als eine vollständige Steuerlösung
