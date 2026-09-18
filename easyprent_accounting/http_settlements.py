"""Settlement transport contracts and synchronous HTTP use cases."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Self

from fastapi import APIRouter, Path, Query, Request, Response
from pydantic import Field, model_validator

from .http_db import ReadConnection, WriteConnection
from .http_models import HttpModel
from .settlement_runs import (
    consider_all_settlement_payments,
    create_or_open_settlement_run,
    find_settlement_run_id,
    get_settlement_run_overview,
    import_gnucash_payments_for_period,
    refresh_settlement_run_payments,
    set_settlement_payment_considered,
)
from .settlements import Settlements


class AllocationPeriodResponse(HttpModel):
    period_start: date
    period_end: date
    period_amount: Decimal
    basis_value: Decimal
    basis_total: Decimal
    share: Decimal


class SettlementLineResponse(HttpModel):
    source_id: int
    label: str
    allocation_method: str
    period_amount: Decimal
    basis_value: Decimal
    basis_total: Decimal
    charge_type: str
    recurrence: str
    interval_name: str | None
    share: Decimal
    expense_category: str
    allocation_periods: list[AllocationPeriodResponse]
    tenant_consumption_value: Decimal | None = None
    consumption_unit: str | None = None
    consumption_value: Decimal | None = None


class SettlementLeaseResponse(HttpModel):
    lease_id: int
    tenant_name: str
    unit_label: str
    billing_period_start: date
    billing_period_end: date
    allocated_costs: Decimal
    advances_paid: Decimal
    balance: Decimal
    line_items: list[SettlementLineResponse]


class SettlementTotalsResponse(HttpModel):
    costs: Decimal
    advances: Decimal
    balance: Decimal


class SettlementResponse(HttpModel):
    property_id: int | None
    unit_id: int | None
    period_start: date
    period_end: date
    results: list[SettlementLeaseResponse]
    totals: SettlementTotalsResponse


class SettlementRunWrite(HttpModel):
    property_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    unit_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    year: Annotated[int, Field(strict=True, ge=1900, le=9999)]

    @model_validator(mode="after")
    def _require_one_target(self) -> Self:
        if (self.property_id is None) == (self.unit_id is None):
            raise ValueError("settlement run requires exactly one property or standalone unit")
        return self


class SettlementRunResponse(HttpModel):
    id: str
    property_id: int | None
    unit_id: int | None
    target_label: str
    year: int
    period_start: date
    period_end: date
    status: str


class SettlementRunLookupResponse(HttpModel):
    id: str | None


class SettlementPaymentResponse(HttpModel):
    split_guid: str
    lease_id: int
    tenant_name: str
    booking_date: date
    amount: Decimal
    description: str
    warning: str | None = None
    assigned_settlement_id: str | None = None


class MissingAccountLeaseResponse(HttpModel):
    lease_id: int
    tenant_name: str


class SettlementRunOverviewResponse(HttpModel):
    run: SettlementRunResponse
    settlement: SettlementResponse
    open_payments: list[SettlementPaymentResponse]
    considered_payments: list[SettlementPaymentResponse]
    outside_payments: list[SettlementPaymentResponse]
    missing_account_leases: list[MissingAccountLeaseResponse]


class SettlementPeriodWrite(HttpModel):
    property_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    unit_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def _require_one_target(self) -> Self:
        if (self.property_id is None) == (self.unit_id is None):
            raise ValueError("settlement requires exactly one property or standalone unit")
        return self


class PaymentImportResponse(HttpModel):
    imported: int
    existing: int
    accounts: int


class SettlementRefreshResponse(HttpModel):
    imported: PaymentImportResponse = Field(alias="import")
    settlement: SettlementResponse


class SettlementRunRefreshResponse(HttpModel):
    imported: PaymentImportResponse = Field(alias="import")
    overview: SettlementRunOverviewResponse


router = APIRouter(tags=["Settlements"])


@router.get("/api/v1/settlements", response_model=SettlementResponse)
def calculate_settlement(
    period_start: date,
    period_end: date,
    connection: ReadConnection,
    property_id: Annotated[int | None, Query(gt=0)] = None,
    unit_id: Annotated[int | None, Query(gt=0)] = None,
) -> SettlementResponse:
    if (property_id is None) == (unit_id is None):
        raise ValueError("settlement requires exactly one property or standalone unit")
    result = Settlements(connection).for_period(
        property_id, period_start.isoformat(), period_end.isoformat(), unit_id
    )
    return SettlementResponse.model_validate(result)


@router.get("/api/v1/settlement-runs", response_model=SettlementRunLookupResponse)
def find_settlement_run(
    year: Annotated[int, Query(ge=1900, le=9999)],
    connection: ReadConnection,
    property_id: Annotated[int | None, Query(gt=0)] = None,
    unit_id: Annotated[int | None, Query(gt=0)] = None,
) -> SettlementRunLookupResponse:
    if (property_id is None) == (unit_id is None):
        raise ValueError("settlement run requires exactly one property or standalone unit")
    return SettlementRunLookupResponse(
        id=find_settlement_run_id(connection, property_id, unit_id, year)
    )


@router.post("/api/v1/settlement-runs", response_model=SettlementRunResponse)
def create_settlement_run(
    payload: SettlementRunWrite,
    response: Response,
    connection: WriteConnection,
) -> SettlementRunResponse:
    run, created = create_or_open_settlement_run(connection, payload.model_dump())
    response.status_code = 201 if created else 200
    return SettlementRunResponse.model_validate(run)


@router.get("/api/v1/settlement-runs/{settlement_id}", response_model=SettlementRunOverviewResponse)
def settlement_run_overview(
    settlement_id: Annotated[str, Path(min_length=1)],
    connection: ReadConnection,
) -> SettlementRunOverviewResponse:
    return SettlementRunOverviewResponse.model_validate(
        get_settlement_run_overview(connection, settlement_id)
    )


@router.post("/api/v1/settlements/refresh", response_model=SettlementRefreshResponse)
def refresh_settlement(
    payload: SettlementPeriodWrite,
    request: Request,
    connection: WriteConnection,
) -> SettlementRefreshResponse:
    period_start = payload.period_start.isoformat()
    period_end = payload.period_end.isoformat()
    imported = import_gnucash_payments_for_period(
        connection, payload.property_id, period_start, period_end, payload.unit_id,
        reader=request.app.state.gnucash_reader,
    )
    settlement = Settlements(connection).for_period(
        payload.property_id, period_start, period_end, payload.unit_id
    )
    return SettlementRefreshResponse.model_validate({"import": imported, "settlement": settlement})


@router.post(
    "/api/v1/settlement-runs/{settlement_id}/payments/refresh",
    response_model=SettlementRunRefreshResponse,
)
def refresh_run_payments(
    settlement_id: Annotated[str, Path(min_length=1)],
    request: Request,
    connection: WriteConnection,
) -> SettlementRunRefreshResponse:
    imported = refresh_settlement_run_payments(
        connection, settlement_id, reader=request.app.state.gnucash_reader
    )
    overview = get_settlement_run_overview(connection, settlement_id)
    return SettlementRunRefreshResponse.model_validate({"import": imported, "overview": overview})


@router.post(
    "/api/v1/settlement-runs/{settlement_id}/payments/consider-all",
    response_model=SettlementRunOverviewResponse,
)
def consider_all_payments(
    settlement_id: Annotated[str, Path(min_length=1)],
    connection: WriteConnection,
) -> SettlementRunOverviewResponse:
    return SettlementRunOverviewResponse.model_validate(
        consider_all_settlement_payments(connection, settlement_id)
    )


@router.post(
    "/api/v1/settlement-runs/{settlement_id}/payments/{split_guid}/consider",
    response_model=SettlementRunOverviewResponse,
)
def consider_payment(
    settlement_id: Annotated[str, Path(min_length=1)],
    split_guid: Annotated[str, Path(min_length=1)],
    connection: WriteConnection,
) -> SettlementRunOverviewResponse:
    return SettlementRunOverviewResponse.model_validate(
        set_settlement_payment_considered(connection, settlement_id, split_guid, True)
    )


@router.post(
    "/api/v1/settlement-runs/{settlement_id}/payments/{split_guid}/unassign",
    response_model=SettlementRunOverviewResponse,
)
def unassign_payment(
    settlement_id: Annotated[str, Path(min_length=1)],
    split_guid: Annotated[str, Path(min_length=1)],
    connection: WriteConnection,
) -> SettlementRunOverviewResponse:
    return SettlementRunOverviewResponse.model_validate(
        set_settlement_payment_considered(connection, settlement_id, split_guid, False)
    )
