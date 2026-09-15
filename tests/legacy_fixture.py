"""Complete synthetic database for the frozen unversioned migration source."""

from __future__ import annotations

from pathlib import Path
import sqlite3


def create_legacy_fixture(path: Path) -> None:
    """Create the known Legacy schema at ``path`` without using production rows."""

    if path.exists():
        raise FileExistsError(path)
    fixture_dir = Path(__file__).parent / "fixtures"
    schema_sql = (fixture_dir / "legacy_schema.sql").read_text(
        encoding="utf-8"
    )
    rows_sql = (fixture_dir / "legacy_rows.sql").read_text(
        encoding="utf-8"
    )
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema_sql)
        connection.executescript(rows_sql)
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Synthetic Legacy fixture has broken foreign keys")
        connection.commit()
    finally:
        connection.close()
