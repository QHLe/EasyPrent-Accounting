"""Tenant and rental contract HTTP contracts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path
from pydantic import Field

from .http_db import ReadConnection, WriteConnection
from .http_models import HttpModel
from .tenancy import Tenancy


PositiveId = Annotated[int, Path(gt=0)]


class TenantWrite(HttpModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    alternate_street: str | None = None
    alternate_postal_code: str | None = None
    alternate_city: str | None = None


class TenantResponse(TenantWrite):
    id: int


class LeaseWrite(HttpModel):
    tenant_id: Annotated[int, Field(strict=True, gt=0)]
    unit_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    room_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    rent_cold: str
    additional_charges_advance: str
    occupant_count: Annotated[int, Field(strict=True, ge=1)]
    start_date: date
    end_date: date | None = None
    status: str = "active"
    gnucash_nk_account_guid: str | None = None
    gnucash_nk_account_name: str | None = None


class LeaseResponse(HttpModel):
    id: int
    unit_id: int
    room_id: int | None
    tenant_id: int
    rent_cold: str
    additional_charges_advance: str
    occupant_count: int
    start_date: str
    end_date: str | None
    status: str
    gnucash_nk_account_guid: str | None = None
    gnucash_nk_account_name: str | None = None
    unit_label: str | None = None
    room_label: str | None = None
    tenant_name: str | None = None
    rental_object_type: Literal["room", "unit"] | None = None
    rental_object_label: str | None = None


class TenancyResponse(HttpModel):
    tenants: list[TenantResponse]
    leases: list[LeaseResponse]


class TenancyDeleteResponse(HttpModel):
    resource: Literal["tenants", "leases"]
    id: int
    deleted: bool


def _lease_response(row: dict) -> LeaseResponse:
    fields = {name: row[name] for name in LeaseResponse.model_fields if name in row}
    for name in ("rent_cold", "additional_charges_advance"):
        fields[name] = str(fields[name])
    return LeaseResponse.model_validate(fields)


router = APIRouter(tags=["Tenancy"])


@router.get("/api/v1/tenancy", response_model=TenancyResponse)
def list_tenancy(connection: ReadConnection) -> TenancyResponse:
    result = Tenancy(connection).list_tenancy()
    return TenancyResponse(
        tenants=[TenantResponse.model_validate(row) for row in result["tenants"]],
        leases=[_lease_response(row) for row in result["leases"]],
    )


@router.post("/api/v1/tenants", status_code=201, response_model=TenantResponse)
def create_tenant(payload: TenantWrite, connection: WriteConnection) -> dict:
    return Tenancy(connection).create_tenant(payload.model_dump())


@router.put("/api/v1/tenants/{tenant_id}", response_model=TenantResponse)
def update_tenant(tenant_id: PositiveId, payload: TenantWrite, connection: WriteConnection) -> dict:
    return Tenancy(connection).update_tenant(tenant_id, payload.model_dump())


@router.delete("/api/v1/tenants/{tenant_id}", response_model=TenancyDeleteResponse)
def delete_tenant(tenant_id: PositiveId, connection: WriteConnection) -> dict:
    return Tenancy(connection).delete_tenant(tenant_id)


@router.post("/api/v1/leases", status_code=201, response_model=LeaseResponse)
def create_lease(payload: LeaseWrite, connection: WriteConnection) -> LeaseResponse:
    return _lease_response(Tenancy(connection).create_lease(payload.model_dump(mode="json")))


@router.put("/api/v1/leases/{lease_id}", response_model=LeaseResponse)
def update_lease(lease_id: PositiveId, payload: LeaseWrite, connection: WriteConnection) -> LeaseResponse:
    return _lease_response(Tenancy(connection).update_lease(lease_id, payload.model_dump(mode="json")))


@router.delete("/api/v1/leases/{lease_id}", response_model=TenancyDeleteResponse)
def delete_lease(lease_id: PositiveId, connection: WriteConnection) -> dict:
    return Tenancy(connection).delete_lease(lease_id)
