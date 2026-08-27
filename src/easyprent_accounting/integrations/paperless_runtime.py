from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import AppConfig, load_config
from app.models import PaperlessSettings

try:
    from app.integrations.paperless import PaperlessService
except Exception:
    PaperlessService = None


@dataclass
class EffectivePaperlessConfig:
    enabled: bool
    configured: bool
    base_url: str | None
    token: str | None
    source: str


def mask_token(token: str | None) -> str | None:
    if not token:
        return None
    if len(token) <= 4:
        return "•" * len(token)
    return f"{'•' * max(8, len(token) - 4)}{token[-4:]}"


def normalize_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().rstrip("/")
    return normalized or None


def get_paperless_settings(db: Session) -> PaperlessSettings | None:
    return db.query(PaperlessSettings).order_by(PaperlessSettings.id.desc()).first()


def resolve_paperless_config(db: Session, cfg: AppConfig | None = None) -> EffectivePaperlessConfig:
    cfg = cfg or load_config()
    settings = get_paperless_settings(db)
    if settings and settings.base_url and settings.api_token:
        return EffectivePaperlessConfig(
            enabled=True,
            configured=True,
            base_url=settings.base_url,
            token=settings.api_token,
            source="settings",
        )

    env_configured = bool(getattr(cfg, "PAPERLESS_ENABLED", False) and cfg.PAPERLESS_URL and cfg.PAPERLESS_TOKEN)
    return EffectivePaperlessConfig(
        enabled=bool(getattr(cfg, "PAPERLESS_ENABLED", False)),
        configured=env_configured,
        base_url=normalize_base_url(getattr(cfg, "PAPERLESS_URL", None)),
        token=getattr(cfg, "PAPERLESS_TOKEN", None),
        source="env" if env_configured or getattr(cfg, "PAPERLESS_ENABLED", False) else "none",
    )


def serialize_paperless_runtime(db: Session, cfg: AppConfig | None = None) -> dict[str, object]:
    resolved = resolve_paperless_config(db, cfg)
    token_masked = mask_token(resolved.token)
    return {
        "enabled": resolved.enabled,
        "configured": resolved.configured,
        "base_url": resolved.base_url,
        "token_present": bool(resolved.token),
        "token_masked": token_masked,
        "source": resolved.source,
    }


@asynccontextmanager
async def open_paperless_service(request: Request, db: Session, cfg: AppConfig | None = None) -> AsyncIterator[object]:
    resolved = resolve_paperless_config(db, cfg)
    service_class = getattr(request.app.state, "paperless_service_class", PaperlessService)
    if not resolved.configured or service_class is None or not resolved.base_url or not resolved.token:
        raise HTTPException(status_code=501, detail="Paperless service not configured")

    service = service_class(base_url=resolved.base_url, token=resolved.token)
    try:
        yield service
    finally:
        close = getattr(service, "close", None)
        if close is not None:
            maybe_awaitable = close()
            if maybe_awaitable is not None:
                await maybe_awaitable
