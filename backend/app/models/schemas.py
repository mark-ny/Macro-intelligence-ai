"""Shared Pydantic response models.

Treasury is fully typed since that module is implemented this milestone.
Other modules get their schemas added in the same commit that implements
them — see README > Roadmap.
"""
from typing import Optional

from pydantic import BaseModel


class YieldCurveResponse(BaseModel):
    yield_curve: dict[str, Optional[float]]
    spreads: dict[str, Optional[float]]
    inverted: bool
    as_of: Optional[str]


class YieldHistoryPoint(BaseModel):
    date: str
    value: float


class RefreshResult(BaseModel):
    rows_upserted: int
    series_with_errors: dict[str, str]


class ModuleStatus(BaseModel):
    """Returned by every not-yet-implemented module so the frontend can
    render an honest "coming soon" state instead of fake data."""
    module: str
    status: str = "scaffolded"
    implemented: bool = False
