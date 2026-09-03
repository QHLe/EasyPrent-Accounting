# TODO

## Fachlich

- Sonderfälle in der Nebenkostenabrechnung ergänzen:
  Leerstand, Änderungen innerhalb eines laufenden Vertrags und Ausschlüsse
  einzelner Kostenarten
- Tatsächlich geleistete Nebenkostenvorauszahlungen mit Buchungsdatum und
  Betrag erfassen und daraus den periodenbezogenen Saldo berechnen; die dafür
  vorgesehene ODS-Struktur ist bereits vorhanden
- Erweiterte Abschreibungslogik ausbauen:
  Sonderabschreibungen, Komponentenansatz, Denkmalschutz, Modernisierungsmaßnahmen
- Authentifizierung und Rechteprüfung auf Basis der Rollen aktivieren

## Technisch

- Formulare und Validierungsfehler im Frontend ergänzen
- Datenbankmigrationen statt Initialschema einführen
- OpenAPI-Beschreibung mit den weiteren Funktionen synchron halten
- Optionalen CSV-Export für Abrechnungsdaten ergänzen

## Qualität

- API- und ODS-Regressionsfälle für weitere Abrechnungssonderfälle ergänzen
- Historisierung für Vertragsänderungen und Staffelmieten ausbauen
- Beispielmandanten für private Vermieter und Hausverwaltung getrennt abbilden
