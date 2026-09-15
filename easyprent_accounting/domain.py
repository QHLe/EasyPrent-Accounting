from __future__ import annotations

import datetime
from decimal import Decimal
from typing import NewType

# Domain Errors
class DomainError(Exception):
    """Base class for all domain errors."""
    
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


# Simple value types using NewType for strict static typing
Money = NewType("Money", Decimal)
Percentage = NewType("Percentage", Decimal)

class DateRange:
    """A period bounded by a start and end date (inclusive)."""
    
    def __init__(self, start: datetime.date, end: datetime.date) -> None:
        if end < start:
            raise DomainError("invalid_date_range", "End date cannot be before start date.")
        self.start = start
        self.end = end
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DateRange):
            return NotImplemented
        return self.start == other.start and self.end == other.end

    def __hash__(self) -> int:
        return hash((self.start, self.end))

    def __repr__(self) -> str:
        return f"DateRange(start={self.start.isoformat()}, end={self.end.isoformat()})"
