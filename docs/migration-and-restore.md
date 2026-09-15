# Migration dry run, cutover, and restore

Use the CLI only for the [frozen Legacy schema](legacy-schema-inventory.md).
The current WSGI application entry still uses the Legacy schema and rejects a
version-1 database; deploy the later application cutover before activating v1
for a running installation. Commands below accept `--database` or use the
configured `EASYPRENT_DB_PATH`. They require the CLI/server and systemd service
to be stopped for cutover and restore.

Run a complete rehearsal first:

```bash
python3 -m easyprent_accounting.cli migrate \
  --database /path/to/easyprent_accounting.db \
  --dry-run --report /path/to/migration-dry-run.json
```

The command checks the source fingerprint before writing any sidecar, makes a
dated SQLite Backup API snapshot, restores that snapshot to a temporary proof
database, migrates into a separate staging database, and validates it. The
active file is unchanged; the staging file is removed. The verified dated
backup remains. Inspect `success`, `schema_version.target`, `table_counts`,
`foreign_key_check`, `integrity_check`, `checksums`, and `monetary_totals` in
the JSON report. A failed migration writes `success: false` and error codes.

With the application stopped, activate only after a successful dry run:

```bash
python3 -m easyprent_accounting.cli migrate \
  --database /path/to/easyprent_accounting.db \
  --cutover --report /path/to/migration-cutover.json
```

This repeats backup, transformation, and validation from the unchanged Legacy
source. It confirms the active file still matches its backup, then atomically
renames the validated staging database over the active path. The dated Legacy
backup path is recorded in `backup_path` and retained. A target path supplied
with `--target` must be an unused file beside the active database. Unknown
fingerprints, insufficient storage, existing targets, failed validation, and
failed activation leave the active file untouched.

Restore that exact backup if needed:

```bash
python3 -m easyprent_accounting.cli restore \
  --backup /path/to/easyprent_accounting.db.legacy-backup-DATE-ID.db \
  --database /path/to/easyprent_accounting.db \
  --report /path/to/migration-restore.json
```

Restore verifies the backup, creates and checks a separate restored staging
database, retains a dated `pre-restore` backup of any active database, and
atomically replaces the active path. `pre_restore_backup` in the restore report
records that retained v1 state. The end-to-end test performs dry run, cutover,
and restore from the same fully synthetic Legacy fixture.
