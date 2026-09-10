import os
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AppConfig:
    db_path: str
    project_root: Optional[str]
    sender_name: Optional[str]
    sender_street: Optional[str]
    sender_city: Optional[str]
    settlement_template: Optional[str]

def load_config(environ: dict[str, str]) -> AppConfig:
    return AppConfig(
        db_path=environ.get("EASYPRENT_DB_PATH", os.path.join(os.getcwd(), "easyprent_accounting.db")),
        project_root=environ.get("EASYPRENT_PROJECT_ROOT"),
        sender_name=environ.get("EASYPRENT_SENDER_NAME"),
        sender_street=environ.get("EASYPRENT_SENDER_STREET"),
        sender_city=environ.get("EASYPRENT_SENDER_CITY"),
        settlement_template=environ.get("EASYPRENT_SETTLEMENT_TEMPLATE"),
    )
