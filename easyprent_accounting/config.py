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
    project_root_env = environ.get("EASYPRENT_PROJECT_ROOT")
    project_root = Path(project_root_env).expanduser().resolve() if project_root_env is not None else None
    resolved_root = resolve_project_root(project_root)

    db_path_env = environ.get("EASYPRENT_DB_PATH")
    if db_path_env is not None:
        db_path = Path(db_path_env).expanduser().resolve()
    else:
        db_path = (resolved_root / "easyprent_accounting.db").resolve()

    template = environ.get("EASYPRENT_SETTLEMENT_TEMPLATE")
    template_path = (resolved_root / Path(template).expanduser()).resolve() if template is not None else None

    return AppConfig(
        db_path=db_path,
        project_root=project_root,
        sender_name=environ.get("EASYPRENT_SENDER_NAME"),
        sender_street=environ.get("EASYPRENT_SENDER_STREET"),
        sender_city=environ.get("EASYPRENT_SENDER_CITY"),
        settlement_template=template_path,
    )


def resolve_project_root(project_root_override: Optional[Path] = None) -> Path:
    if project_root_override is not None:
        return project_root_override.resolve()
    checkout = find_checkout_root()
    if checkout is not None:
        return checkout
    return Path.cwd().resolve()


def get_project_root() -> Path:
    return resolve_project_root(get_global_config().project_root)


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
