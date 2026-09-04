# Entscheidungslandkarte: GnuCash-Zahlungsimport für Nebenkostenabrechnungen

## Zielbild

Beim Anfordern einer konkreten Nebenkostenabrechnung liest EasyPrent
ausschließlich die dafür relevanten Buchungen der verknüpften
Nebenkostenvorauszahlungskonten aus dem GnuCash-Buch in einer
entfernten PostgreSQL-Datenbank über `piecash`. Aus den Split-Buchungen werden
idempotent Zahlungsnachweise importiert: Ein bereits gespeicherter GnuCash-Split
wird nicht erneut angelegt. Eine Zuordnung verbindet einen Zahlungsnachweis
nachvollziehbar mit einem Mietvertrag; sein Zahlungsmonat wird unmittelbar aus
dem Buchungsdatum abgeleitet. Die
Nebenkostenabrechnung verrechnet die importierten Zahlungsnachweise der Kategorie
`Nebenkostenvorauszahlung`; Vertragswerte sind lediglich Sollwerte für die
Plausibilitätsprüfung.

## Bereits geklärt

- **GnuCash ist das führende Buchungsbuch.** EasyPrent schreibt weder Buchungen
  noch Änderungen in die GnuCash-Datei zurück.
- **GnuCash liegt entfernt in PostgreSQL.** EasyPrent verbindet sich über das
  Netzwerk mit einem dedizierten PostgreSQL-Lesezugang; `piecash.open_book()`
  unterstützt dafür eine PostgreSQL/SQLAlchemy-Verbindungszeichenkette im
  Read-only-Modus.
- **Erster Zahlungszweck:** Nebenkostenvorauszahlungen. Kaltmiete, Nachzahlungen,
  Guthaben, Kaution und Ausgaben folgen später als getrennte Kategorien.
- **Repository-Bestand:** Mietverträge enthalten eine monatliche Soll-
  Vorauszahlung, die Abrechnung weist aber derzeit keine Ist-Zahlungen und keinen
  Saldo aus. Das neue Modell ergänzt diesen Bestand, statt den Vertragswert als
  Zahlung umzudeuten.
- **Importumfang:** Es gibt keinen Hintergrundabzug. Der Abrechnungs-Button
  importiert nur die benötigten Buchungen des angefragten Zeitraums. Ein
  eindeutiger GnuCash-Schlüssel je importiertem Split verhindert doppelte lokale
  Zahlungsnachweise bei wiederholtem Öffnen derselben Abrechnung.
- **Vertragszuordnung:** Jeder Mietvertrag besitzt ein ausgewähltes
  **GnuCash-NK-Vorauszahlungskonto**. Die Aufsplittung erfolgt bereits in
  GnuCash; jede Buchung auf diesem Konto ist damit direkt diesem Mietvertrag und
  der Zahlungsart Nebenkostenvorauszahlung zugeordnet.
- **Bestandsmigration:** Eine frühere Kontoverknüpfung am Mieter wird auf den
  Vertrag mit bereits importierten Zahlungen übertragen, andernfalls auf den
  zuletzt begonnenen Vertrag. Ein GnuCash-Konto bleibt genau einem Mietvertrag
  zugeordnet; weitere Verträge werden bei Bedarf in ihrer Vertragsmaske manuell
  verknüpft. Neue Sicherungen verwenden Exportformat 2, beim Import alter
  Sicherungen im Format 1 erfolgt dieselbe Übertragung automatisch.
- **Zahlungsmonat:** Für die Abrechnung zählt der Kalendermonat des
  GnuCash-Buchungsdatums. Es gibt keine manuelle Monatszuordnung und keine
  Aufteilung einer Zahlung auf mehrere Monate.
- **Zeitraumprüfung:** Eine Buchung wird nur berücksichtigt, wenn ihr
  Buchungsdatum sowohl in den angefragten Abrechnungszeitraum als auch in die
  Laufzeit des verknüpften Mietvertrags fällt. Buchungen vor Vertragsbeginn oder
  nach Vertragsende bleiben vorerst unberücksichtigt.
- **Zukünftige Zahlungsentscheidung:** EasyPrent bereitet je
  Abrechnungsvorgang eine lokale Zuordnung eines GnuCash-Splits vor. Sie hält
  fest, ob ein Split berücksichtigt oder ausgeschlossen wurde, einschließlich
  Betrag und Begründung. Der GnuCash-Split bleibt dabei unverändert die
  Buchungsquelle. Eine spätere KVP-Rückschreibung in GnuCash ist optional und
  benötigt eine gesonderte Schreibberechtigung; sie ist nicht Teil des aktuellen
  Imports.

## Vorbereitetes Datenmodell für Zahlungszuordnungen

`settlement_runs` beschreibt einen Abrechnungsvorgang mit stabiler UUID,
Abrechnungszeitraum, Zielobjekt und Status. Die Tabelle
`settlement_payment_assignments` verbindet diesen Vorgang mit einem importierten
GnuCash-Split (`split_guid`) und dessen Mietvertrag.

- `status = considered`: Die Zahlung zählt für genau einen Abrechnungsvorgang.
- `status = excluded`: Die Zahlung ist für diesen Vorgang sichtbar, aber nicht
  eingerechnet; `reason` kann etwa `before-period`, `after-period` oder
  `outside-lease` enthalten.
- `assigned_amount` ist für eine spätere Teilzahlungszuordnung vorgesehen.

Die Tabellen werden bereits mit der Datenbank angelegt und in Sicherungen
einbezogen. Die Bedienoberfläche zum Anlegen von Abrechnungsvorgängen und zum
manuellen Entscheiden über Zahlungen folgt in einem eigenen Schritt.

## #1: Wo wird das GnuCash-Buch gelesen?

Type: Grilling

### Question

Läuft EasyPrent auf demselben Server wie die GnuCash-Datei oder wird über das
Netzwerk auf ein GnuCash-Buch zugegriffen?

### Recommendation

Einen dedizierten PostgreSQL-Benutzer ohne Schreibrechte verwenden. Die
Verbindungsdaten gehören in die Server-Secret-Konfiguration, niemals in den
EasyPrent-Datenexport oder in Browser-Antworten. Der Import öffnet das Buch mit
`readonly=True`; die Anbindung wird mit TLS und einer Netzwerkfreigabe nur vom
EasyPrent-Server abgesichert.

### Answer

Das GnuCash-Buch liegt auf einem anderen Rechner im Netzwerk und nutzt
PostgreSQL. EasyPrent greift daher über eine Netzwerkverbindung lesend zu.

## #1a: Wie wird der Import ausgelöst?

Blocked by: #1
Type: Grilling

### Question

Soll die Synchronisation zunächst nur über einen manuellen Button mit Vorschau
laufen, oder soll der Server sie bereits zeitgesteuert (z. B. nachts) ausführen?

### Recommendation

Manuell im Abrechnungsablauf: Der Klick auf „Abrechnung laden“ stößt einen auf
den Abrechnungszeitraum begrenzten, idempotenten Import mit Vorschau an. Es gibt
keinen Scheduler und keinen allgemeinen Synchronisationslauf.

### Answer

Der Import wird ausschließlich per Button für die konkret angeforderte
Abrechnung gestartet. Er darf keine bereits bekannten Zahlungsnachweise erneut
anlegen und lädt keine Daten außerhalb des benötigten Zeitraums.

## #2: Welche GnuCash-Splits sind potenzielle Mietzahlungen?

Blocked by: #1
Type: Grilling

### Question

Wo werden die Verbindungsdaten gepflegt und welches Merkmal verbindet einen
Mietvertrag mit seinen GnuCash-Buchungen?

### Answer

Die PostgreSQL-Zugangsdaten werden in den EasyPrent-Einstellungen hinterlegt.
In der Mietvertragsmaske wird das zugehörige GnuCash-Konto ausgewählt. Dieses
Konto ist der Primärschlüssel für die Zahlungszuordnung; Buchungstext und
Verwendungszweck sind dafür nicht erforderlich. Zusätzlich muss das
Buchungsdatum in der Laufzeit dieses Mietvertrags liegen.

## #2a: Welche Kontoseite wird beim Mietvertrag hinterlegt?

Blocked by: #2
Type: Grilling

### Question

Ist das in der Mietvertragsmaske ausgewählte Konto das zugehörige
**GnuCash-NK-Vorauszahlungskonto**?

### Recommendation

Das GnuCash-NK-Vorauszahlungskonto hinterlegen und ausschließlich dessen Splits
importieren. Die in GnuCash bereits vorgenommene Aufsplittung ist die fachliche
Quelle der Zuordnung; ein zusätzliches Bankkonto ist nicht nötig.

### Answer

Es handelt sich um das GnuCash-NK-Vorauszahlungskonto für diesen Mietvertrag,
nicht um ein Bankkonto.

## #3: Wie erfolgt die Zuordnung zum Mietvertrag?

Blocked by: #2a
Type: Grilling

### Question

Wie wird eine GnuCash-Buchung einem Mietvertrag statt nur per Textsuche
eindeutig zugeordnet?

### Recommendation

Das GnuCash-NK-Vorauszahlungskonto als fachlich stabile Kontoverknüpfung am
Mietvertrag verwenden. Damit ist keine Heuristik aus Mietername, Betrag,
Verwendungszweck oder Buchungsdatum erforderlich.

### Answer

Jeder Split auf dem beim Mietvertrag hinterlegten
GnuCash-NK-Vorauszahlungskonto ist bereits direkt diesem Vertrag zugeordnet.

## #3a: Woran erkennt das System die Nebenkostenvorauszahlung?

Blocked by: #3
Type: Grilling

### Question

Sind Nebenkostenvorauszahlungen im GnuCash-Mieterkonto als eigene Buchungen bzw.
eigenes Unterkonto getrennt von Kaltmiete und anderen Zahlungen gebucht, oder
kommt dort eine gemeinsame Gesamtmiete an?

### Recommendation

Eine eindeutige Buchungskategorie oder ein separates Unterkonto für die
Nebenkostenvorauszahlung verwenden. Bei einer Gesamtmiete darf EasyPrent den
NK-Anteil nicht still aus dem Vertrags-Sollwert schätzen; er muss als eigene
Aufteilung erfasst oder bestätigt werden.

### Answer

Die Nebenkostenvorauszahlung wird auf einem eigenen Unterkonto des
GnuCash-Mieterkontos gebucht. Die Mietvertragsmaske verknüpft für diesen Import
direkt dieses Unterkonto; Kaltmiete und andere Zahlungen liegen außerhalb des
Importumfangs.

## #4: Welcher Zahlungsmonat zählt bei verspäteten, Teil- oder Sammelzahlungen?

Blocked by: #3a
Type: Grilling

### Question

Soll der Zahlungsmonat aus dem Buchungsdatum abgeleitet werden, oder darf eine
Zahlung einem anderen Sollmonat zugeordnet und auf mehrere Monate aufgeteilt
werden?

### Recommendation

Den Kalendermonat des Buchungsdatums unmittelbar als Zahlungsmonat verwenden.
Das ist vollständig automatisch, leicht erklärbar und benötigt keine
Zuordnungsmaske.

### Answer

Es zählt ausschließlich der Kalendermonat des Buchungsdatums. Eine verspätete
Zahlung wird folglich im Monat ihrer tatsächlichen Buchung berücksichtigt;
Teil- und Sammelzahlungen werden nicht auf andere Monate verteilt.

## #5: Wie werden Korrekturen und die Abrechnung freigegeben?

Blocked by: #4
Type: Grilling

### Question

Welche Zustände brauchen Zahlungen und Abrechnungen (z. B. importiert,
vorgeschlagen, bestätigt, ausgeschlossen; Entwurf, freigegeben, storniert), und
dürfen bereits freigegebene Abrechnungen nach späteren Importen geändert werden?

### Recommendation

Freigegebene Abrechnungen als Snapshot behandeln. Spätere Korrekturen erzeugen
eine neue Version bzw. Korrekturabrechnung statt still das historische Ergebnis
zu verändern.

### Answer

Es gibt im MVP keine Freigabe-, Entwurfs- oder Korrekturzustände. Jede
Abrechnungsaktualisierung importiert die fehlenden Buchungen des angefragten
Zeitraums und berechnet das Ergebnis live neu. Ein heruntergeladenes
ODS-Dokument ist lediglich ein Stand zum Exportzeitpunkt und wird im System
nicht versioniert oder eingefroren.

## Umsetzungsplan

1. `piecash` mit PostgreSQL-Treiber als Server-Abhängigkeit ergänzen und eine
   read-only Integrationsschicht mit Verbindungs- und Fehlerbehandlung bauen.
2. GnuCash-Einstellungen (Host, Port, Datenbank, Benutzer, Passwort, TLS) sowie
   „Verbindung testen“ im Einstellungs-Tab ergänzen; Zugangsdaten nie exportieren.
3. Die Kontohierarchie bei Bedarf über `piecash` laden und in der
   Mietvertragsmaske das GnuCash-NK-Vorauszahlungskonto per stabiler
   GnuCash-GUID speichern.
4. Eine lokale Tabelle für importierte Zahlungs-Splits mit einzigartiger
   GnuCash-Split-GUID anlegen. Der Abrechnungs-Button importiert nur Splits der
   ausgewählten Mieter-Unterkonten im angefragten Zeitraum.
5. Die Abrechnungsberechnung um Ist-Vorauszahlungen und Saldo erweitern:
   Zahlungsbetrag und Zahlungsmonat stammen unmittelbar aus Betrag und
   Buchungsdatum des importierten Splits.
6. Die Oberfläche zeigt Kostenanteil, geleistete Vorauszahlungen und
   Nachzahlung/Guthaben. Jede Aktualisierung berechnet live neu; ODS enthält
   genau diesen aktuellen Stand.
7. Tests für Kontoauswahl, Zeitraumgrenzen, Split-Deduplizierung, nicht
   erreichbares GnuCash und Live-Neuberechnung ergänzen.
