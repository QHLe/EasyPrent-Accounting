from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import tomllib
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
    sender: SenderAddress = field(default_factory=SenderAddress)
    settlement_template: Optional[Path] = None


def load_config(environ: dict[str, str]) -> AppConfig:
    project_root_env = environ.get("EASYPRENT_PROJECT_ROOT")
    project_root_override = (
        Path(project_root_env).expanduser().resolve()
        if project_root_env is not None
        else None
    )
    current_working_directory = Path.cwd().resolve()
    checkout_root = _find_checkout_root(
        project_root_override,
        current_working_directory,
    )
    effective_project_root = (
        project_root_override or checkout_root or current_working_directory
    )

    db_path_env = environ.get("EASYPRENT_DB_PATH")
    if db_path_env is not None:
        db_path = Path(db_path_env).expanduser().resolve()
    else:
        db_path = (effective_project_root / "easyprent_accounting.db").resolve()

    template = environ.get("EASYPRENT_SETTLEMENT_TEMPLATE")
    if template is not None:
        template_path: Optional[Path] = (
            effective_project_root / Path(template).expanduser()
        ).resolve()
    elif checkout_root is not None:
        checkout_template = checkout_root / "templates" / "utility_settlement.ods"
        if checkout_template.is_file():
            template_path = checkout_template.resolve()
        else:
            template_path = None
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


def _find_checkout_root(
    project_root_override: Optional[Path],
    current_working_directory: Path,
) -> Optional[Path]:
    if project_root_override is not None:
        if _is_checkout_root(project_root_override):
            return project_root_override
        return None

    seen: set[Path] = set()
    search_roots = (Path(__file__).resolve().parent, current_working_directory)
    for search_root in search_roots:
        for candidate in (search_root, *search_root.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if _is_checkout_root(candidate):
                return candidate
    return None


def _is_checkout_root(candidate: Path) -> bool:
    pyproject = candidate / "pyproject.toml"
    package = candidate / "easyprent_accounting"
    if not pyproject.is_file() or not (package / "config.py").is_file():
        return False
    try:
        with pyproject.open("rb") as handle:
            project = tomllib.load(handle).get("project")
    except (OSError, tomllib.TOMLDecodeError):
        return False
    if not isinstance(project, dict) or project.get("name") != "easyprent-accounting":
        return False

    # sudo may read a checkout owned by the application account. Trust only
    # this explicitly validated candidate for these read-only identity checks.
    git = ["git", "-c", f"safe.directory={candidate}", "-C", str(candidate)]
    try:
        root = subprocess.run(
            [*git, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if root.returncode != 0 or Path(root.stdout.rstrip("\n")).resolve() != candidate:
            return False
        tracked = subprocess.run(
            [
                *git, "ls-files", "--error-unmatch", "--",
                "pyproject.toml",
                "easyprent_accounting/__init__.py",
                "easyprent_accounting/config.py",
            ],
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return tracked.returncode == 0


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
