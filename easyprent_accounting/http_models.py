"""Shared HTTP payload shapes.

These models belong to the transport boundary. Domain values and rules remain
independent of Pydantic and are constructed by the use case that handles a
request.
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


class HttpModel(BaseModel):
    """Base for payloads with an explicit, closed field set."""

    model_config = ConfigDict(extra="forbid")


class IdModel(HttpModel):
    """A database entity ID in an HTTP payload."""

    id: Annotated[int, Field(strict=True, gt=0)]


class MoneyModel(HttpModel):
    """A finite amount represented as a decimal string in JSON."""

    amount: Decimal

    @field_validator("amount", mode="before", json_schema_input_type=str)
    @classmethod
    def _require_decimal_input(cls, value: object) -> object:
        if not isinstance(value, (str, Decimal)):
            raise ValueError("Money must be supplied as a decimal string.")
        return value

    @field_validator("amount")
    @classmethod
    def _require_finite_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Money must be finite.")
        return value

    @field_serializer("amount", when_used="json")
    def _serialize_amount(self, value: Decimal) -> str:
        return str(value)


class DateRangeModel(HttpModel):
    """An inclusive period with date-only boundaries."""

    start: datetime.date
    end: datetime.date

    @field_validator("start", "end", mode="before")
    @classmethod
    def _require_calendar_date(cls, value: object) -> object:
        if isinstance(value, datetime.datetime):
            raise ValueError("Date range boundaries must be calendar dates.")
        if isinstance(value, datetime.date):
            return value
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
        raise ValueError("Date range boundaries must be ISO calendar dates.")

    @model_validator(mode="after")
    def _require_ordered_range(self) -> Self:
        if self.end < self.start:
            raise ValueError("End date cannot be before start date.")
        return self


class ErrorDetail(HttpModel):
    """A stable machine code and a readable explanation."""

    code: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1)]


class ErrorResponse(HttpModel):
    """The common HTTP error envelope."""

    error: ErrorDetail
