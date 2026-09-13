from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class SenderAddress:
    name: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None


@dataclass(frozen=True)
class AppConfig:
    db_path: Path
    project_root: Path
    sender: SenderAddress = SenderAddress()
    settlement_template: Optional[Path] = None

    def __init__(
        self,
        db_path: Path,
        project_root: Path,
        sender: Optional[SenderAddress] = None,
        settlement_template: Optional[Path] = None,
        sender_name: Optional[str] = None,
        sender_street: Optional[str] = None,
        sender_city: Optional[str] = None,
    ) -> None:
        object.__setattr__(self, "db_path", db_path)
        object.__setattr__(self, "project_root", project_root)
        if sender is None:
            sender = SenderAddress(name=sender_name, street=sender_street, city=sender_city)
        object.__setattr__(self, "sender", sender)
        object.__setattr__(self, "settlement_template", settlement_template)

    @property
    def sender_name(self) -> Optional[str]:
        return self.sender.name

    @property
    def sender_street(self) -> Optional[str]:
        return self.sender.street

    @property
    def sender_city(self) -> Optional[str]:
        return self.sender.city


def load_config(environ: dict[str, str]) -> AppConfig:
    project_root_env = environ.get("EASYPRENT_PROJECT_ROOT")
    project_root_override = Path(project_root_env).expanduser().resolve() if project_root_env is not None else None
    effective_project_root = resolve_project_root(project_root_override)

    db_path_env = environ.get("EASYPRENT_DB_PATH")
    if db_path_env is not None:
        db_path = Path(db_path_env).expanduser().resolve()
    else:
        db_path = (effective_project_root / "easyprent_accounting.db").resolve()

    template = environ.get("EASYPRENT_SETTLEMENT_TEMPLATE")
    if template is not None:
        template_path: Optional[Path] = (effective_project_root / Path(template).expanduser()).resolve()
    else:
        checkout_template = effective_project_root / "templates" / "utility_settlement.ods"
        if checkout_template.is_file():
            template_path = checkout_template.resolve()
        else:
            template_path = None

    sender = SenderAddress(
        name=environ.get("EASYPRENT_SENDER_NAME"),
        street=environ.get("EASYPRENT_SENDER_STREET"),
        city=environ.get("EASYPRENT_SENDER_CITY"),
    )

    return AppConfig(
        db_path=db_path,
        project_root=effective_project_root,
        sender=sender,
        settlement_template=template_path,
    )


def resolve_project_root(project_root_override: Optional[Path] = None) -> Path:
    if project_root_override is not None:
        return project_root_override.resolve()
    checkout = find_checkout_root()
    if checkout is not None:
        return checkout
    return Path.cwd().resolve()



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
