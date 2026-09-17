from __future__ import annotations

from datetime import UTC, datetime


def health_status() -> dict:
    return {
        "status": "ok",
        "reachable": True,
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }

