from __future__ import annotations

from wsgiref.simple_server import make_server

from .db import initialize_database
from .web import application

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8020


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    initialize_database()
    with make_server(host, port, application) as httpd:
        print(f"EasyPrent Accounting laeuft auf http://{host}:{port}")
        httpd.serve_forever()


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
