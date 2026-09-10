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


def find_checkout_root() -> Optional[Path]:
    candidate = Path(__file__).resolve().parents[1]
    if (candidate / "pyproject.toml").is_file():
        return candidate
    return None

_global_config: Optional[AppConfig] = None

def set_global_config(cfg: Optional[AppConfig]) -> None:
    global _global_config
    _global_config = cfg

def get_global_config() -> AppConfig:
    if _global_config is None:
        raise RuntimeError(
            "AppConfig not initialised. "
            "Call set_global_config() from the composition root before serving requests or CLI functions."
        )
    return _global_config
