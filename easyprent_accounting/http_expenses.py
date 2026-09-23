"""Expense transport contracts and synchronous HTTP use cases."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from pydantic import Field

from .expenses import Expenses
from .http_db import ReadConnection, WriteConnection
from .http_models import HttpModel, MoneyModel


ObjectType = Literal["property", "building", "unit", "room"]
ChargeType = Literal["one_time", "total", "monthly", "quarterly", "yearly", "consumption"]
PositiveId = Annotated[int, Path(gt=0)]


class ExpenseWrite(MoneyModel):
    object_type: ObjectType
    object_id: Annotated[int, Field(strict=True, gt=0)]
    expense_category: str
    beneficiary_name: str | None = None
    label: str | None = None
    allocation_method: str
    charge_type: ChargeType
    booking_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    meter_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    consumption_unit: str | None = None
    consumption_value: str | None = None
    conversion_factor: str | None = None

    def domain_payload(self) -> dict:
        return self.model_dump(mode="json", exclude_none=True)


class ExpenseResponse(HttpModel):
    id: int
    object_type: ObjectType
    object_id: int
    expense_category: str
    beneficiary_name: str
    label: str
    amount: str
    allocation_method: str
    charge_type: Literal["one_time", "monthly", "quarterly", "yearly", "consumption"]
    recurrence: str
    interval: str | None = None
    meter_id: int | None = None
    meter_unit: str | None = None
    consumption_unit: str | None = None
    conversion_factor: str | None = None
    consumption_value: str | None = None
    effective_consumption_value: str | None = None
    total_amount: str | None = None
    booking_date: str | None = None
    period_start: str
    period_end: str | None = None
    is_open_ended: bool
    is_archived: bool = False
    archived_at: str | None = None


class ExpenseCategoryResponse(HttpModel):
    expense_category: str
    beneficiary_name: str
    expense_count: int


class ExpenseListResponse(HttpModel):
    expenses: list[ExpenseResponse]
    expense_categories: list[ExpenseCategoryResponse]


class ExpenseDevelopmentCategory(HttpModel):
    expense_category: str
    amount: str | None
    has_uncalculated_expense: bool


class ExpenseDevelopmentMonth(HttpModel):
    month: int
    total_amount: str | None
    has_uncalculated_expense: bool
    categories: list[ExpenseDevelopmentCategory]


class ExpenseDevelopmentResponse(HttpModel):
    year: int
    total_amount: str | None
    has_uncalculated_expense: bool
    categories: list[ExpenseDevelopmentCategory]
    months: list[ExpenseDevelopmentMonth]


class ExpenseLifecycleResponse(HttpModel):
    resource: Literal["expenses"]
    id: int
    is_archived: bool
    archived_at: str | None = None


class ExpenseDeleteResponse(HttpModel):
    resource: Literal["expenses"]
    id: int
    deleted: bool


def _expense_response(row: dict) -> ExpenseResponse:
    """Project the domain result to the stable HTTP fields."""
    fields = {
        field: row.get(field)
        for field in ExpenseResponse.model_fields
        if field in row
    } | {"interval": row.get("interval", row.get("interval_name"))}
    for field in ("amount", "conversion_factor", "consumption_value", "effective_consumption_value", "total_amount"):
        if fields.get(field) is not None:
            fields[field] = str(fields[field])
    return ExpenseResponse.model_validate(fields)


router = APIRouter(prefix="/api/v1/expenses", tags=["Expenses"])


@router.get("", response_model=ExpenseListResponse)
def list_expenses(connection: ReadConnection) -> ExpenseListResponse:
    result = Expenses(connection).list_expenses()
    return ExpenseListResponse(
        expenses=[_expense_response(row) for row in result["expenses"]],
        expense_categories=[ExpenseCategoryResponse.model_validate(row) for row in result["expense_categories"]],
    )


@router.get(
    "/development",
    response_model=ExpenseDevelopmentResponse,
    operation_id="expenses_get_expense_development",
)
def expense_development(
    year: Annotated[int, Query(ge=1900, le=9998)],
    connection: ReadConnection,
) -> ExpenseDevelopmentResponse:
    return ExpenseDevelopmentResponse.model_validate(Expenses(connection).development_for_year(year))


@router.post("", status_code=201, response_model=ExpenseResponse)
def create_expense(payload: ExpenseWrite, connection: WriteConnection) -> ExpenseResponse:
    return _expense_response(Expenses(connection).create(payload.domain_payload()))


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(expense_id: PositiveId, payload: ExpenseWrite, connection: WriteConnection) -> ExpenseResponse:
    return _expense_response(Expenses(connection).update(expense_id, payload.domain_payload()))


@router.post("/{expense_id}/archive", response_model=ExpenseLifecycleResponse)
def archive_expense(expense_id: PositiveId, connection: WriteConnection) -> dict:
    return Expenses(connection).archive(expense_id)


@router.post("/{expense_id}/restore", response_model=ExpenseLifecycleResponse)
def restore_expense(expense_id: PositiveId, connection: WriteConnection) -> dict:
    return Expenses(connection).restore(expense_id)


@router.delete("/{expense_id}", response_model=ExpenseDeleteResponse)
def delete_expense(expense_id: PositiveId, connection: WriteConnection) -> dict:
    return Expenses(connection).delete(expense_id)
