# Anforderungen

## Zweck

Dieses Dokument hält fachliche Anforderungen mit stabilen IDs fest.
Die IDs dienen der Rückverfolgbarkeit zwischen Anforderung, Implementierung,
Testfall und Abnahme.

## ID-Schema

- `REQ-WEB-*` für allgemeine Anforderungen an die Web-Anwendung
- `REQ-PROP-*` für Immobilien, Gebäude und Einheiten
- `REQ-LEASE-*` für Mieter und Mietverträge
- `REQ-NKA-*` für Nebenkostenabrechnung
- `REQ-DEPR-*` für Abschreibung
- `REQ-ROLE-*` für Mandanten, Nutzer und Rollen
- `NFR-*` für nicht-funktionale Anforderungen
- `OUT-*` für aktuell bewusst ausgeschlossene Themen

## Produktziel

EasyPrent Accounting ist ein webbasiertes Tool zur Verwaltung von Mietimmobilien.
Es soll sowohl für private Vermieter als auch für Hausverwaltungen nutzbar sein.
Der fachliche Schwerpunkt liegt auf der strukturierten Verwaltung von Immobilien,
Mietverträgen, Nebenkosten und abschreibungsrelevanten Objektdaten.

## Zielgruppen

- Private Vermieter mit wenigen bis mittleren Objektbeständen
- Hausverwaltungen mit mehreren Immobilien und mehreren Nutzern
- Mitarbeitende mit unterschiedlichen Rollen, zum Beispiel Verwaltung oder Sachbearbeitung

## Funktionale Anforderungen

### Webbasierte Anwendung

- `REQ-WEB-001`
  Die Anwendung muss über einen Browser nutzbar sein.
- `REQ-WEB-002`
  Die Anwendung muss eine zentrale Datenhaltung bereitstellen.
- `REQ-WEB-003`
  Die Anwendung darf keine lokale Desktop-Installation voraussetzen.
- `REQ-WEB-004`
  Die Anwendung muss einen Erfassungsbereich für neue Objekte bereitstellen.
- `REQ-WEB-005`
  Im ersten Schritt muss der Erfassungsbereich mindestens einen Tab für neue Kosten bereitstellen.
- `REQ-WEB-006`
  Die Anwendung muss eine maschinenlesbare OpenAPI-Beschreibung der HTTP-Schnittstellen bereitstellen.
- `REQ-WEB-007`
  Die Web-Oberfläche muss mit React als UI-Framework von Meta umgesetzt werden.
- `REQ-WEB-008`
  Die React-Oberfläche muss die Anwendungsdaten über die dokumentierten API-Endpunkte laden und Änderungen über API-Aufrufe speichern können.
- `REQ-WEB-009`
  Die OpenAPI-Beschreibung muss mindestens die Endpunkte für Übersicht, Nebenkostenabrechnung, Abschreibungsplan und Kostenerfassung dokumentieren.
- `REQ-WEB-010`
  Die React-Laufzeit muss lokal mit der Anwendung ausgeliefert werden und darf für die Grundfunktion nicht von externen CDN-Ressourcen abhängen.
- `REQ-WEB-011`
  Der Erfassungsbereich muss Tabs für Anlagen, Gebäude, Wohnungen, Zimmer und Kosten anzeigen.
- `REQ-WEB-012`
  Die Tabs für Gebäude, Wohnungen, Zimmer und Kosten müssen als nutzbare Erfassungsformulare umgesetzt sein.
- `REQ-WEB-013`
  Die Web-Oberfläche muss einen eigenen Haupt-Tab `Neue Objekte` für die Objekterfassung bereitstellen.
- `REQ-WEB-014`
  Die Übersicht und die Objekterfassung müssen als getrennte Haupt-Tabs nutzbar sein.
- `REQ-WEB-015`
  Die ausgelieferte React-Oberfläche muss als syntaktisch gültiges JavaScript bereitgestellt werden, damit die Startseite ohne Frontend-Abbruch gerendert werden kann.
- `REQ-WEB-016`
  Im Haupt-Tab `Objektverwaltung` muss die Objektliste Anlagen, Gebäude, Wohnungen und Zimmer gemeinsam anzeigen, unabhängig davon, welcher Objekt-Untertab gerade für die Erfassung aktiv ist.
- `REQ-WEB-017`
  Die Objektvorschau für Wohnungen muss mindestens Bezeichnung, Gebäudezuordnung, Anlagenzuordnung, Adresse, Fläche, deklarierte Zimmeranzahl und Anzahl der bereits erfassten Zimmer anzeigen.
- `REQ-WEB-018`
  Die Objektvorschau muss für unterstützte Objektarten eine Aktion zum Archivieren aktiver Einträge und eine Aktion zum Löschen bereits archivierter Einträge bereitstellen.
- `REQ-WEB-019`
  Archivierte Objekte müssen in der Objektvorschau mit ihrem Archivstatus sichtbar bleiben, bis sie gelöscht werden.
- `REQ-WEB-020`
  Das Kostenformular muss die Auswahl einer Zielobjektart und eines konkreten Zielobjekts für Kostenpositionen bereitstellen.
- `REQ-WEB-021`
  Der Erfassungsbereich muss einen nutzbaren Tab für Zähler bereitstellen.
- `REQ-WEB-022`
  Im Zähler-Tab müssen Zähler angelegt und Zählerstände mit Datum und Wert erfasst werden können.
- `REQ-WEB-023`
  Das Kostenformular muss für verbrauchsbezogene Kosten alternativ zur manuellen Verbrauchseinheit auch die Auswahl eines Zählers unterstützen.
- `REQ-WEB-024`
  Im Zähler-Tab muss für den ausgewählten Zähler die vollständige Zählerstandhistorie sichtbar sein.
- `REQ-WEB-025`
  Die Zählerstandhistorie muss durch Auswahl oder Klick auf einen Zähler aus der Zählerliste geöffnet werden können.
- `REQ-WEB-026`
  Im Zähler-Tab muss jeder einzelne Zählerstand aus der Historie löschbar sein.
- `REQ-WEB-027`
  Im Zähler-Tab muss für den ausgewählten Zähler eine grafische Darstellung der Zählerentwicklung verfügbar sein.
- `REQ-WEB-028`
  Die grafische Darstellung der Zählerentwicklung muss mindestens zwischen Monats- und Jahresansicht umschaltbar sein.
- `REQ-WEB-029`
  Die grafische Darstellung der Zählerentwicklung muss mindestens als kumulierte Entwicklung und als Säulendarstellung nutzbar sein.
- `REQ-WEB-030`
  Die grafische Darstellung der Zählerentwicklung muss Zwischenstände zwischen real erfassten Zählerständen interpolieren können.
- `REQ-WEB-031`
  Für die Interpolation der Zählerentwicklung muss mindestens zwischen `linear` und `quadratisch` umgeschaltet werden können.
- `REQ-WEB-032`
  Die Kostenvorschau darf keinen abgeleiteten Anlagenbezug für Kostenpositionen anzeigen.
- `REQ-WEB-033`
  Aktive Kostenpositionen müssen in der Kostenvorschau bearbeitbar sein.
- `REQ-WEB-034`
  Der Editor für eine Kostenposition muss direkt unterhalb der ausgewählten Kostenzeile eingeblendet werden.
- `REQ-WEB-035`
  Im Kostenformular müssen `Zielobjektart` und `Zielobjekt` als ein gemeinsames Auswahlfeld für das Zielobjekt dargestellt werden.
- `REQ-WEB-036`
  Das gemeinsame Auswahlfeld für das Zielobjekt im Kostenformular muss die auswählbaren Objekte mindestens nach `Anlage`, `Gebäude`, `Wohnung` und `Zimmer` gruppieren.
- `REQ-WEB-037`
  Aktive Kostenpositionen müssen durch Klick auf die jeweilige Kostenzeile inline bearbeitbar sein.
- `REQ-WEB-038`
  Solange eine Kostenposition inline bearbeitet wird, darf für diese Kostenzeile keine Archivierungsaktion angezeigt werden.
- `REQ-WEB-039`
  In der Kostenauflistung muss die fachliche Kostenart getrennt von der Abrechnungsart dargestellt werden.
- `REQ-WEB-040`
  In der Kostenauflistung muss zu jeder Kostenposition ein Empfänger oder Begünstigter angezeigt werden können.
- `REQ-WEB-041`
  Die Spaltenbezeichnung `Typ` darf in der Kostenauflistung nicht für Turnus- oder Abrechnungswerte verwendet werden; stattdessen müssen sprechende Bezeichnungen wie `Abrechnungsart` und `Turnus` verwendet werden.
- `REQ-WEB-042`
  Im Kostenformular müssen vorhandene Kostenarten mit zugehörigem Empfänger zur Auswahl eingeblendet werden können.
- `REQ-WEB-043`
  Die Auswahl einer vorhandenen Kostenart im Kostenformular muss die zugehörigen Stammdaten für Kostenart und Empfänger vorbelegen können.
- `REQ-WEB-044`
  Für aktive Kostenpositionen darf die Archivierungsaktion in der Objektliste nicht als separate Zeilenaktion erscheinen, sondern nur innerhalb der eingeblendeten Bearbeitungsmaske.
- `REQ-WEB-045`
  Für alle Objektarten mit Archivierungsfunktion muss in der Benutzeroberfläche eine Aktion zum Rückgängigmachen der Archivierung verfügbar sein.
- `REQ-WEB-046`
  Das Kostenart-Feld im Kostenformular muss beim Eintippen vorhandene Kostenarten direkt als Vorschläge anzeigen.
- `REQ-WEB-047`
  Für Kostenart-Vorschläge darf kein separates Feld `Vorhandene Kostenart` mehr angezeigt werden; die Vorschläge müssen direkt im Feld `Kostenart` eingeblendet werden.
- `REQ-WEB-048`
  Bei verbrauchsbezogenen Kosten darf das Feld für den manuellen Verbrauchswert nur sichtbar und editierbar sein, wenn kein Zähler zugeordnet ist.
- `REQ-WEB-049`
  Bei zählerbezogenen Verbrauchskosten muss die Benutzeroberfläche bei abweichender Verbrauchseinheit die Eingabe eines Umrechnungsfaktors ermöglichen.
- `REQ-WEB-050`
  Das Kostenformular und die Kostenvorschau müssen für verbrauchsbezogene Kosten eine berechnete Gesamtsumme anzeigen können.
- `REQ-WEB-051`
  In der grafischen Zählerentwicklung müssen tatsächlich erfasste Zählerstände als explizit markierte Messpunkte erkennbar sein.
- `REQ-WEB-052`
  Interpolierte Punkte an Monats- oder Jahreswechseln müssen in der grafischen Zählerentwicklung visuell von erfassten Messpunkten unterscheidbar dargestellt werden.
- `REQ-WEB-053`
  Im Bereich `Zählerentwicklung` muss ein frei wählbarer Zeitraum mit `Von-Datum` und `Bis-Datum` verfügbar sein.
- `REQ-WEB-054`
  Der voreingestellte Zeitraum der Zählerentwicklung muss standardmäßig die letzten 12 Monate bis zum zuletzt verfügbaren Zählerstand abdecken.
- `REQ-WEB-059`
  Die grafische Zählerentwicklung muss über ein professionelles Chart-Framework mit interaktivem Tooltip umgesetzt werden.
- `REQ-WEB-060`
  Änderungen von `Von-Datum` und `Bis-Datum` in der Zählerentwicklung müssen die dargestellten Chart-Werte auch bei untermonatlichen oder unterjährigen Zeiträumen nachvollziehbar beeinflussen.
- `REQ-WEB-061`
  Die Y-Achse der Zählerentwicklung muss absolute Messwerte anzeigen und automatisch an die dargestellten Werte skaliert werden, ohne manuellen Y-Achsen-Slider.
- `REQ-WEB-062`
  Im Kostenbereich muss eine grafische Darstellung der Kostenentwicklung verfügbar sein.
- `REQ-WEB-063`
  Die Kostenentwicklung muss mindestens konfigurierbar nach Zeitraum, Granularität und Diagrammtyp sein sowie Filter nach Zielobjekt und Kostenart unterstützen.
- `REQ-WEB-064`
  Im Säulendiagramm der Kostenentwicklung muss die Zusammensetzung farblich nach Kostenarten hervorgehoben werden, sodass Beitragsanteile pro Zeitraum visuell unterscheidbar sind.
- `REQ-WEB-064a`
  Zählergebundene verbrauchsbezogene Kosten müssen in der Kostenentwicklung für jeden angezeigten Zeitraum aus den tatsächlichen oder linear interpolierten Zählerständen berechnet werden; eine zeitanteilige Verteilung ihres Gesamtbetrags ist dafür nicht zulässig.
- `REQ-WEB-065`
  In der Kostenübersicht der Hauptansicht müssen Kostenpositionen standardmäßig nach Enddatum absteigend sortiert sein (neueste zuerst, älteste zuletzt).
- `REQ-WEB-066`
  Es muss einen Tab `Einstellungen` geben, in dem die Paperless-URL und ein API-Token gepflegt werden können; gespeicherte Tokens müssen maskiert angezeigt werden, sodass nur die letzten 4 Zeichen sichtbar sind.
- `REQ-WEB-067`
  Beim Laden der Anwendung muss die Erreichbarkeit des Servers geprüft und als Status in der Oberfläche angezeigt werden.
- `REQ-WEB-068`
  Im Bearbeitungspanel einer Kostenposition müssen ein oder mehrere Dokumente in einem Upload-Vorgang ausgewählt und hochgeladen werden können.
- `REQ-WEB-069`
  Hochgeladene Dokumente müssen einer konkreten Kostenposition zugeordnet, im Bearbeitungspanel gelistet und für den Abruf verfügbar gemacht werden.
- `REQ-WEB-070`
  Wenn Paperless konfiguriert ist, muss der Dokumenten-Upload den Upload zu Paperless versuchen und eine Referenz auf das Paperless-Dokument oder den Paperless-Task je Dokument speichern.
- `REQ-WEB-071`
  Die Web-Oberfläche muss einen eigenen Haupt-Tab `Kostenverwaltung` bereitstellen.
- `REQ-WEB-072`
  Die Untertabs `Kosten` und `Zähler` müssen im Haupt-Tab `Kostenverwaltung` geführt werden; der Haupt-Tab `Objektverwaltung` darf diese Untertabs nicht mehr enthalten.
- `REQ-WEB-073`
  Für `Gesamtkosten` muss das Formular einen verpflichtenden Zeitraum (`Von-Datum` und `Bis-Datum`) erfassbar machen; ein separates Einzeldatum darf nicht mehr erforderlich sein.
- `REQ-WEB-074`
  Die Web-Oberfläche muss einen eigenen Haupt-Tab `Mieterverwaltung` bereitstellen.
- `REQ-WEB-075`
  Im Haupt-Tab `Mieterverwaltung` müssen die Untertabs `Mieter` und `Mietverträge` verfügbar sein.
- `REQ-WEB-076`
  Im Untertab `Mieter` müssen Mieter mit Pflichtfeld `Name` sowie optionalen Kontaktdaten (`E-Mail`, `Telefon`) erfasst und in einer Liste angezeigt werden können.
- `REQ-WEB-077`
  Im Untertab `Mietverträge` müssen Mietverträge mit den Feldern Einheit, Mieter, Kaltmiete, Nebenkostenvorauszahlung, Personenzahl, Startdatum, optionales Enddatum und Status erfasst und in einer Liste angezeigt werden können.
- `REQ-WEB-078`
  In den Bereichen `Objektverwaltung` und `Mieterverwaltung` muss die jeweilige Listenansicht über mindestens einen Textfilter verfügen.
- `REQ-WEB-079`
  In den Bereichen `Objektverwaltung` und `Mieterverwaltung` müssen Listeneinträge per Klick in einen Bearbeitungsmodus überführt und gespeichert werden können.
- `REQ-WEB-080`
  Erfassungsformulare in den Verwaltungs-Tabs müssen initial ausgeblendet sein und erst nach explizitem Benutzerklick angezeigt werden.
- `REQ-WEB-081`
  Im Bereich `Objektverwaltung` muss die Aktion zur Formularanzeige als `Objekt erzeugen` benannt sein.
- `REQ-WEB-082`
  Im Bereich `Kostenverwaltung` muss die Aktion zur Formularanzeige als `Kostenposten erzeugen` benannt sein.
- `REQ-WEB-083`
  Im Bereich `Mieterverwaltung` müssen die Aktionen zur Formularanzeige kontextabhängig als `Mieter erzeugen` und `Mietvertrag erzeugen` benannt sein.
- `REQ-WEB-084`
  Die React-Weboberfläche muss in mehreren lokal ausgelieferten JavaScript-Dateien strukturiert sein, wobei mindestens eine Datei die App-Orchestrierung und mindestens eine weitere Datei wiederverwendbare Hilfs- oder Diagrammfunktionen kapselt.
- `REQ-WEB-085`
  Die React-Weboberfläche muss fachliche Hilfslogik und Diagramm-Komponenten in getrennten lokalen JavaScript-Dateien kapseln, sodass `app_main.js` nicht die zentrale Stelle für beide Verantwortlichkeiten bleibt.
- `REQ-WEB-086`
  Die React-Weboberfläche muss die Bereichs- und Seitenlayouts für Übersicht, Einstellungen und Verwaltungsansichten in einem separaten lokalen UI-Modul kapseln, sodass `app_main.js` nicht zugleich App-Orchestrierung und komplette Seitenstruktur enthält.
- `REQ-WEB-087`
  Die React-Weboberfläche muss Erfassungs- und Bearbeitungsformulare für Objekte, Kosten, Zähler, Mieter und Mietverträge in einem separaten lokalen Formular-Modul kapseln, sodass `app_main.js` nicht die vollständige Formularstruktur enthält.
- `REQ-WEB-088`
  Die React-Weboberfläche muss Listen-, Tabellen- und Vorschauaufbereitungen für Übersichten, Objektlisten, Kostenlisten und Zählerhistorien in einem separaten lokalen Modul kapseln, sodass `app_main.js` nicht zugleich die vollständige Listen- und Preview-Struktur enthält.
- `REQ-WEB-089`
  Im Bearbeitungspanel einer Kostenposition muss zusätzlich zum Dateiupload ein Feld zur manuellen Eingabe einer vorhandenen Paperless-Dokument-ID verfügbar sein, damit bestehende Paperless-Dokumente ohne erneuten Upload mit dem Kostenposten verknüpft werden können.
- `REQ-WEB-090`
  Dokumente im Bearbeitungspanel einer Kostenposition müssen über einen einheitlichen Öffnen-Workflow verfügbar sein: Sobald eine Paperless-Dokument-ID vorhanden ist, soll dieselbe Öffnen-Logik wie bei hochgeladenen und bereits nach Paperless referenzierten Dokumenten greifen, und lokal gespeicherte Dateien sollen nach Möglichkeit direkt im Browser statt als erzwungener Download geöffnet werden.
- `REQ-WEB-091`
  Wenn ein Dokument nur über eine vorhandene Paperless-Dokument-ID referenziert ist, muss der Abruf über EasyPrent serverseitig mit den hinterlegten Paperless-Zugangsdaten erfolgen, damit Benutzer das Dokument öffnen können, ohne selbst direkt bei Paperless angemeldet zu sein.
- `REQ-WEB-092`
  Im Bearbeitungspanel einer Kostenposition müssen bereits verknüpfte Dokumente wieder gelöscht werden können, unabhängig davon, ob sie hochgeladen oder per vorhandener Paperless-Dokument-ID referenziert wurden.
- `REQ-WEB-093`
  In den Bereichen `Objektverwaltung` und `Mieterverwaltung` muss die Bearbeitungsmaske für einen per Klick gewählten Eintrag direkt unterhalb der zugehörigen Listenzeile eingeblendet werden.
- `REQ-WEB-094`
  Die Verwaltungslisten für Objekte, Mieter, Mietverträge und Kosten sollen einen konsistenten Inline-Listen- und Bearbeitungsmechanismus über wiederverwendbare React-Bausteine nutzen, damit Auswahl, Einblendung und Bearbeitung tabübergreifend gleich funktionieren.
- `REQ-WEB-095`
  Im Tab `Einstellungen` muss eine persistente Umschaltoption verfügbar sein, mit der Löschaktionen in der Benutzeroberfläche global ein- oder ausgeblendet werden können.
- `REQ-WEB-096`
  Im Bearbeitungspanel eines Mieters und eines Mietvertrags muss derselbe Dokument-Workflow wie bei Kostenpositionen verfügbar sein: mehrfache Dateiauswahl, Upload, manuelle Verknüpfung über eine vorhandene Paperless-Dokument-ID, Listenanzeige, Öffnen und Löschen bereits verknüpfter Dokumente.
- `REQ-WEB-097`
  Die gemeinsame Objektliste in der `Objektverwaltung` muss Eltern- und Kindbeziehungen der Objekte erkennbar darstellen, mindestens über hierarchische Reihenfolge sowie Angaben zu übergeordneten und untergeordneten Objekten.
- `REQ-WEB-098`
  Im Tab `Einstellungen` muss ein Datenexport verfügbar sein, der den aktuellen Anwendungsdatenbestand als portable Sicherungsdatei bereitstellt.
- `REQ-WEB-099`
  Im Tab `Einstellungen` muss ein Datenimport verfügbar sein, der eine zuvor exportierte Sicherungsdatei einlesen und den aktuellen Anwendungsdatenbestand damit vollständig ersetzen kann.
- `REQ-WEB-100`
  Der Datenexport und Datenimport dürfen keine Integrationskonfigurationen mit Zugangsdaten enthalten; insbesondere gespeicherte Paperless-URLs und API-Tokens dürfen nicht Bestandteil einer exportierten Sicherungsdatei sein und bei einem Import nicht wiederhergestellt werden.
- `REQ-WEB-101`
  Exportierte und importierte Dokumentdaten dürfen nur referenzierte Paperless-Dokumente als Metadaten und Referenzinformationen enthalten; lokal gespeicherte Dokumentinhalte dürfen weder exportiert noch importiert werden.
- `REQ-WEB-102`
  Dokument-Uploads für Kostenpositionen, Mieter und Mietverträge müssen bei Datei-Uploads eine konfigurierte Paperless-Integration voraussetzen und nach dem Upload nur Metadaten sowie Paperless-Referenzen speichern; lokale Dokumentinhalte dürfen in der Anwendungsdatenbank nicht dauerhaft abgelegt werden.
- `REQ-WEB-055`
  Im Kostenformular darf kein separates Feld `Kostenbezeichnung` angezeigt werden; die Bezeichnung soll aus der Kostenart abgeleitet werden können.
- `REQ-WEB-056`
  In der Kostenliste muss ein Filter nach Zielobjekt verfügbar sein.
- `REQ-WEB-057`
  In der Kostenliste muss ein Filter nach Kostenart verfügbar sein.
- `REQ-WEB-058`
  Wenn in der Kostenliste ein Zielobjektfilter, ein Kostenartfilter oder beide gesetzt sind, dürfen nur passende Kostenpositionen angezeigt werden.

### Verwaltung von Immobilien

- `REQ-PROP-001`
  Das System muss Immobilien anlegen und verwalten können.
- `REQ-PROP-002`
  Das System muss eine Immobilie in Gebäude strukturieren können.
- `REQ-PROP-003`
  Das System muss Gebäude in Einheiten strukturieren können.
- `REQ-PROP-004`
  Das System muss Stammdaten einer Immobilie speichern können, mindestens Name, Adresse, Ort und Postleitzahl.
- `REQ-PROP-005`
  Das System muss Stammdaten einer Einheit speichern können, mindestens Bezeichnung, Fläche und Zimmeranzahl.
- `REQ-PROP-006`
  Ein Gebäude darf einer Immobilie zugeordnet sein, muss aber auch ohne übergeordnete Immobilie anlegbar sein.
- `REQ-PROP-007`
  Eine Wohnung darf einem Gebäude zugeordnet sein, muss aber auch ohne übergeordnetes Gebäude anlegbar sein.
- `REQ-PROP-008`
  Das System muss Zimmer als eigene Objektart verwalten können.
- `REQ-PROP-009`
  Ein Zimmer muss immer genau einer Wohnung zugeordnet sein und darf nicht standalone angelegt werden.
- `REQ-PROP-010`
  Das System muss Gebäude über die Web-Oberfläche anlegen können.
- `REQ-PROP-011`
  Das System muss Wohnungen über die Web-Oberfläche anlegen können.
- `REQ-PROP-012`
  Das System muss Zimmer über die Web-Oberfläche anlegen können.
- `REQ-PROP-013`
  Gebäude müssen eigene Adressdaten speichern können, mindestens Straße, Ort und Postleitzahl.
- `REQ-PROP-014`
  Wohnungen müssen eigene Adressdaten speichern können, mindestens Straße, Ort und Postleitzahl.
- `REQ-PROP-015`
  Die Anzahl der einer Wohnung zugeordneten Zimmerobjekte darf die in der Wohnung hinterlegte Zimmeranzahl nicht überschreiten.
- `REQ-PROP-016`
  Anlagen, Gebäude, Wohnungen und Zimmer müssen archiviert werden können.
- `REQ-PROP-017`
  Anlagen, Gebäude, Wohnungen und Zimmer dürfen nur gelöscht werden, wenn sie zuvor archiviert wurden.
- `REQ-PROP-018`
  Das System muss Zähler als eigene Objektart verwalten können.
- `REQ-PROP-019`
  Ein Zähler muss einer unterstützten Objektart und einem konkreten Objekt zugeordnet werden können, mindestens `property`, `building`, `unit` oder `room`.
- `REQ-PROP-020`
  Ein Zähler muss mindestens Bezeichnung und Messeinheit speichern können.
- `REQ-PROP-021`
  Das System muss Zählerstände mit Zählerbezug, Ablesedatum und Zählerstand speichern können.
- `REQ-PROP-022`
  Zähler müssen archiviert werden können und dürfen nur nach vorheriger Archivierung gelöscht werden.
- `REQ-PROP-023`
  Zählerstände eines Zählers müssen mit der Zeit gleichbleibend oder steigen.
- `REQ-PROP-024`
  Beim Erfassen eines Zählerstands muss der Wert mindestens so groß wie jeder frühere und höchstens so groß wie jeder spätere Zählerstand desselben Zählers sein.
- `REQ-PROP-025`
  Pro Zähler und Ablesedatum darf höchstens ein Zählerstand gespeichert werden.
- `REQ-PROP-026`
  Zählerstände müssen einzeln gelöscht werden können, um fehlerhafte Erfassungen zu korrigieren.
- `REQ-PROP-027`
  Zimmer müssen eine eigene Wohnfläche speichern können.

### Verwaltung von Mietern und Mietverträgen

- `REQ-LEASE-001`
  Das System muss Mieter mit Stammdaten anlegen und verwalten können.
- `REQ-LEASE-002`
  Das System muss Mietverträge einer Einheit zuordnen können.
- `REQ-LEASE-003`
  Ein Mietvertrag muss mindestens Startdatum, optionales Enddatum, Kaltmiete, Nebenkostenvorauszahlung und Personenzahl speichern können.
- `REQ-LEASE-004`
  Das System muss den Bezug zwischen Mieter, Mietvertrag und Einheit eindeutig herstellen können.
- `REQ-LEASE-005`
  Vertragsdaten und Objektzuordnung müssen historisch nachvollziehbar gespeichert werden.
- `REQ-LEASE-006`
  Das System muss Mieter löschen können, sofern keine Mietverträge auf den Mieter verweisen.
- `REQ-LEASE-007`
  Das System muss Mietverträge löschen können.
- `REQ-LEASE-008`
  Ein Mietvertrag muss optional einem Zimmer zugeordnet werden können; dabei muss die übergeordnete Wohnung weiterhin eindeutig erhalten bleiben.
- `REQ-LEASE-009`
  Ein Mieter muss mit einem oder mehreren Dokumenten verknüpft werden können, insbesondere für Identitätsdokumente wie Reisepass oder Personalausweis.
- `REQ-LEASE-010`
  Ein Mietvertrag muss mit einem oder mehreren Dokumenten verknüpft werden können, einschließlich referenzierter Paperless-Dokumente.

### Nebenkostenabrechnung als MVP

- `REQ-NKA-001`
  Das System muss umlagefähige Kosten für einen Abrechnungszeitraum erfassen können.
- `REQ-NKA-002`
  Eine Kostenposition muss mindestens Bezeichnung, Betrag, Zeitraum und Verteilerschlüssel speichern können.
- `REQ-NKA-002A`
  Eine Kostenposition muss einen Kostentyp speichern können.
- `REQ-NKA-002B`
  Im MVP müssen mindestens die Kostentypen `total`, `monthly`, `yearly` und `consumption` unterstützt werden.
- `REQ-NKA-003`
  Das System muss Verteilerschlüssel auf Kostenpositionen anwenden können.
- `REQ-NKA-004`
  Im MVP müssen mindestens die Verteilerschlüssel `area`, `unit_count` und `occupants` unterstützt werden.
- `REQ-NKA-005`
  Das System muss für einen definierten Zeitraum eine Nebenkostenabrechnung pro Mietverhältnis erzeugen können.
- `REQ-NKA-006`
  Das System muss Nebenkostenvorauszahlungen in der Abrechnung berücksichtigen können.
- `REQ-NKA-007`
  Das System muss das Ergebnis je Mietverhältnis als Nachzahlung oder Guthaben ausweisen können.
- `REQ-NKA-008`
  Das System muss die Kostenverteilung nachvollziehbar je Kostenposition darstellen können.
- `REQ-NKA-009`
  Bei monatlichen Kosten muss der Abrechnungsbetrag für den ausgewählten Zeitraum monatsgenau aus dem Monatsbetrag ermittelt werden.
- `REQ-NKA-010`
  Bei `Gesamtkosten` muss der Abrechnungsbetrag entsprechend dem hinterlegten Kostenzeitraum im passenden Abrechnungszeitraum berücksichtigt werden.
- `REQ-NKA-011`
  Verbrauchsbezogene Kosten müssen mit Verbrauchsinformationen erfassbar sein.
- `REQ-NKA-012`
  Verbrauchsbezogene Kosten müssen in der Abrechnung mit ihrem erfassten Gesamtbetrag berücksichtigt werden können.
- `REQ-NKA-013`
  Kosten müssen als `Gesamtkosten` oder wiederholend erfassbar sein.
- `REQ-NKA-014`
  Wiederholende Kosten müssen mindestens mit den Intervallen `monthly` und `yearly` erfassbar sein.
- `REQ-NKA-015`
  Der Kosten-Erfassungsbereich muss mindestens die Felder Kostenart, Wert, Wiederholungsart, Intervall, Von-Datum und ein optionales Bis-Datum für wiederholende Kosten bereitstellen.
- `REQ-NKA-016`
  Kostenpositionen müssen archiviert werden können.
- `REQ-NKA-017`
  Kostenpositionen dürfen nur gelöscht werden, wenn sie zuvor archiviert wurden.
- `REQ-NKA-018`
  Kostenpositionen müssen einer Objektart und einem konkreten Objekt zugeordnet werden können, mindestens `property`, `building`, `unit` oder `room`.
- `REQ-NKA-019`
  Die Kostenzuordnung muss mindestens die Felder `object_type` und `object_id` speichern können.
- `REQ-NKA-020`
  `Gesamtkosten` müssen einen Zeitraum mit `period_start` und `period_end` speichern.
- `REQ-NKA-021`
  Wiederholende Kosten müssen mindestens `period_start` speichern und können optional mit `period_end` begrenzt werden.
- `REQ-NKA-022`
  Verbrauchsbezogene Kosten müssen mindestens eine Verbrauchseinheit speichern können.
- `REQ-NKA-023`
  Verbrauchsbezogene Kosten müssen alternativ zu einer direkt eingegebenen Verbrauchseinheit einem Zähler zugeordnet werden können.
- `REQ-NKA-024`
  Die Kostenstruktur muss für zählerbezogene Verbrauchskosten mindestens das Feld `meter_id` speichern können.
- `REQ-NKA-025`
  Für verbrauchsbezogene Kosten muss entweder eine Verbrauchseinheit oder ein Zähler angegeben werden.
- `REQ-NKA-026`
  Wenn eine verbrauchsbezogene Kostenposition einem Zähler zugeordnet wird, muss die zugehörige Messeinheit des Zählers für die Kostenposition verfügbar sein.
- `REQ-NKA-027`
  Kostenpositionen müssen nach ihrer Anlage fachlich bearbeitet werden können.
- `REQ-NKA-028`
  Für das Bearbeiten von Kostenpositionen müssen dieselben Validierungen und Pflichtfelder gelten wie beim Anlegen.
- `REQ-NKA-029`
  Das Bearbeiten einer Kostenposition über die Benutzeroberfläche muss mit einem gemeinsamen Zielobjekt-Feld möglich sein, das die unterstützten Objektarten in einer Auswahl zusammenfasst.
- `REQ-NKA-030`
  Eine Kostenposition muss zusätzlich zur Bezeichnung eine fachliche Kostenart speichern können.
- `REQ-NKA-031`
  Eine Kostenposition muss einen Empfänger oder Begünstigten speichern können.
- `REQ-NKA-032`
  Das System muss aus vorhandenen Kostenpositionen wiederverwendbare Kombinationen aus Kostenart und Empfänger für die erneute Erfassung ableiten können.
- `REQ-NKA-033`
  Eine archivierte Kostenposition muss wieder in einen aktiven Zustand zurückgesetzt werden können.
- `REQ-NKA-034`
  Für verbrauchsbezogene Kosten mit zugeordnetem Zähler und abweichender Verbrauchseinheit muss ein Umrechnungsfaktor speicherbar sein.
- `REQ-NKA-035`
  Bei verbrauchsbezogenen Kosten mit zugeordnetem Zähler darf ein manuell übergebener Verbrauchswert nicht fachlich verwendet werden.
- `REQ-NKA-036`
  Bei verbrauchsbezogenen Kosten ohne Zähler muss der Verbrauchswert direkt erfasst und gespeichert werden können.
- `REQ-NKA-037`
  Für verbrauchsbezogene Kosten muss aus Preis je Einheit, Verbrauchsmenge und optionalem Umrechnungsfaktor eine Gesamtsumme berechnet werden können.
- `REQ-NKA-038`
  Bei zählerbezogenen Verbrauchskosten muss die Verbrauchsmenge aus den Zählerständen im Kostenzeitraum abgeleitet werden können.
- `REQ-NKA-039`
  Liegen für Anfang oder Ende des Kostenzeitraums keine exakten Zählerstände vor, darf die abzuleitende Verbrauchsmenge linear aus den benachbarten Zählerständen interpoliert werden.
- `REQ-NKA-040`
  Die berechnete Gesamtsumme einer Kostenposition muss für wiederholende Kosten tagesgenau anhand der tatsächlichen Überlappungstage innerhalb des Kostenzeitraums ermittelt werden.
- `REQ-NKA-041`
  Kostenwerte müssen als EUR-Beträge verarbeitet werden; Kostenbeträge dürfen mit bis zu zehn Nachkommastellen erfasst werden.
- `REQ-NKA-042`
  Bei verbrauchsbezogenen Kosten muss der Preis je Einheit mit bis zu zehn Nachkommastellen erfassbar und berechenbar sein.
- `REQ-NKA-043`
  Wenn beim Anlegen oder Bearbeiten einer Kostenposition keine explizite Kostenbezeichnung übergeben wird, muss automatisch die Kostenart als Bezeichnung gespeichert werden.
- `REQ-NKA-044`
  Bei jährlich wiederholenden Kosten muss die tagesgenaue Verteilung auf einem jahresweisen Kostenzyklus basieren, der am `period_start` der Kostenposition verankert ist; ein vollständig abgedeckter Jahreszyklus muss genau den Jahresbetrag ergeben.
- `REQ-NKA-045`
  Für `Gesamtkosten` muss der Zeitraum (`period_start` und `period_end`) verpflichtend gespeichert werden.

### Objektlebenszyklus

- `REQ-LIFE-001`
  Für alle Objektarten mit Archivierungsfunktion muss die Archivierung fachlich rückgängig gemacht werden können.
- `REQ-LIFE-002`
  Das Rückgängigmachen einer Archivierung muss den Archivstatus entfernen und den Archivzeitpunkt leeren.

### Abschreibungsverwaltung

- `REQ-DEPR-001`
  Das System muss abschreibungsrelevante Objektdaten erfassen und speichern können.
- `REQ-DEPR-002`
  Ein Abschreibungsobjekt muss mindestens Bezeichnung, Anschaffungskosten, Gebäudewertanteil, Nutzungsdauer, Inbetriebnahmedatum und Methode speichern können.
- `REQ-DEPR-003`
  Das System muss für ein Jahr einen Abschreibungswert berechnen können.
- `REQ-DEPR-004`
  Im MVP muss mindestens die lineare Abschreibung unterstützt werden.
- `REQ-DEPR-005`
  Die Abschreibung muss monatsgenau anteilig berechnet werden können, wenn ein Objekt nicht zum Jahresanfang in Betrieb genommen wurde.
- `REQ-DEPR-006`
  Die Datenstruktur muss eine spätere Erweiterung um zusätzliche steuerliche Abschreibungslogik ermöglichen.

### Mehrbenutzerfähigkeit und Rollenmodell

- `REQ-ROLE-001`
  Das System muss Organisationen als fachliche Mandanten abbilden können.
- `REQ-ROLE-002`
  Das System muss Nutzer einer Organisation zuordnen können.
- `REQ-ROLE-003`
  Das System muss Rollen je Organisationszuordnung speichern können.
- `REQ-ROLE-004`
  Im MVP muss die fachliche Grundlage für Mehrbenutzerfähigkeit vorhanden sein, auch wenn noch keine Anmeldung implementiert ist.

## Nicht-funktionale Anforderungen

- `NFR-001`
  Die Anwendung soll als Web-Anwendung zentral deploybar sein.
- `NFR-002`
  Die fachlichen Anforderungen sollen so beschrieben sein, dass daraus Testfälle mit eindeutiger Rückverfolgbarkeit erstellt werden können.
- `NFR-003`
  Die wichtigsten Berechnungen für Nebenkosten und Abschreibung sollen automatisiert testbar sein.
- `NFR-004`
  Die OpenAPI-Beschreibung soll unter einem stabilen JSON-Endpunkt bereitgestellt werden.
- `NFR-005`
  Die Web-Oberfläche soll auch ohne Internetzugriff auf externe JavaScript-CDNs starten können.
- `NFR-006`
  Zeit- und verbrauchsbezogene Kostenberechnungslogik soll in einem dedizierten Fachmodul gekapselt werden, damit Wiederverwendung und Wartbarkeit verbessert werden.

## Fachliche Datenstrukturen

- Immobilienstruktur:
  Objekt -> Gebäude -> Wohnung
- Zimmerstruktur:
  Wohnung -> Zimmer
- Zählerstruktur:
  Objekt -> Zähler -> Zählerstände
- Vertragsstruktur:
  Mieter -> Mietvertrag -> Einheit
- Abrechnungsstruktur:
  Abrechnungszeitraum -> Kostenart -> Verteilerschlüssel -> Ergebnis je Vertrag oder Einheit
- Abschreibungsstruktur:
  Abschreibungsobjekt -> Anschaffungsdaten -> Regel -> Jahreswerte

## Bewusst außerhalb des MVP

- `OUT-001`
  Keine vollständige Finanzbuchhaltung
- `OUT-002`
  Keine Benutzeranmeldung
- `OUT-003`
  Keine automatische OCR-Klassifikation oder fachliche Dokumentanalyse für hochgeladene Unterlagen
- `OUT-004`
  Keine komplexen Sonderfälle der Nebenkostenabrechnung
- `OUT-005`
  Keine vollständige steuerliche Speziallogik für Abschreibung

## Abnahmeorientierte Prüfpunkte

- `ACC-001`
  Die Anforderungen `REQ-PROP-001` bis `REQ-PROP-027` sind erfüllt, wenn Immobilien, Gebäude, Wohnungen, Zimmer und Zähler konsistent angelegt, mit den erforderlichen Adress- und Stammdaten einschließlich eigener Zimmer-Wohnflächen gespeichert, gemäß ihrer erlaubten Pflicht- und Optionalbeziehungen verknüpft, in ihrer maximal zulässigen Zimmeranzahl pro Wohnung begrenzt, Zählerstände erfassbar, pro Datum eindeutig und über die Zeit gleichbleibend oder steigend gespeichert, bei Bedarf gezielt wieder gelöscht, archiviert und erst nach der Archivierung gelöscht sowie über die Web-Oberfläche angelegt werden können.
- `ACC-002`
  Die Anforderungen `REQ-LEASE-001` bis `REQ-LEASE-010` sind erfüllt, wenn Mieter und Mietverträge Wohnungen eindeutig zugeordnet werden können, Mietverträge optional zusätzlich einem Zimmer innerhalb der Wohnung zugeordnet werden können, Mieter ohne referenzierende Mietverträge gezielt gelöscht werden können, Mietverträge selbst ebenfalls gezielt gelöscht werden können und sowohl Mieter als auch Mietverträge mit einem oder mehreren Dokumenten einschließlich referenzierter Paperless-Dokumente verknüpft werden können.
- `ACC-003`
  Die Anforderungen `REQ-NKA-001` bis `REQ-NKA-045` sind erfüllt, wenn für einen definierten Zeitraum eine nachvollziehbare Nebenkostenabrechnung mit Vorauszahlungen, Saldo und den Kostentypen `total`, `monthly`, `yearly` und `consumption` erzeugt werden kann, Kostenpositionen Objekten der unterstützten Objektarten zugeordnet, gemäß ihrer Typlogik mit verpflichtendem Zeitraum bei Gesamtkosten, offenem oder begrenztem Zeitraum bei wiederholenden Kosten, Verbrauchseinheit oder Zählerbezug erfasst, um Kostenart, Empfänger und Bezeichnung fachlich ergänzt, aus vorhandenen Kombinationen wiederverwendbar vorgeschlagen, nachträglich mit denselben fachlichen Regeln bearbeitet sowie archiviert und erst nach der Archivierung gelöscht werden können, die berechnete Gesamtsumme wiederholender Kosten tagesgenau über die tatsächliche Zeitüberlappung ermittelt wird, jährlich wiederholende Kosten einen am Startdatum verankerten Jahreszyklus für die tagesgenaue Verteilung nutzen, EUR-Präzisionsregeln für Beträge und Verbrauchspreise eingehalten werden und fehlende Bezeichnungen automatisch aus der Kostenart abgeleitet werden.
- `ACC-004`
  Die Anforderungen `REQ-DEPR-001` bis `REQ-DEPR-006` sind erfüllt, wenn Abschreibungsdaten vollständig erfasst und Jahreswerte berechnet werden können.
- `ACC-005`
  Die Anforderungen `REQ-WEB-001` bis `REQ-WEB-102` sowie `NFR-001`, `NFR-004` und `NFR-005` sind erfüllt, wenn die Anwendung zentral bereitgestellt, per Browser über eine lokal ausgelieferte React-Oberfläche mit getrennten Haupt-Tabs für Übersicht, Objektverwaltung, Kostenverwaltung, Mieterverwaltung und Einstellungen genutzt werden kann, die ausgelieferten Frontend-Skripte syntaktisch gültig sind, die React-Oberfläche über mehrere lokale JavaScript-Dateien mit getrennter App-Orchestrierung, fachlicher Hilfslogik, Diagramm-Komponenten, Bereichs-Layouts, Formular-Modulen und Listen-/Preview-Modulen ausgeliefert wird, die gemeinsame Objektliste in der Objektverwaltung alle Anlagen, Gebäude, Wohnungen und Zimmer mit den geforderten Beziehungs- und Detailinformationen einschließlich Eltern-/Kindrelation zeigt, Archivieren, Wiederherstellen und Löschen für unterstützte Objektarten bereitstellt, die Untertabs `Kosten` und `Zähler` im Haupt-Tab `Kostenverwaltung` geführt werden, der Zählerbereich Zähler und Zählerstände erfassen, einzelne Zählerstände löschen, die vollständige Historie eines ausgewählten Zählers anzeigen sowie dessen Entwicklung als umschaltbares Monats- oder Jahresdiagramm in kumulierter oder Säulendarstellung mit linearer oder quadratischer Interpolation visualisieren lässt, einen frei wählbaren Zeitraum mit einem Standard von 12 Monaten rückwirkend bereitstellt, die Zählerentwicklung über ein professionelles Chart-Framework mit Tooltip visualisiert und Zeitraum-Eingaben auch bei untermonatlichen oder unterjährigen Bereichen wirksam in die dargestellten Werte einbezieht, die Y-Achse der Zählerentwicklung absolute Werte mit automatischer Skalierung ohne manuellen Y-Slider zeigt, der Kostenbereich eine konfigurierbare Kostenentwicklung mit Zeitraum-, Granularitäts- und Diagrammtyp-Optionen sowie Filtern nach Zielobjekt und Kostenart bereitstellt, die Kostenzusammensetzung im Säulendiagramm farblich nach Kostenarten hervorhebt, die Kostenübersicht der Hauptansicht Kostenpositionen nach Enddatum absteigend sortiert darstellt, Gesamtkosten im Formular als Zeitraum ohne separates Einzeldatum erfassen kann, der Haupt-Tab `Mieterverwaltung` die Untertabs `Mieter` und `Mietverträge` mit Erfassungsmasken und Listen bereitstellt, Objekt- und Mieterlisten textbasiert filterbar sind, Einträge per Klick in einen Bearbeitungsmodus wechseln und gespeichert werden können, Erfassungsformulare je Verwaltungstab initial ausgeblendet und erst auf expliziten Klick angezeigt werden, die Formularaktionen als `Objekt erzeugen`, `Kostenposten erzeugen`, `Mieter erzeugen` und `Mietvertrag erzeugen` benannt sind, ein eigener Einstellungs-Tab die Pflege von Paperless-URL und API-Token ermöglicht und gespeicherte Tokens maskiert bis auf die letzten 4 Zeichen anzeigt, die Erreichbarkeit des Servers beim Laden sichtbar prüft, zusätzlich eine persistente Umschaltoption zum Ein- oder Ausblenden von Löschaktionen bereitstellt und bei deaktivierter Option alle Löschaktionen in der Oberfläche ausblendet, im Einstellungs-Tab einen Datenexport als portable Sicherungsdatei sowie einen Datenimport zum vollständigen Wiederherstellen eines zuvor exportierten Datenbestands anbietet, solche Sicherungen aber keine Integrationszugangsdaten enthalten und referenzierte Paperless-Dokumente nur als Metadaten ohne lokale Dateiinhalte transportieren, das Kosten-Bearbeitungspanel Mehrfach-Uploads von Dokumenten unterstützt, hochgeladene Dokumente kostenpostenbezogen listet und bereitstellt, zusätzlich vorhandene Paperless-Dokumente per manueller Dokument-ID mit Kostenposten verknüpfen kann, solche Dokumentverknüpfungen bei Bedarf wieder löschen kann, ab Vorliegen einer Paperless-Dokument-ID denselben Öffnen-Workflow wie andere referenzierte Dokumente nutzt, lokal gespeicherte Dateien nach Möglichkeit direkt im Browser öffnet statt einen erzwungenen Download auszulösen, referenzierte Paperless-Dokumente serverseitig über die hinterlegten Zugangsdaten proxyt statt einen direkten Login beim Benutzer vorauszusetzen, bei Datei-Uploads eine konfigurierte Paperless-Integration voraussetzt, dabei nur Dokumentreferenzen statt lokaler Blob-Inhalte speichert, dieselbe Dokumentlogik auch in den Bearbeitungspanels von Mietern und Mietverträgen anbietet, die Kostenvorschau keinen abgeleiteten Anlagenbezug zeigt, aktive Kostenpositionen direkt unterhalb der ausgewählten Zeile per Klick inline bearbeitbar sind, Objekt-, Mieter- und Mietvertragslisten die Bearbeitung direkt unterhalb der ausgewählten Zeile einblenden, dafür einen tabübergreifend konsistenten wiederverwendbaren Inline-Listen- und Bearbeitungsmechanismus nutzen, die Archivierungsaktion für aktive Kosten nur in der Bearbeitungsmaske zeigt, archivierte Objekte wiederherstellen kann, die Kostenauflistung Kostenart, Empfänger und Abrechnungsart klar voneinander trennt, sprechende Spaltenbezeichnungen statt des missverständlichen Begriffs `Typ` verwendet, kein separates Bezeichnungsfeld im Kostenformular anzeigt, Kostenarten direkt im Feld `Kostenart` vorschlägt, kein separates Vorschlagsfeld für Kostenarten anzeigt, Kostenlisten nach Zielobjekt und Kostenart filterbar macht und bei gesetzten Filtern nur passende Positionen darstellt, verbrauchsbezogene Kosten je nach Zählerbezug nur die passenden Eingabefelder zeigen, Umrechnungsfaktoren für abweichende Verbrauchseinheiten berücksichtigen, berechnete Gesamtsummen sichtbar machen, erfasste Messpunkte in der Zählerentwicklung eindeutig markieren, interpolierte Periodenpunkte visuell absetzen und die API über eine OpenAPI-JSON-Beschreibung nachvollziehbar dokumentiert wird.
- `ACC-006`
  Die Anforderung `NFR-006` ist erfüllt, wenn die Zeit- und Verbrauchslogik für Kostenperioden in einem separaten Python-Modul implementiert ist und dafür isolierte Unit-Tests für Überlappung, tagesgenaue Verteilung und Zählerinterpolation existieren.

## Offene Fachfragen

- Welche Rollen werden in Version 1 wirklich benötigt?
- Welche Sonderfälle in der Nebenkostenabrechnung haben Priorität?
- Welche Abschreibungsarten sollen nach dem MVP unterstützt werden?
- Welche Auswertungen oder Exporte werden zuerst benötigt?
