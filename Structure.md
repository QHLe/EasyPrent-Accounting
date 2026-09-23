# Architektur und Projektstruktur

EasyPrent Accounting ist ein modularer Monolith. Python/FastAPI liefert die
HTTP-API und die mit Vite gebaute React-Anwendung aus. SQLite ist der einzige
Persistenzadapter. Node.js wird zum Entwickeln und Bauen benötigt, nicht zum
Starten eines installierten Python-Pakets.

## Verzeichnisse

- `easyprent_accounting/`: Python-Paket mit Fachmodulen, HTTP-Routern,
  Migration, CLI und ASGI-Anwendung.
- `src/`: React/TypeScript-Frontend. Jedes `features/`-Verzeichnis enthält
  Darstellung und lokalen Zustand für einen Fachbereich.
- `tests/`: Python-Verhaltens-, HTTP-, Migrations- und Installationsprüfungen.
- `CONTEXT.md`: gemeinsame fachliche Sprache. Neue Architekturentscheidungen
  werden bei Bedarf unter `docs/adr/` festgehalten.
- `scripts/`: Qualitätslauf, OpenAPI-Export und Vorlagenpflege.
- `easyprent_accounting/static_dist/`: Vite-Produktionsartefakte im Paket.
  Der Wheel-Bau erstellt diese aus `package-lock.json` neu.

## Backend-Grenzen

`server.py` ist der lokale ASGI-Startpunkt. `asgi.py` erzeugt die FastAPI-
Anwendung; `easyprent_accounting.asgi:app` ist der ASGI-Einstieg für einen
Prozessmanager. `config.py` liest Umgebung und konfiguriert die Anwendung an
der Composition Root. Router in `http_*.py` validieren HTTP-Ein- und Ausgaben
mit Pydantic und rufen fachliche Module auf. SQLite-Operationen und
Geschäftsregeln bleiben in den Fachmodulen.

| Fachbereich | Python-Modul | Frontend |
| --- | --- | --- |
| Anlagen, Gebäude, Wohnungen, Zimmer | `asset_registry.py` | `src/features/asset-registry/` |
| Zähler und Messwerte | `metering.py` | `src/features/metering/` |
| Mieter und Mietverträge | `tenancy.py` | `src/features/tenancy/` |
| Kosten und Preise | `expenses.py`, `expense_pricer.py` | `src/features/expenses/` |
| Abrechnungen | `settlements.py`, `settlement_runs.py` | `src/features/settlements/` |
| Verknüpfte Dokumente | `linked_documents.py` | `src/features/linked-documents/` |
| Einstellungen und Datensicherung | `settings.py` | `src/features/settings/` |
| Abschreibung | `depreciation.py` | `src/features/depreciation/` |
| Dashboard | `dashboard.py` | `src/features/dashboard/` |

GnuCash und Paperless werden über Adapter in `integrations/` angebunden.
Die fachlichen Geld- und Abrechnungswerte entstehen im Backend. Das Frontend
zeigt die typisierten Projektionen an. FastAPI generiert `/openapi.json`;
`scripts/export_openapi.py` schreibt daraus `openapi.json`, und
`npm run generate-api` erzeugt `src/api/schema.d.ts`.

## Datenbank und Auslieferung

`schema_runner.py` führt nummerierte Schemaänderungen transaktional mit
`schema_migrations` aus. `migration.py` migriert ausschließlich das
eingefrorene Legacy-Schema in eine neue v1-Datei, validiert sie und aktiviert
sie erst beim expliziten Cutover. Details stehen in
[Migration und Restore](docs/migration-and-restore.md).

`packaging.py` baut aus einer isolierten Quellkopie per `npm ci` und Vite
ein Wheel mit statischen Artefakten. `install.sh` und `deployment.py`
prüfen vor dem systemd-Cutover den tatsächlichen Installationspfad, einen
nicht privilegierten Laufzeitbenutzer und den Datenbankzustand. Der Dienst
startet Uvicorn mit `easyprent_accounting.asgi:app`. Betriebs- und
Änderungsabläufe stehen in [Wartung](docs/maintenance.md).
