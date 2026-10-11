"""A small cron expression parser for cron-based rolling policies.

Supports the standard five-field form ``minute hour day-of-month month
day-of-week`` and the six-field form with a leading ``seconds`` field. Each
field accepts ``*``, lists (``a,b,c``), ranges (``a-b``), and steps
(``*/n`` or ``a-b/n``). Month and day-of-week names (``JAN``..``DEC``,
``SUN``..``SAT``) are recognised, and ``0``/``7`` both mean Sunday.

When both day-of-month and day-of-week are restricted, a date matches if
*either* one matches (the common cron convention).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Set

_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_DOWS = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}

_MAX_SEARCH_DAYS = 366 * 8


class CronExpression:
    """A parsed cron expression that can test and schedule datetimes."""

    def __init__(self, expression: str) -> None:
        fields = str(expression).split()
        if len(fields) == 5:
            self.has_seconds = False
            second, minute, hour, dom, month, dow = "0", *fields
        elif len(fields) == 6:
            self.has_seconds = True
            second, minute, hour, dom, month, dow = fields
        else:
            raise ValueError(
                "cron expression must have 5 or 6 fields: " f"{expression!r}"
            )
        self.expression = " ".join(fields)
        self._second = self._parse_field(second, 0, 59, {})
        self._minute = self._parse_field(minute, 0, 59, {})
        self._hour = self._parse_field(hour, 0, 23, {})
        self._dom = self._parse_field(dom, 1, 31, {})
        self._month = self._parse_field(month, 1, 12, _MONTHS)
        self._dow = self._parse_field(dow, 0, 7, _DOWS)
        if 7 in self._dow:
            self._dow.discard(7)
            self._dow.add(0)
        if not self._second:
            raise ValueError("no valid seconds in cron expression")
        self._dom_restricted = dom.strip() != "*"
        self._dow_restricted = dow.strip() != "*"

    @staticmethod
    def _parse_field(
        field: str, low: int, high: int, names: Dict[str, int]
    ) -> Set[int]:
        values: Set[int] = set()
        for part in field.split(","):
            values.update(_parse_part(part, low, high, names))
        return values

    def _date_matches(self, moment: datetime) -> bool:
        dom_ok = moment.day in self._dom
        cron_dow = (moment.weekday() + 1) % 7
        dow_ok = cron_dow in self._dow
        if self._dom_restricted and self._dow_restricted:
            return dom_ok or dow_ok
        if self._dom_restricted:
            return dom_ok
        if self._dow_restricted:
            return dow_ok
        return True

    def matches(self, moment: datetime) -> bool:
        """Return ``True`` when *moment* satisfies every cron field."""
        return (
            moment.second in self._second
            and moment.minute in self._minute
            and moment.hour in self._hour
            and moment.month in self._month
            and self._date_matches(moment)
        )

    def next_after(self, timestamp: float) -> float:
        """Return the epoch time of the first match strictly after *timestamp*."""
        current = datetime.fromtimestamp(timestamp).replace(microsecond=0)
        current += timedelta(seconds=1)
        start_date = current.date()
        for offset in range(_MAX_SEARCH_DAYS):
            day = start_date + timedelta(days=offset)
            if day.month not in self._month:
                continue
            probe = current if offset == 0 else datetime(day.year, day.month, day.day)
            if not self._date_matches(probe):
                continue
            candidate = self._first_time(day, current if offset == 0 else None)
            if candidate is not None:
                return candidate.timestamp()
        raise ValueError("no matching time found within search horizon")

    def _first_time(self, day, lower):
        midnight = datetime(day.year, day.month, day.day)
        for hour in sorted(self._hour):
            if lower is not None and hour < lower.hour:
                continue
            for minute in sorted(self._minute):
                if lower is not None and hour == lower.hour and minute < lower.minute:
                    continue
                for second in sorted(self._second):
                    if (
                        lower is not None
                        and hour == lower.hour
                        and minute == lower.minute
                        and second < lower.second
                    ):
                        continue
                    return midnight.replace(hour=hour, minute=minute, second=second)
        return None


def _parse_part(part: str, low: int, high: int, names: Dict[str, int]) -> Set[int]:
    step = 1
    if "/" in part:
        base, _, step_text = part.partition("/")
        try:
            step = int(step_text)
        except ValueError as exc:
            raise ValueError(f"invalid step in cron field: {part!r}") from exc
        if step <= 0:
            raise ValueError(f"invalid step in cron field: {part!r}")
        part = base
    if part == "*":
        start, end = low, high
    elif "-" in part:
        first, _, last = part.partition("-")
        start = _field_value(first, names, low, high)
        end = _field_value(last, names, low, high)
    else:
        start = end = _field_value(part, names, low, high)
    if start > end:
        raise ValueError(f"invalid range in cron field: {part!r}")
    return set(range(start, end + 1, step))


def _field_value(token: str, names: Dict[str, int], low: int, high: int) -> int:
    text = token.strip()
    if text.upper() in names:
        return names[text.upper()]
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"invalid value in cron field: {token!r}") from exc
    if not low <= value <= high:
        raise ValueError(f"value out of range in cron field: {token!r}")
    return value
