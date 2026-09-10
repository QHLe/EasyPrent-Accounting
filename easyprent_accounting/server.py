from __future__ import annotations

import os

from wsgiref.simple_server import make_server

from .config import load_config
from .db import initialize_database
from .web import application
from .config import set_global_config

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8020


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    config = load_config(os.environ)
    set_config(config)
    initialize_database(config.db_path)
    with make_server(host, port, application) as httpd:
        print(f"EasyPrent Accounting laeuft auf http://{host}:{port}")
        httpd.serve_forever()


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
