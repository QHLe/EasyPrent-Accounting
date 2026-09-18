"""Meter and reading HTTP contracts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from pydantic import Field

from .http_db import ReadConnection, WriteConnection
from .http_models import HttpModel
from .metering import Metering


TargetType = Literal["property", "building", "unit", "room"]
PositiveId = Annotated[int, Path(gt=0)]


class MeterWrite(HttpModel):
    object_type: TargetType
    object_id: Annotated[int, Field(strict=True, gt=0)]
    label: str
    meter_type: str | None = None
    unit: str
    serial_number: str | None = None


class MeterResponse(MeterWrite):
    id: int
    property_id: int | None = None
    is_archived: bool = False
    archived_at: str | None = None
    property_name: str | None = None
    object_name: str | None = None
    latest_reading_date: str | None = None
    latest_reading_value: str | None = None
    reading_count: int = 0


class ReadingWrite(HttpModel):
    meter_id: Annotated[int, Field(strict=True, gt=0)]
    reading_date: date
    reading_value: str


class ReadingResponse(HttpModel):
    id: int
    meter_id: int
    reading_date: str
    reading_value: str
    meter_label: str | None = None
    meter_unit: str | None = None
    object_type: TargetType | None = None
    object_id: int | None = None
    property_name: str | None = None
    object_name: str | None = None


class MeteringResponse(HttpModel):
    meters: list[MeterResponse]
    meter_readings: list[ReadingResponse]


class ConsumptionResponse(HttpModel):
    meter_id: int
    start: date
    end: date
    quantity: str | None


class MeterLifecycleResponse(HttpModel):
    resource: Literal["meters"]
    id: int
    is_archived: bool
    archived_at: str | None


class MeterDeleteResponse(HttpModel):
    resource: Literal["meters", "meter_readings"]
    id: int
    deleted: bool


def _meter_response(row: dict) -> MeterResponse:
    fields = {name: row[name] for name in MeterResponse.model_fields if name in row}
    if fields.get("latest_reading_value") is not None:
        fields["latest_reading_value"] = str(fields["latest_reading_value"])
    return MeterResponse.model_validate(fields)


def _reading_response(row: dict) -> ReadingResponse:
    fields = {name: row[name] for name in ReadingResponse.model_fields if name in row}
    fields["reading_value"] = str(fields["reading_value"])
    return ReadingResponse.model_validate(fields)


router = APIRouter(tags=["Metering"])


@router.get("/api/v1/metering", response_model=MeteringResponse)
def list_metering(connection: ReadConnection) -> MeteringResponse:
    result = Metering(connection).list_meters()
    return MeteringResponse(
        meters=[_meter_response(row) for row in result["meters"]],
        meter_readings=[_reading_response(row) for row in result["meter_readings"]],
    )


@router.post("/api/v1/meters", status_code=201, response_model=MeterResponse)
def create_meter(payload: MeterWrite, connection: WriteConnection) -> MeterResponse:
    return _meter_response(Metering(connection).create_meter(payload.model_dump(exclude_none=True)))


@router.put("/api/v1/meters/{meter_id}", response_model=MeterResponse)
def update_meter(meter_id: PositiveId, payload: MeterWrite, connection: WriteConnection) -> MeterResponse:
    return _meter_response(Metering(connection).update_meter(meter_id, payload.model_dump(exclude_none=True)))


@router.post("/api/v1/meter-readings", status_code=201, response_model=ReadingResponse)
def create_reading(payload: ReadingWrite, connection: WriteConnection) -> ReadingResponse:
    return _reading_response(Metering(connection).create_reading(payload.model_dump(mode="json")))


@router.delete("/api/v1/meter-readings/{reading_id}", response_model=MeterDeleteResponse)
def delete_reading(reading_id: PositiveId, connection: WriteConnection) -> dict:
    return Metering(connection).delete_reading(reading_id)


@router.get("/api/v1/meters/{meter_id}/consumption", response_model=ConsumptionResponse)
def meter_consumption(
    meter_id: PositiveId,
    connection: ReadConnection,
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
) -> ConsumptionResponse:
    if end < start:
        raise ValueError("end must be after or equal to start")
    quantity = Metering(connection).consumption_for_period(
        meter_id, start.isoformat(), end.isoformat()
    )
    return ConsumptionResponse(
        meter_id=meter_id, start=start, end=end,
        quantity=None if quantity is None else str(quantity),
    )


@router.post("/api/v1/meters/{meter_id}/archive", response_model=MeterLifecycleResponse)
def archive_meter(meter_id: PositiveId, connection: WriteConnection) -> dict:
    return Metering(connection).archive_meter(meter_id)


@router.post("/api/v1/meters/{meter_id}/restore", response_model=MeterLifecycleResponse)
def restore_meter(meter_id: PositiveId, connection: WriteConnection) -> dict:
    return Metering(connection).restore_meter(meter_id)


@router.delete("/api/v1/meters/{meter_id}", response_model=MeterDeleteResponse)
def delete_meter(meter_id: PositiveId, connection: WriteConnection) -> dict:
    return Metering(connection).delete_meter(meter_id)
