"""Time source and month helpers.

Every service asks the Clock for the time instead of calling datetime.now(),
so the demo can fast-forward a lesson and the tests can fix the time.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from ..data import SettingsRepository

OFFSET_KEY = "clock_offset_minutes"


class Clock:
    def __init__(self, settings: SettingsRepository | None = None) -> None:
        self.settings = settings

    def offset_minutes(self) -> int:
        if self.settings is None:
            return 0
        return int(self.settings.get(OFFSET_KEY, "0") or 0)

    def now(self) -> datetime:
        return datetime.now().replace(second=0, microsecond=0) + timedelta(
            minutes=self.offset_minutes()
        )

    def today(self) -> date:
        return self.now().date()

    def advance(self, minutes: int) -> None:
        if self.settings is not None:
            self.settings.set(OFFSET_KEY, str(self.offset_minutes() + minutes))

    def reset(self) -> None:
        if self.settings is not None:
            self.settings.set(OFFSET_KEY, "0")


class FixedClock(Clock):
    """A clock that only moves when told to; used by the tests and the seeder."""

    def __init__(self, at: datetime) -> None:
        super().__init__(None)
        self.at = at

    def now(self) -> datetime:
        return self.at

    def advance(self, minutes: int) -> None:
        self.at += timedelta(minutes=minutes)


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def month_bounds(key: str) -> tuple[datetime, datetime]:
    year, month = (int(part) for part in key.split("-"))
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def shift_month(key: str, by: int) -> str:
    year, month = (int(part) for part in key.split("-"))
    index = year * 12 + (month - 1) + by
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def recent_months(key: str, count: int) -> list[str]:
    """The `count` months ending with `key`, oldest first."""
    return [shift_month(key, -offset) for offset in range(count - 1, -1, -1)]


def month_label(key: str) -> str:
    start, _ = month_bounds(key)
    return start.strftime("%b %Y")
