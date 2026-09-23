"""ASGI server command for local CLI and development use."""

from __future__ import annotations

import argparse
import os
import sys

import uvicorn

from .asgi import create_asgi_app
from .config import load_config
from .runtime_schema import prepare_database


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8020


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    config = load_config(dict(os.environ))
    try:
        prepare_database(config.db_path)
    except (OSError, RuntimeError) as error:
        print(f"Serverstart fehlgeschlagen: {error}", file=sys.stderr)
        return 1
    uvicorn.run(
        create_asgi_app(config),
        host=host,
        port=port,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EasyPrent Accounting ASGI server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    return run_server(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
