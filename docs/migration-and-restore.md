# Migration dry run, cutover, and restore

Use the CLI only for the [frozen Legacy schema](legacy-schema-inventory.md).
The ASGI application requires schema version 1. It rejects a Legacy database
with an explicit migration instruction and never changes that schema during
startup. Commands below accept `--database` or use the configured
`EASYPRENT_DB_PATH`. Stop the CLI/server and systemd service before cutover
or restore.

From the intended non-privileged installation owner, run `./install.sh
--dry-run` before deployment. The script builds and checks the wheel, validates
the actual install path and systemd unit, and inspects the database. For a
Legacy database it runs the complete migration dry run below and prints the
retained JSON report and verified backup paths. It installs no package or
service and does not activate the target database. A normal `./install.sh`
refuses a Legacy database until the explicit cutover is complete. A fresh
database or a valid v1 database passes the schema preflight directly.

Run a complete rehearsal first:

```bash
python3 -m easyprent_accounting.cli migrate \
  --database /path/to/easyprent_accounting.db \
  --dry-run --report /path/to/migration-dry-run.json
```

The command checks the source fingerprint before creating a backup or staging
database, makes a
dated SQLite Backup API snapshot, restores that snapshot to a temporary proof
database, migrates into a separate staging database, and validates it. The
active file is unchanged; the staging file is removed. The verified dated
backup remains. Inspect `success`, `schema_version.target`, `table_counts`,
`foreign_key_check`, `integrity_check`, `checksums`, and `monetary_totals` in
the JSON report. If `--report` is omitted, the CLI creates a dated report
beside the database and prints its path. An unknown fingerprint or failed
migration writes `success: false` and error codes to that report without
changing the source database.

With the application stopped, activate only after a successful dry run:

```bash
python3 -m easyprent_accounting.cli migrate \
  --database /path/to/easyprent_accounting.db \
  --cutover --report /path/to/migration-cutover.json
```

This repeats backup, transformation, and validation from the unchanged Legacy
source. It writes and syncs the successful validation report before activation;
a report write failure aborts while Legacy stays active. It confirms the active
file still matches its backup, then atomically renames the validated staging
database over the active path. The dated Legacy
backup path is recorded in `backup_path` and retained. A target path supplied
with `--target` must be an unused file beside the active database. Unknown
fingerprints, insufficient storage, existing targets, failed validation, and
failed activation leave the active file untouched.

SQLite WAL mode and existing `-wal`/`-shm` sidecars make a main-file rename
unsafe. Cutover and restore reject that state before activation; a dry run can
still validate a WAL source. Quiesce all database users and use an explicit,
backed-up SQLite maintenance step to checkpoint and leave WAL mode before
retrying. Do not delete WAL sidecars by hand. The migration command itself
only reads the original until the atomic activation.

Restore that exact backup if needed:

```bash
python3 -m easyprent_accounting.cli restore \
  --backup /path/to/easyprent_accounting.db.legacy-backup-DATE-ID.db \
  --database /path/to/easyprent_accounting.db \
  --report /path/to/migration-restore.json
```

Restore verifies the backup, creates and checks a separate restored staging
database, retains a dated `pre-restore` backup of any active database, and
persists its report before atomically replacing the active path.
`pre_restore_backup` in the restore report
records that retained v1 state. The end-to-end test performs dry run, cutover,
and restore from the same fully synthetic Legacy fixture.

After the successful cutover, run `./install.sh --dry-run` again. The preflight
must report `"database_state": "v1"`; then run `./install.sh`. Check
`systemctl status easyprent-accounting.service`, `/api/v1/health`, the
frontend at `/`, and `/openapi.json`. The installed runtime uses Uvicorn and
the packaged Vite files; it does not require Node.js.
