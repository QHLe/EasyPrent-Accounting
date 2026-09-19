"""Dashboard transport models and routes."""

from __future__ import annotations

from fastapi import APIRouter

from .dashboard import Dashboard
from .http_db import ReadConnection
from .http_models import HttpModel


class DashboardSummaryCounts(HttpModel):
    properties: int
    buildings: int
    units: int
    rooms: int
    meters: int
    tenants: int
    leases: int
    expenses: int
    depreciation_assets: int


class DashboardRole(HttpModel):
    full_name: str
    email: str
    role: str
    organization_name: str


class DashboardSummaryResponse(HttpModel):
    summary: DashboardSummaryCounts
    roles: list[DashboardRole]


router = APIRouter(tags=["Dashboard"])


@router.get("/api/v1/dashboard/summary", response_model=DashboardSummaryResponse, operation_id="get_dashboard_summary")
def summary(connection: ReadConnection) -> HttpModel:
    result = Dashboard(connection).summary()
    return DashboardSummaryResponse.model_validate(result)

