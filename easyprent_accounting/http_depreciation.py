"""Depreciation transport models and routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from .depreciation import Depreciation
from .http_db import ReadConnection, WriteConnection
from .http_models import HttpModel


PositiveInt = Annotated[int, Path(gt=0)]


from datetime import date
from decimal import Decimal

class AssetWrite(HttpModel):
    property_id: int
    asset_name: str
    acquisition_cost: Decimal
    building_share_percent: Decimal
    useful_life_years: int
    placed_in_service: date


class AssetResponse(AssetWrite):
    id: int


class ScheduleRow(HttpModel):
    asset_name: str
    placed_in_service: date
    depreciable_basis: Decimal
    useful_life_years: int
    months_in_year: int
    yearly_depreciation: Decimal

class ScheduleResponse(HttpModel):
    year: int
    rows: list[ScheduleRow]
    total: Decimal


router = APIRouter(tags=["Depreciation"])


@router.post("/api/v1/depreciation/assets", status_code=201, response_model=AssetResponse, operation_id="create_depreciation_asset")
def create_asset(payload: AssetWrite, connection: WriteConnection) -> HttpModel:
    result = Depreciation(connection).create_asset(payload.model_dump(mode="json"))
    return AssetResponse.model_validate(result)


@router.get("/api/v1/depreciation/assets", response_model=list[AssetResponse], operation_id="list_depreciation_assets")
def list_assets(connection: ReadConnection) -> list[HttpModel]:
    return [AssetResponse.model_validate(row) for row in Depreciation(connection).list_assets()]


@router.get("/api/v1/depreciation/schedule/{year}", response_model=ScheduleResponse, operation_id="get_depreciation_schedule")
def schedule_for_year(year: PositiveInt, connection: ReadConnection) -> HttpModel:
    result = Depreciation(connection).schedule_for_year(year)
    return ScheduleResponse.model_validate(result)
