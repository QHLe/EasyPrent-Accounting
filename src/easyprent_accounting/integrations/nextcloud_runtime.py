from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator
from urllib.parse import quote

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import AppConfig, load_config
from app.models import NextcloudSettings

try:
    from app.integrations.nextcloud import NextcloudService
except Exception:
    NextcloudService = None


@dataclass
class EffectiveNextcloudConfig:
    enabled: bool
    configured: bool
    base_url: str | None
    username: str | None
    password: str | None
    verify_ssl: bool
    tasks_collection: str | None
    autosync: bool
    source: str


def mask_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    if len(secret) <= 4:
        return "•" * len(secret)
    return f"{'•' * max(8, len(secret) - 4)}{secret[-4:]}"


def normalize_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().rstrip("/")
    return normalized or None


def normalize_collection(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().rstrip("/")
    return normalized or None


def get_nextcloud_settings(db: Session) -> NextcloudSettings | None:
    return db.query(NextcloudSettings).order_by(NextcloudSettings.id.desc()).first()


def resolve_nextcloud_config(db: Session, cfg: AppConfig | None = None) -> EffectiveNextcloudConfig:
    cfg = cfg or load_config()
    settings = get_nextcloud_settings(db)
    if settings and settings.base_url and settings.username and settings.password:
        return EffectiveNextcloudConfig(
            enabled=True,
            configured=True,
            base_url=normalize_base_url(settings.base_url),
            username=settings.username,
            password=settings.password,
            verify_ssl=bool(settings.verify_ssl),
            tasks_collection=normalize_collection(settings.tasks_collection),
            autosync=bool(settings.autosync),
            source="settings",
        )

    env_enabled = bool(getattr(cfg, "NEXTCLOUD_ENABLED", False))
    env_configured = bool(env_enabled and cfg.NEXTCLOUD_BASE_URL and cfg.NEXTCLOUD_USERNAME and cfg.NEXTCLOUD_PASSWORD)
    return EffectiveNextcloudConfig(
        enabled=env_enabled,
        configured=env_configured,
        base_url=normalize_base_url(getattr(cfg, "NEXTCLOUD_BASE_URL", None)),
        username=getattr(cfg, "NEXTCLOUD_USERNAME", None),
        password=getattr(cfg, "NEXTCLOUD_PASSWORD", None),
        verify_ssl=bool(getattr(cfg, "NEXTCLOUD_VERIFY_SSL", True)),
        tasks_collection=normalize_collection(getattr(cfg, "NEXTCLOUD_TASKS_COLLECTION", None)),
        autosync=bool(getattr(cfg, "NEXTCLOUD_AUTOSYNC", False)),
        source="env" if env_configured or env_enabled else "none",
    )


def serialize_nextcloud_runtime(db: Session, cfg: AppConfig | None = None) -> dict[str, object]:
    resolved = resolve_nextcloud_config(db, cfg)
    backup_directory = (
        f"{resolved.base_url}/remote.php/dav/files/{quote(resolved.username, safe='')}/easy_contract_manager/backups"
        if resolved.base_url and resolved.username
        else None
    )
    return {
        "enabled": resolved.enabled,
        "configured": resolved.configured,
        "base_url": resolved.base_url,
        "username": resolved.username,
        "password_present": bool(resolved.password),
        "password_masked": mask_secret(resolved.password),
        "verify_ssl": resolved.verify_ssl,
        "tasks_collection": resolved.tasks_collection
        or (
            f"{resolved.base_url}/remote.php/dav/calendars/{resolved.username}/personal"
            if resolved.base_url and resolved.username
            else None
        ),
        "backup_directory": backup_directory,
        "autosync": resolved.autosync,
        "source": resolved.source,
    }


@asynccontextmanager
async def open_nextcloud_service(
    request: Request,
    db: Session,
    cfg: AppConfig | None = None,
) -> AsyncIterator[object]:
    override_service = getattr(request.app.state, "nextcloud_service", None)
    if override_service is not None:
        yield override_service
        return

    resolved = resolve_nextcloud_config(db, cfg)
    service_class = getattr(request.app.state, "nextcloud_service_class", NextcloudService)
    if (
        not resolved.configured
        or service_class is None
        or not resolved.base_url
        or not resolved.username
        or not resolved.password
    ):
        raise HTTPException(status_code=501, detail="Nextcloud service not configured")

    service = service_class(
        base_url=resolved.base_url,
        username=resolved.username,
        password=resolved.password,
        verify_ssl=resolved.verify_ssl,
        tasks_collection=resolved.tasks_collection,
    )
    try:
        yield service
    finally:
        close = getattr(service, "close", None)
        if close is not None:
            maybe_awaitable = close()
            if maybe_awaitable is not None:
                await maybe_awaitable
