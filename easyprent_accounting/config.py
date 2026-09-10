import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class AppConfig:
    db_path: Path
    project_root: Optional[Path]
    sender_name: Optional[str]
    sender_street: Optional[str]
    sender_city: Optional[str]
    settlement_template: Optional[Path]

def load_config(environ: dict[str, str]) -> AppConfig:
    project_root = environ.get("EASYPRENT_PROJECT_ROOT")
    template = environ.get("EASYPRENT_SETTLEMENT_TEMPLATE")
    
    return AppConfig(
        db_path=Path(environ.get("EASYPRENT_DB_PATH", os.path.join(os.getcwd(), "easyprent_accounting.db"))),
        project_root=Path(project_root) if project_root is not None else None,
        sender_name=environ.get("EASYPRENT_SENDER_NAME"),
        sender_street=environ.get("EASYPRENT_SENDER_STREET"),
        sender_city=environ.get("EASYPRENT_SENDER_CITY"),
        settlement_template=Path(template) if template is not None else None,
    )
