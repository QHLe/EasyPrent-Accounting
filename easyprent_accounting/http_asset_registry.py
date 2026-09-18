"""Asset Registry transport models and routes."""

from __future__ import annotations

from typing import Annotated, Literal, TypeVar

from fastapi import APIRouter, Path
from pydantic import Field, model_validator

from .asset_registry import AssetRegistry
from .http_db import ReadConnection, WriteConnection
from .http_models import HttpModel


PositiveId = Annotated[int, Path(gt=0)]


class PropertyWrite(HttpModel):
    organization_id: Annotated[int, Field(strict=True, gt=0)]
    name: str
    street: str
    city: str
    postal_code: str


class PropertyResponse(PropertyWrite):
    id: int
    is_archived: bool = False
    archived_at: str | None = None
    organization_name: str | None = None
    building_count: int = 0
    unit_count: int = 0
    room_count: int = 0
    expense_count: int = 0


class BuildingWrite(HttpModel):
    property_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    name: str
    year_built: int | None = None
    street: str
    city: str
    postal_code: str


class BuildingResponse(BuildingWrite):
    id: int
    is_archived: bool = False
    archived_at: str | None = None
    property_name: str | None = None
    unit_count: int = 0
    room_count: int = 0


class UnitWrite(HttpModel):
    building_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    label: str
    area_sqm: str
    mea_percent: str
    room_count: Annotated[int, Field(strict=True, ge=0)]
    street: str | None = None
    city: str | None = None
    postal_code: str | None = None

    @model_validator(mode="after")
    def require_standalone_address(self) -> UnitWrite:
        if self.building_id is None and not all((self.street, self.city, self.postal_code)):
            raise ValueError("street, city and postal_code are required without building_id")
        return self


class UnitResponse(UnitWrite):
    id: int
    property_id: int | None = None
    building_name: str | None = None
    property_name: str | None = None
    actual_room_count: int = 0
    is_archived: bool = False
    archived_at: str | None = None


class RoomWrite(HttpModel):
    unit_id: Annotated[int, Field(strict=True, gt=0)]
    label: str
    area_sqm: str | None = None
    area_share_percent: str | None = None


class RoomResponse(RoomWrite):
    id: int
    unit_label: str | None = None
    building_id: int | None = None
    property_id: int | None = None
    building_name: str | None = None
    property_name: str | None = None
    is_archived: bool = False
    archived_at: str | None = None


class AssetListResponse(HttpModel):
    properties: list[PropertyResponse]
    buildings: list[BuildingResponse]
    units: list[UnitResponse]
    rooms: list[RoomResponse]


class AssetLifecycleResponse(HttpModel):
    resource: Literal["properties", "buildings", "units", "rooms"]
    id: int
    is_archived: bool
    archived_at: str | None


class AssetDeleteResponse(HttpModel):
    resource: Literal["properties", "buildings", "units", "rooms"]
    id: int
    deleted: bool


ResponseModel = TypeVar("ResponseModel", bound=HttpModel)


def _response(model: type[ResponseModel], row: dict) -> ResponseModel:
    fields = {name: row[name] for name in model.model_fields if name in row}
    for name in ("area_sqm", "area_share_percent", "mea_percent"):
        if fields.get(name) is not None:
            fields[name] = str(fields[name])
    return model.model_validate(fields)


router = APIRouter(tags=["Asset Registry"])


@router.get("/api/v1/assets", response_model=AssetListResponse)
def list_assets(connection: ReadConnection) -> AssetListResponse:
    result = AssetRegistry(connection).list_assets()
    return AssetListResponse(
        properties=[_response(PropertyResponse, row) for row in result["properties"]],
        buildings=[_response(BuildingResponse, row) for row in result["buildings"]],
        units=[_response(UnitResponse, row) for row in result["units"]],
        rooms=[_response(RoomResponse, row) for row in result["rooms"]],
    )


@router.post("/api/v1/properties", status_code=201, response_model=PropertyResponse)
def create_property(payload: PropertyWrite, connection: WriteConnection) -> HttpModel:
    return _response(PropertyResponse, AssetRegistry(connection).create_property(payload.model_dump()))


@router.put("/api/v1/properties/{property_id}", response_model=PropertyResponse)
def update_property(property_id: PositiveId, payload: PropertyWrite, connection: WriteConnection) -> HttpModel:
    return _response(PropertyResponse, AssetRegistry(connection).update_property(property_id, payload.model_dump()))


@router.post("/api/v1/buildings", status_code=201, response_model=BuildingResponse)
def create_building(payload: BuildingWrite, connection: WriteConnection) -> HttpModel:
    return _response(BuildingResponse, AssetRegistry(connection).create_building(payload.model_dump()))


@router.put("/api/v1/buildings/{building_id}", response_model=BuildingResponse)
def update_building(building_id: PositiveId, payload: BuildingWrite, connection: WriteConnection) -> HttpModel:
    return _response(BuildingResponse, AssetRegistry(connection).update_building(building_id, payload.model_dump()))


@router.post("/api/v1/units", status_code=201, response_model=UnitResponse)
def create_unit(payload: UnitWrite, connection: WriteConnection) -> HttpModel:
    return _response(UnitResponse, AssetRegistry(connection).create_unit(payload.model_dump(exclude_none=True)))


@router.put("/api/v1/units/{unit_id}", response_model=UnitResponse)
def update_unit(unit_id: PositiveId, payload: UnitWrite, connection: WriteConnection) -> HttpModel:
    return _response(UnitResponse, AssetRegistry(connection).update_unit(unit_id, payload.model_dump(exclude_none=True)))


@router.post("/api/v1/rooms", status_code=201, response_model=RoomResponse)
def create_room(payload: RoomWrite, connection: WriteConnection) -> HttpModel:
    return _response(RoomResponse, AssetRegistry(connection).create_room(payload.model_dump(exclude_none=True)))


@router.put("/api/v1/rooms/{room_id}", response_model=RoomResponse)
def update_room(room_id: PositiveId, payload: RoomWrite, connection: WriteConnection) -> HttpModel:
    return _response(RoomResponse, AssetRegistry(connection).update_room(room_id, payload.model_dump(exclude_none=True)))


@router.post("/api/v1/properties/{property_id}/archive", response_model=AssetLifecycleResponse)
def archive_property(property_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).archive_property(property_id)


@router.post("/api/v1/properties/{property_id}/restore", response_model=AssetLifecycleResponse)
def restore_property(property_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).restore_property(property_id)


@router.delete("/api/v1/properties/{property_id}", response_model=AssetDeleteResponse)
def delete_property(property_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).delete_property(property_id)


@router.post("/api/v1/buildings/{building_id}/archive", response_model=AssetLifecycleResponse)
def archive_building(building_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).archive_building(building_id)


@router.post("/api/v1/buildings/{building_id}/restore", response_model=AssetLifecycleResponse)
def restore_building(building_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).restore_building(building_id)


@router.delete("/api/v1/buildings/{building_id}", response_model=AssetDeleteResponse)
def delete_building(building_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).delete_building(building_id)


@router.post("/api/v1/units/{unit_id}/archive", response_model=AssetLifecycleResponse)
def archive_unit(unit_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).archive_unit(unit_id)


@router.post("/api/v1/units/{unit_id}/restore", response_model=AssetLifecycleResponse)
def restore_unit(unit_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).restore_unit(unit_id)


@router.delete("/api/v1/units/{unit_id}", response_model=AssetDeleteResponse)
def delete_unit(unit_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).delete_unit(unit_id)


@router.post("/api/v1/rooms/{room_id}/archive", response_model=AssetLifecycleResponse)
def archive_room(room_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).archive_room(room_id)


@router.post("/api/v1/rooms/{room_id}/restore", response_model=AssetLifecycleResponse)
def restore_room(room_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).restore_room(room_id)


@router.delete("/api/v1/rooms/{room_id}", response_model=AssetDeleteResponse)
def delete_room(room_id: PositiveId, connection: WriteConnection) -> dict:
    return AssetRegistry(connection).delete_room(room_id)
