from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch
from collections import namedtuple

from easyprent_accounting import cli, migration
from easyprent_accounting.legacy_schema import schema_fingerprint, SUPPORTED_LEGACY_FINGERPRINTS
from tests.legacy_fixture import create_legacy_fixture


class MigrationCliTests(unittest.TestCase):
    def _call(self, arguments: list[str], root: Path) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        environ = {"EASYPRENT_PROJECT_ROOT": str(root), "EASYPRENT_DB_PATH": str(root / "active.db")}
        # These tests migrate a private temporary database, independent of any
        # systemd unit installed on the machine running the suite.
        with patch.dict(os.environ, environ), \
             patch.object(cli, "installed_systemd_unit", return_value=None), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_dry_run_validates_complete_fixture_and_preserves_active_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            report_path = root / "dry-run.json"
            create_legacy_fixture(active)
            before = active.read_bytes()

            code, stdout, stderr = self._call(
                ["migrate", "--database", str(active), "--dry-run", "--report", str(report_path)], root
            )

            self.assertEqual(code, 0, stderr)
            self.assertEqual(active.read_bytes(), before)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["success"], stdout)
            self.assertEqual(report["schema_version"]["target"], 1)
            self.assertTrue(all(entry["match"] for entry in report["table_counts"].values()))
            backup = Path(report["backup_path"])
            self.assertTrue(backup.is_file())
            self.assertEqual(list(root.glob("*.v1-staging-*.db")), [])
            with sqlite3.connect(active) as connection:
                self.assertIn(schema_fingerprint(connection), SUPPORTED_LEGACY_FINGERPRINTS)

    def test_cutover_and_restore_round_trip_the_same_legacy_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            cutover_report = root / "cutover.json"
            restore_report = root / "restore.json"
            create_legacy_fixture(active)
            with sqlite3.connect(active) as source:
                legacy_fingerprint = schema_fingerprint(source)

            code, _, stderr = self._call(
                ["migrate", "--database", str(active), "--cutover", "--report", str(cutover_report)], root
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(cutover_report.read_text(encoding="utf-8"))
            self.assertTrue(report["success"])
            self.assertTrue(report["activated"])
            backup = Path(report["backup_path"])
            self.assertTrue(backup.is_file())
            with sqlite3.connect(active) as upgraded:
                self.assertEqual(upgraded.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 1)
                self.assertEqual(upgraded.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(upgraded.execute("PRAGMA integrity_check").fetchone()[0], "ok")

            code, _, stderr = self._call(
                ["restore", "--backup", str(backup), "--database", str(active), "--report", str(restore_report)], root
            )
            self.assertEqual(code, 0, stderr)
            restored = json.loads(restore_report.read_text(encoding="utf-8"))
            self.assertTrue(restored["success"])
            self.assertTrue(Path(restored["pre_restore_backup"]).is_file())
            with sqlite3.connect(active) as original_again:
                self.assertEqual(schema_fingerprint(original_again), legacy_fingerprint)
                self.assertEqual(original_again.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_insufficient_storage_aborts_before_backup_or_cutover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)
            before = active.read_bytes()
            usage = namedtuple("Usage", "total used free")(1000, 999, 1)

            with patch("easyprent_accounting.migration.shutil.disk_usage", return_value=usage):
                code, _, stderr = self._call(
                    ["migrate", "--database", str(active), "--cutover"], root
                )

            self.assertEqual(code, 1, stderr)
            self.assertEqual(active.read_bytes(), before)
            self.assertEqual(list(root.glob("*.legacy-backup-*.db")), [])

    def test_unknown_schema_is_rejected_without_backup_or_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            report_path = root / "rejected.json"
            create_legacy_fixture(active)
            with sqlite3.connect(active) as altered:
                altered.execute("ALTER TABLE tenants ADD COLUMN unknown_field TEXT")
            before = active.read_bytes()

            code, _, _ = self._call(
                ["migrate", "--database", str(active), "--dry-run", "--report", str(report_path)], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertEqual(list(root.glob("*.legacy-backup-*.db")), [])
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["errors"][0]["code"],
                             "unknown_schema_fingerprint")

    def test_unknown_schema_without_report_flag_writes_dated_failure_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)
            with sqlite3.connect(active) as altered:
                altered.execute("ALTER TABLE tenants ADD COLUMN unknown_field TEXT")
            before = active.read_bytes()

            code, _, stderr = self._call(
                ["migrate", "--database", str(active), "--dry-run"], root
            )

            self.assertEqual(code, 1, stderr)
            self.assertEqual(active.read_bytes(), before)
            self.assertEqual(list(root.glob("*.legacy-backup-*.db")), [])
            reports = list(root.glob("active.db.migration-report-*.json"))
            self.assertEqual(len(reports), 1)
            self.assertIn(str(reports[0]), stderr)
            self.assertEqual(
                json.loads(reports[0].read_text(encoding="utf-8"))["errors"][0]["code"],
                "unknown_schema_fingerprint",
            )

    def test_missing_polymorphic_reference_aborts_without_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            report_path = root / "invalid.json"
            create_legacy_fixture(active)
            with sqlite3.connect(active) as altered:
                altered.execute("UPDATE expense_items SET object_id = 9999 WHERE id = 30")
            before = active.read_bytes()

            code, _, _ = self._call(
                ["migrate", "--database", str(active), "--cutover", "--report", str(report_path)], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertTrue(list(root.glob("*.legacy-backup-*.db")))
            self.assertFalse(json.loads(report_path.read_text(encoding="utf-8"))["success"])

    def test_non_monotone_meter_series_aborts_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            report_path = root / "readings.json"
            create_legacy_fixture(active)
            with sqlite3.connect(active) as altered:
                altered.execute("UPDATE meter_readings SET reading_value = 1 WHERE id = 30")
            before = active.read_bytes()

            code, _, _ = self._call(
                ["migrate", "--database", str(active), "--dry-run", "--report", str(report_path)], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["success"])
            self.assertIn("non-monotone", report["errors"][0]["reason"])

    def test_non_linear_depreciation_method_aborts_without_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            report_path = root / "depreciation-method.json"
            create_legacy_fixture(active)
            with sqlite3.connect(active) as altered:
                altered.execute(
                    "UPDATE depreciation_assets SET method = ? WHERE id = 10",
                    ("declining_balance",),
                )
            before = active.read_bytes()

            code, _, _ = self._call(
                ["migrate", "--database", str(active), "--cutover", "--report", str(report_path)], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["success"])
            self.assertFalse(report["activated"])
            self.assertIn("unsupported method", report["errors"][0]["reason"])
            self.assertEqual(list(root.glob("*.v1-staging-*.db")), [])

    def test_existing_target_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            target = root / "reserved.db"
            create_legacy_fixture(active)
            target.write_bytes(b"reserved content")
            before = active.read_bytes()

            code, _, _ = self._call(
                ["migrate", "--database", str(active), "--target", str(target), "--dry-run"], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertEqual(target.read_bytes(), b"reserved content")
            self.assertEqual(list(root.glob("*.legacy-backup-*.db")), [])

    def test_interrupted_atomic_rename_keeps_legacy_active_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)
            before = active.read_bytes()

            actual_replace = os.replace

            def interrupted_replace(source: os.PathLike[str] | str, destination: os.PathLike[str] | str) -> None:
                if Path(destination) == active:
                    raise OSError("simulated interruption")
                actual_replace(source, destination)

            with patch("easyprent_accounting.migration.os.replace", side_effect=interrupted_replace):
                code, _, _ = self._call(
                    ["migrate", "--database", str(active), "--cutover"], root
                )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertTrue(list(root.glob("*.legacy-backup-*.db")))
            self.assertEqual(list(root.glob("*.v1-staging-*.db")), [])

    def test_same_unchanged_source_can_be_migrated_twice_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)
            before = active.read_bytes()
            reports = []
            for number in (1, 2):
                report_path = root / f"dry-run-{number}.json"
                code, _, stderr = self._call(
                    ["migrate", "--database", str(active), "--dry-run", "--report", str(report_path)], root
                )
                self.assertEqual(code, 0, stderr)
                self.assertEqual(active.read_bytes(), before)
                reports.append(json.loads(report_path.read_text(encoding="utf-8")))
            self.assertNotEqual(reports[0]["backup_path"], reports[1]["backup_path"])
            self.assertEqual(reports[0]["checksums"], reports[1]["checksums"])

    def test_restore_rejects_unrelated_valid_sqlite_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            wrong_backup = root / "unrelated.db"
            create_legacy_fixture(active)
            before = active.read_bytes()
            with sqlite3.connect(wrong_backup) as unrelated:
                unrelated.execute("CREATE TABLE something_else (id INTEGER PRIMARY KEY)")

            code, _, _ = self._call(
                ["restore", "--database", str(active), "--backup", str(wrong_backup)], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertEqual(list(root.glob("*.pre-restore-*.db")), [])

    def test_cutover_and_restore_preserve_active_file_owner_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            report_path = root / "cutover.json"
            create_legacy_fixture(active)
            active.chmod(0o640)
            original = active.stat()

            code, _, stderr = self._call(
                ["migrate", "--database", str(active), "--cutover", "--report", str(report_path)], root
            )
            self.assertEqual(code, 0, stderr)
            after_cutover = active.stat()
            self.assertEqual((after_cutover.st_uid, after_cutover.st_gid),
                             (original.st_uid, original.st_gid))
            self.assertEqual(stat.S_IMODE(after_cutover.st_mode), 0o640)

            backup = Path(json.loads(report_path.read_text(encoding="utf-8"))["backup_path"])
            code, _, stderr = self._call(
                ["restore", "--backup", str(backup), "--database", str(active)], root
            )
            self.assertEqual(code, 0, stderr)
            after_restore = active.stat()
            self.assertEqual((after_restore.st_uid, after_restore.st_gid),
                             (original.st_uid, original.st_gid))
            self.assertEqual(stat.S_IMODE(after_restore.st_mode), 0o640)

    def test_directory_sync_preflight_failure_leaves_legacy_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)
            before = active.read_bytes()
            actual_fsync = os.fsync
            call_count = 0

            def fail_directory_preflight(descriptor: int) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated directory sync failure")
                actual_fsync(descriptor)

            with patch("easyprent_accounting.migration.os.fsync", side_effect=fail_directory_preflight):
                code, _, _ = self._call(
                    ["migrate", "--database", str(active), "--cutover"], root
                )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertTrue(list(root.glob("*.legacy-backup-*.db")))

    def test_report_status_update_failure_after_cutover_retains_pre_cutover_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)

            actual_persist = migration._persist_report
            write_count = 0

            def fail_status_update(path: Path, report: dict[str, object]) -> None:
                nonlocal write_count
                write_count += 1
                if write_count == 2:
                    raise OSError("report disk error")
                actual_persist(path, report)

            report_path = root / "report.json"
            with patch.object(migration, "_persist_report", side_effect=fail_status_update):
                code, stdout, stderr = self._call(
                    ["migrate", "--database", str(active), "--cutover", "--report", str(report_path)], root
                )

            self.assertEqual(code, 0, stderr)
            self.assertIn("activated", stdout)
            pending = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(pending["success"])
            self.assertTrue(pending["cutover_requested"])
            self.assertFalse(pending["activated"])
            with sqlite3.connect(active) as upgraded:
                self.assertEqual(upgraded.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 1)

    def test_validation_report_persistence_failure_aborts_before_cutover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)
            before = active.read_bytes()

            with patch.object(migration, "_persist_report", side_effect=OSError("report disk error")):
                code, _, _ = self._call(
                    ["migrate", "--database", str(active), "--cutover"], root
                )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertTrue(list(root.glob("*.legacy-backup-*.db")))
            self.assertEqual(list(root.glob("*.v1-staging-*.db")), [])

    def test_missing_redundant_cadence_field_uses_canonical_charge_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            report_path = root / "cadence.json"
            create_legacy_fixture(active)
            with sqlite3.connect(active) as source:
                source.execute("UPDATE expense_items SET interval_name = NULL WHERE id = 20")

            code, _, stderr = self._call(
                ["migrate", "--database", str(active), "--dry-run", "--report", str(report_path)], root
            )

            self.assertEqual(code, 0, stderr)
            self.assertTrue(json.loads(report_path.read_text(encoding="utf-8"))["success"])

    def test_failed_mapping_without_report_flag_still_persists_machine_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)
            with sqlite3.connect(active) as source:
                source.execute("UPDATE expense_items SET object_id = 9999 WHERE id = 30")
            before = active.read_bytes()

            code, _, _ = self._call(
                ["migrate", "--database", str(active), "--dry-run"], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            reports = list(root.glob("active.db.migration-report-*.json"))
            self.assertEqual(len(reports), 1)
            self.assertFalse(json.loads(reports[0].read_text(encoding="utf-8"))["success"])

    def test_wal_mode_with_live_sidecars_rejects_cutover_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            report_path = root / "wal-rejected.json"
            create_legacy_fixture(active)
            writer = sqlite3.connect(active)
            try:
                self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
                writer.execute("INSERT INTO tenants (id, full_name) VALUES (999, 'Synthetic WAL tenant')")
                writer.commit()

                code, _, _ = self._call(
                    ["migrate", "--database", str(active), "--cutover", "--report", str(report_path)], root
                )

                self.assertEqual(code, 1)
                self.assertEqual(writer.execute("SELECT COUNT(*) FROM tenants WHERE id = 999").fetchone()[0], 1)
                self.assertEqual(writer.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(writer.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='schema_migrations'").fetchone()[0], 0)
                self.assertFalse(json.loads(report_path.read_text(encoding="utf-8"))["success"])
            finally:
                writer.close()

    def test_wal_mode_with_live_sidecars_rejects_restore_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            cutover_report = root / "cutover.json"
            restore_report = root / "restore-rejected.json"
            create_legacy_fixture(active)
            code, _, stderr = self._call(
                ["migrate", "--database", str(active), "--cutover", "--report", str(cutover_report)], root
            )
            self.assertEqual(code, 0, stderr)
            backup = Path(json.loads(cutover_report.read_text(encoding="utf-8"))["backup_path"])
            writer = sqlite3.connect(active)
            try:
                self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
                writer.execute("UPDATE application_settings SET sender_name = 'Synthetic change' WHERE id = 10")
                writer.commit()

                code, _, _ = self._call(
                    ["restore", "--database", str(active), "--backup", str(backup), "--report", str(restore_report)], root
                )

                self.assertEqual(code, 1)
                self.assertEqual(writer.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 1)
                self.assertEqual(writer.execute("SELECT sender_name FROM application_settings WHERE id = 10").fetchone()[0],
                                 "Synthetic change")
                self.assertEqual(writer.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertFalse(json.loads(restore_report.read_text(encoding="utf-8"))["success"])
            finally:
                writer.close()

    def test_unwritable_report_destination_aborts_cutover_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            create_legacy_fixture(active)
            before = active.read_bytes()
            missing_report = root / "missing" / "validation.json"

            code, _, _ = self._call(
                ["migrate", "--database", str(active), "--cutover", "--report", str(missing_report)], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertFalse((root / "missing").exists())

    def test_unwritable_restore_report_destination_aborts_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.db"
            cutover_report = root / "cutover.json"
            create_legacy_fixture(active)
            code, _, stderr = self._call(
                ["migrate", "--database", str(active), "--cutover", "--report", str(cutover_report)], root
            )
            self.assertEqual(code, 0, stderr)
            backup = Path(json.loads(cutover_report.read_text(encoding="utf-8"))["backup_path"])
            before = active.read_bytes()
            missing_report = root / "missing" / "restore.json"

            code, _, _ = self._call(
                ["restore", "--database", str(active), "--backup", str(backup),
                 "--report", str(missing_report)], root
            )

            self.assertEqual(code, 1)
            self.assertEqual(active.read_bytes(), before)
            self.assertFalse((root / "missing").exists())


if __name__ == "__main__":
    unittest.main()
