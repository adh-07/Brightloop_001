from datetime import UTC, date, datetime


class Clock:
    """Injectable clock for deterministic time testing."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return datetime.now(UTC).date()


class FrozenClock(Clock):
    """Clock frozen at a specific date/datetime for testing."""

    def __init__(self, current_date: date | None = None, current_datetime: datetime | None = None):
        self._date = current_date
        self._datetime = current_datetime

    def now(self) -> datetime:
        if self._datetime is not None:
            return self._datetime
        if self._date is not None:
            return datetime(self._date.year, self._date.month, self._date.day, tzinfo=UTC)
        return super().now()

    def today(self) -> date:
        if self._date is not None:
            return self._date
        if self._datetime is not None:
            return self._datetime.date()
        return super().today()


_default_clock: Clock = Clock()


def get_clock() -> Clock:
    return _default_clock


def set_clock(clock: Clock) -> None:
    global _default_clock
    _default_clock = clock


def reset_clock() -> None:
    global _default_clock
    _default_clock = Clock()

