#!/usr/bin/env python3
"""Export the FastAPI OpenAPI document as JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the root directory is in the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from easyprent_accounting.asgi import create_asgi_app
from easyprent_accounting.config import AppConfig, SenderAddress


def main() -> int:
    config = AppConfig(
        db_path=Path("easyprent.db"),
        project_root=Path(__file__).resolve().parents[1],
        sender=SenderAddress(),
    )
    app = create_asgi_app(config)
    
    # We must explicitly query the app's OpenAPI schema
    schema = app.openapi()
    
    output_path = config.project_root / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(schema, file, indent=2, ensure_ascii=False)
        file.write("\n")
    
    print(f"Exported {output_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
