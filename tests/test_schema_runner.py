from __future__ import annotations

import sqlite3
import unittest

from easyprent_accounting.schema_runner import (
    Migration,
    MigrationError,
    MigrationSession,
    run_migrations,
    schema_version,
)


class SchemaRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")

    def tearDown(self) -> None:
        self.connection.close()

    def test_first_migration_creates_a_versioned_schema(self) -> None:
        def create_first_schema(connection: MigrationSession) -> None:
            connection.execute("CREATE TABLE example (id INTEGER PRIMARY KEY, value TEXT)")

        applied = run_migrations(
            self.connection, [Migration(1, "first schema", create_first_schema)]
        )

        self.assertEqual(applied, [1])
        self.assertEqual(schema_version(self.connection), 1)
        self.assertIsNotNone(
            self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'example'"
            ).fetchone()
        )

    def test_failed_upgrade_rolls_back_data_and_version(self) -> None:
        first = Migration(
            1,
            "first schema",
            lambda connection: connection.execute(
                "CREATE TABLE example (id INTEGER PRIMARY KEY, value TEXT)"
            ),
        )
        run_migrations(self.connection, [first])

        def failing_upgrade(connection: MigrationSession) -> None:
            connection.execute("INSERT INTO example (id, value) VALUES (1, 'partial')")
            raise RuntimeError("upgrade failed")

        with self.assertRaisesRegex(RuntimeError, "upgrade failed"):
            run_migrations(
                self.connection, [first, Migration(2, "second schema", failing_upgrade)]
            )

        self.assertEqual(schema_version(self.connection), 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM example").fetchone()[0], 0)

    def test_pending_upgrades_apply_in_order_and_do_not_repeat(self) -> None:
        migrations = [
            Migration(
                1,
                "first schema",
                lambda connection: connection.execute(
                    "CREATE TABLE example (id INTEGER PRIMARY KEY, value TEXT)"
                ),
            ),
            Migration(
                2,
                "add data",
                lambda connection: connection.execute(
                    "INSERT INTO example (id, value) VALUES (1, 'once')"
                ),
            ),
        ]

        self.assertEqual(run_migrations(self.connection, migrations[:1]), [1])
        self.assertEqual(run_migrations(self.connection, migrations), [2])
        self.assertEqual(run_migrations(self.connection, migrations), [])

        self.assertEqual(schema_version(self.connection), 2)
        self.assertEqual(
            self.connection.execute("SELECT value FROM example").fetchall(), [("once",)]
        )

    def test_unversioned_database_is_rejected_without_changes(self) -> None:
        self.connection.execute("CREATE TABLE legacy_data (id INTEGER PRIMARY KEY)")
        self.connection.commit()
        before = self.connection.iterdump()
        before_sql = "\n".join(before)

        with self.assertRaisesRegex(MigrationError, "unversioned database"):
            run_migrations(
                self.connection,
                [
                    Migration(
                        1,
                        "first schema",
                        lambda connection: connection.execute(
                            "CREATE TABLE example (id INTEGER PRIMARY KEY)"
                        ),
                    )
                ],
            )

        self.assertEqual("\n".join(self.connection.iterdump()), before_sql)

    def test_failed_first_migration_leaves_no_schema_or_ledger(self) -> None:
        def failing_first_schema(connection: MigrationSession) -> None:
            connection.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
            raise RuntimeError("first migration failed")

        with self.assertRaisesRegex(RuntimeError, "first migration failed"):
            run_migrations(
                self.connection,
                [Migration(1, "first schema", failing_first_schema)],
            )

        self.assertEqual(schema_version(self.connection), 0)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0],
            0,
        )

    def test_missing_ledger_version_is_rejected_before_an_upgrade(self) -> None:
        self.connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)"
        )
        self.connection.execute(
            "INSERT INTO schema_migrations VALUES (2, 'second schema', '2026-01-01')"
        )
        self.connection.commit()

        with self.assertRaisesRegex(MigrationError, "gap or invalid version"):
            run_migrations(
                self.connection,
                [
                    Migration(1, "first schema", lambda _: None),
                    Migration(2, "second schema", lambda _: None),
                ],
            )

        self.assertEqual(
            self.connection.execute("SELECT version FROM schema_migrations").fetchall(),
            [(2,)],
        )

    def test_callback_cannot_commit_partial_schema_with_executescript(self) -> None:
        def unsafe_callback(connection: MigrationSession) -> None:
            connection.executescript("CREATE TABLE partial_schema (id INTEGER PRIMARY KEY);")

        with self.assertRaises(MigrationError):
            run_migrations(
                self.connection, [Migration(1, "first schema", unsafe_callback)]
            )

        self.assertEqual(schema_version(self.connection), 0)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0],
            0,
        )

    def test_callback_cannot_commit_partial_schema_with_sql(self) -> None:
        def unsafe_callback(connection: MigrationSession) -> None:
            connection.execute("CREATE TABLE partial_schema (id INTEGER PRIMARY KEY)")
            connection.execute("COMMIT")

        with self.assertRaises(MigrationError):
            run_migrations(
                self.connection, [Migration(1, "first schema", unsafe_callback)]
            )

        self.assertEqual(schema_version(self.connection), 0)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
