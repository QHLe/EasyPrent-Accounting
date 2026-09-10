from __future__ import annotations

import os

from typing import Callable
from wsgiref.simple_server import WSGIServer, make_server

from .config import load_config, set_global_config
from .db import initialize_database
from .web import application

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8020


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> WSGIServer:
    config = load_config(os.environ)
    set_global_config(config)
    initialize_database(config.db_path)
    return make_server(host, port, application)


def run_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    ready_callback: Callable[[WSGIServer], None] | None = None,
) -> None:
    with create_server(host, port) as httpd:
        if ready_callback is not None:
            ready_callback(httpd)
        print(f"EasyPrent Accounting laeuft auf http://{host}:{port}")
        httpd.serve_forever()


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
