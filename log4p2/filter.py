"""Filters decide whether a record reaches an appender, using log4j's tri-state
``ACCEPT`` / ``DENY`` / ``NEUTRAL`` protocol.

Filters that test a condition accept ``onMatch`` / ``onMismatch`` (each one of
``"accept"``, ``"deny"``, ``"neutral"``) so they compose cleanly with
``AndFilter`` / ``OrFilter`` / ``NotFilter``.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from enum import IntEnum
from typing import Union

from .levels import Level, getLevel
from .message import MapMessage, StructuredDataMessage
from .record import LogRecord


class FilterReply(IntEnum):
    DENY = -1
    NEUTRAL = 0
    ACCEPT = 1


_REPLY_NAMES = {
    "accept": FilterReply.ACCEPT,
    "deny": FilterReply.DENY,
    "neutral": FilterReply.NEUTRAL,
}


def _parse_reply(value) -> FilterReply:
    if isinstance(value, FilterReply):
        return value
    try:
        return _REPLY_NAMES[str(value).lower()]
    except KeyError:
        raise ValueError(
            f"reply must be 'accept', 'deny', or 'neutral', got {value!r}"
        ) from None


class Filter:
    """Base class. Return one of :class:`FilterReply` from :meth:`decide`."""

    def __init__(self, onMatch="neutral", onMismatch="deny") -> None:
        self.onMatch = _parse_reply(onMatch)
        self.onMismatch = _parse_reply(onMismatch)

    def _reply(self, matched: bool) -> FilterReply:
        return self.onMatch if matched else self.onMismatch

    def decide(self, record: LogRecord) -> FilterReply:  # pragma: no cover
        return FilterReply.NEUTRAL


class AcceptAllFilter(Filter):
    """Accept every record."""

    def decide(self, record: LogRecord) -> FilterReply:
        return FilterReply.ACCEPT


class DenyAllFilter(Filter):
    """Deny every record."""

    def decide(self, record: LogRecord) -> FilterReply:
        return FilterReply.DENY


class ThresholdFilter(Filter):
    """Match records at or above *level* (deny the rest by default)."""

    def __init__(
        self,
        level: Union[str, int, Level],
        onMatch="neutral",
        onMismatch="deny",
    ) -> None:
        super().__init__(onMatch, onMismatch)
        self.level = getLevel(level)

    def decide(self, record: LogRecord) -> FilterReply:
        return self._reply(int(record.level) >= int(self.level))


class LevelMatchFilter(Filter):
    """Match records whose level equals *level* exactly."""

    def __init__(
        self,
        level: Union[str, int, Level],
        onMatch="neutral",
        onMismatch="deny",
    ) -> None:
        super().__init__(onMatch, onMismatch)
        self.level = getLevel(level)

    def decide(self, record: LogRecord) -> FilterReply:
        return self._reply(int(record.level) == int(self.level))


class LevelRangeFilter(Filter):
    """Match records whose level falls within ``[min_level, max_level]``."""

    def __init__(
        self,
        min_level: Union[str, int, Level] = "ALL",
        max_level: Union[str, int, Level] = "OFF",
        onMatch="neutral",
        onMismatch="deny",
    ) -> None:
        super().__init__(onMatch, onMismatch)
        self.min_level = getLevel(min_level)
        self.max_level = getLevel(max_level)

    def decide(self, record: LogRecord) -> FilterReply:
        return self._reply(
            int(self.min_level) <= int(record.level) <= int(self.max_level)
        )


class RegexFilter(Filter):
    """Match a regex against a record field.

    *field* is one of the ``LogRecord`` attributes, most commonly ``message``
    (the default) or ``name``. By default a match lets the record through and a
    miss denies it; set ``on_match='deny'`` to invert, or pass explicit
    ``onMatch`` / ``onMismatch`` replies.
    """

    def __init__(
        self,
        pattern: str,
        field: str = "message",
        on_match: str = "accept",
        onMatch=None,
        onMismatch=None,
    ) -> None:
        if onMatch is None and onMismatch is None:
            if on_match not in ("accept", "deny"):
                raise ValueError("on_match must be 'accept' or 'deny'")
            if on_match == "accept":
                onMatch, onMismatch = "neutral", "deny"
            else:
                onMatch, onMismatch = "deny", "neutral"
        super().__init__(
            onMatch if onMatch is not None else "neutral",
            onMismatch if onMismatch is not None else "deny",
        )
        self.regex = re.compile(pattern)
        self.field = field
        self.on_match = on_match

    def decide(self, record: LogRecord) -> FilterReply:
        if self.field == "message":
            value = record.getMessage()
        elif self.field == "name":
            value = record.name
        elif self.field == "level":
            value = record.level.name
        else:
            value = str(record.context.get(self.field, ""))
        return self._reply(bool(self.regex.search(value)))


class MarkerFilter(Filter):
    """Match records carrying *marker* (or a marker derived from it).

    *marker* may be a :class:`~log4p.marker.Marker` or a name, which is looked
    up (and created) in the marker registry.
    """

    def __init__(
        self,
        marker,
        on_match: str = "accept",
        onMatch=None,
        onMismatch=None,
    ) -> None:
        from .marker import getMarker

        if onMatch is None and onMismatch is None:
            if on_match not in ("accept", "deny"):
                raise ValueError("on_match must be 'accept' or 'deny'")
            if on_match == "accept":
                onMatch, onMismatch = "neutral", "deny"
            else:
                onMatch, onMismatch = "deny", "neutral"
        super().__init__(
            onMatch if onMatch is not None else "neutral",
            onMismatch if onMismatch is not None else "deny",
        )
        self.marker = marker if hasattr(marker, "isInstanceOf") else getMarker(str(marker))
        self.on_match = on_match

    def decide(self, record: LogRecord) -> FilterReply:
        present = bool(record.marker) and record.marker.isInstanceOf(self.marker)
        return self._reply(present)


class ContextMapFilter(Filter):
    """Match records whose context (MDC) contains the configured pairs.

    *properties* maps context keys to expected values. With ``operator="and"``
    (default) every pair must match; with ``"or"`` any single pair matching is
    enough.
    """

    def __init__(
        self,
        properties,
        operator: str = "and",
        onMatch="neutral",
        onMismatch="deny",
    ) -> None:
        super().__init__(onMatch, onMismatch)
        self.properties = dict(properties)
        op = operator.lower()
        if op not in ("and", "or"):
            raise ValueError("operator must be 'and' or 'or'")
        self.operator = op

    def decide(self, record: LogRecord) -> FilterReply:
        if not self.properties:
            return self._reply(False)
        checks = (
            str(record.context.get(key, "")) == str(value)
            for key, value in self.properties.items()
        )
        matched = all(checks) if self.operator == "and" else any(checks)
        return self._reply(matched)


class MapFilter(Filter):
    """Match :class:`MapMessage` records by their key/value data (log4j's
    ``MapFilter``).

    *properties* maps message keys to expected values. With ``operator="and"``
    (default) every pair must match; with ``"or"`` any single pair suffices.
    With no properties, any map message matches.
    """

    def __init__(
        self,
        properties=None,
        operator: str = "and",
        onMatch="neutral",
        onMismatch="deny",
    ) -> None:
        super().__init__(onMatch, onMismatch)
        self.properties = dict(properties or {})
        op = operator.lower()
        if op not in ("and", "or"):
            raise ValueError("operator must be 'and' or 'or'")
        self.operator = op

    def decide(self, record: LogRecord) -> FilterReply:
        message = record.message
        if not isinstance(message, MapMessage):
            return self._reply(False)
        if not self.properties:
            return self._reply(True)
        checks = (
            str(message.data.get(key, "")) == str(value)
            for key, value in self.properties.items()
        )
        matched = all(checks) if self.operator == "and" else any(checks)
        return self._reply(matched)


class StructuredDataFilter(Filter):
    """Match :class:`StructuredDataMessage` records (log4j's filter of the same
    name).

    *properties* maps structured-data keys to expected values; *type* optionally
    restricts matches to a structured-data type. With ``operator="and"``
    (default) every pair must match; with ``"or"`` any single pair suffices.
    With no properties and no type, any structured-data record matches.
    """

    def __init__(
        self,
        properties=None,
        type=None,
        operator: str = "and",
        onMatch="neutral",
        onMismatch="deny",
    ) -> None:
        super().__init__(onMatch, onMismatch)
        self.properties = dict(properties or {})
        self.type = type
        op = operator.lower()
        if op not in ("and", "or"):
            raise ValueError("operator must be 'and' or 'or'")
        self.operator = op

    def decide(self, record: LogRecord) -> FilterReply:
        message = record.message
        if not isinstance(message, StructuredDataMessage):
            return self._reply(False)
        if self.type is not None and message.type != self.type:
            return self._reply(False)
        if not self.properties:
            return self._reply(True)
        checks = (
            str(message.data.get(key, "")) == str(value)
            for key, value in self.properties.items()
        )
        matched = all(checks) if self.operator == "and" else any(checks)
        return self._reply(matched)


class DynamicThresholdFilter(Filter):
    """Per-context-key threshold: the effective level depends on *key*.

    *levels* maps a context value to a level name/int. When the record's
    context value has no entry, *default_threshold* is used. Records at or above
    the resulting threshold match.
    """

    def __init__(
        self,
        key: str,
        levels,
        default_threshold="ERROR",
        onMatch="neutral",
        onMismatch="deny",
    ) -> None:
        super().__init__(onMatch, onMismatch)
        self.key = key
        self.levels = {str(k): getLevel(v) for k, v in dict(levels).items()}
        self.default_threshold = getLevel(default_threshold)

    def decide(self, record: LogRecord) -> FilterReply:
        value = str(record.context.get(self.key, ""))
        threshold = self.levels.get(value, self.default_threshold)
        return self._reply(int(record.level) >= int(threshold))


class NoMarkerFilter(Filter):
    """Match records that carry no marker."""

    def __init__(self, onMatch="neutral", onMismatch="deny") -> None:
        super().__init__(onMatch, onMismatch)

    def decide(self, record: LogRecord) -> FilterReply:
        return self._reply(record.marker is None)


class BurstFilter(Filter):
    """Rate-limit records with a token bucket (log4j's ``BurstFilter``).

    *rate* is the steady number of events per second allowed and *maxBurst* the
    bucket capacity. Records at or above *level* bypass the limit.
    """

    def __init__(
        self,
        rate: float = 10.0,
        maxBurst: int = 100,
        level: Union[str, int, Level, None] = None,
        onMatch="neutral",
        onMismatch="deny",
    ) -> None:
        super().__init__(onMatch, onMismatch)
        self.rate = float(rate)
        self.maxBurst = int(maxBurst)
        self.level = getLevel(level) if level is not None else None
        self._lock = threading.Lock()
        self._tokens = float(maxBurst)
        self._last = time.monotonic()

    def _allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            self._tokens = min(
                self.maxBurst, self._tokens + (now - self._last) * self.rate
            )
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def decide(self, record: LogRecord) -> FilterReply:
        if self.level is not None and int(record.level) >= int(self.level):
            return self._reply(True)
        return self._reply(self._allow())


class TimeFilter(Filter):
    """Match records whose time-of-day falls in ``[start, end]`` (log4j's
    ``TimeFilter``).

    *start* and *end* are ``"HH:MM"`` or ``"HH:MM:SS"``. When *start* is later
    than *end* the window wraps across midnight (e.g. ``22:00``-``06:00``).
    """

    def __init__(self, start: str, end: str, onMatch="neutral", onMismatch="deny"):
        super().__init__(onMatch, onMismatch)
        self.start = start
        self.end = end
        self._start = _parse_time_of_day(start)
        self._end = _parse_time_of_day(end)

    def decide(self, record: LogRecord) -> FilterReply:
        moment = datetime.fromtimestamp(record.created)
        current = moment.hour * 3600 + moment.minute * 60 + moment.second
        if self._start <= self._end:
            matched = self._start <= current <= self._end
        else:
            matched = current >= self._start or current <= self._end
        return self._reply(matched)


def _parse_time_of_day(value: str) -> int:
    parts = str(value).split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid time-of-day: {value!r}")
    try:
        numbers = [int(part) for part in parts]
    except ValueError as exc:  # pragma: no cover - covered via message below
        raise ValueError(f"invalid time-of-day: {value!r}") from exc
    hour, minute = numbers[0], numbers[1]
    second = numbers[2] if len(numbers) == 3 else 0
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError(f"invalid time-of-day: {value!r}")
    return hour * 3600 + minute * 60 + second


class _CompositeFilter(Filter):
    """Base for filters that combine child filters."""

    def __init__(self, *filters: Filter) -> None:
        flat: list = []
        for item in filters:
            if isinstance(item, (list, tuple)):
                flat.extend(item)
            else:
                flat.append(item)
        self.filters = flat


class AndFilter(_CompositeFilter):
    """Accept only when every child accepts (deny on any denial)."""

    def decide(self, record: LogRecord) -> FilterReply:
        if not self.filters:
            return FilterReply.NEUTRAL
        saw_neutral = False
        for filt in self.filters:
            reply = filt.decide(record)
            if reply == FilterReply.DENY:
                return FilterReply.DENY
            if reply == FilterReply.NEUTRAL:
                saw_neutral = True
        return FilterReply.NEUTRAL if saw_neutral else FilterReply.ACCEPT


class OrFilter(_CompositeFilter):
    """Accept when any child accepts (deny only when every child denies)."""

    def decide(self, record: LogRecord) -> FilterReply:
        if not self.filters:
            return FilterReply.NEUTRAL
        all_deny = True
        for filt in self.filters:
            reply = filt.decide(record)
            if reply == FilterReply.ACCEPT:
                return FilterReply.ACCEPT
            if reply != FilterReply.DENY:
                all_deny = False
        return FilterReply.DENY if all_deny else FilterReply.NEUTRAL


class NotFilter(Filter):
    """Invert a single child filter (``ACCEPT`` <-> ``DENY``)."""

    def __init__(self, filter: Filter) -> None:
        self.filter = filter

    def decide(self, record: LogRecord) -> FilterReply:
        reply = self.filter.decide(record)
        if reply == FilterReply.ACCEPT:
            return FilterReply.DENY
        if reply == FilterReply.DENY:
            return FilterReply.ACCEPT
        return FilterReply.NEUTRAL


class CallableFilter(Filter):
    """Filter backed by a Python predicate (the log4j2 ``ScriptFilter`` analogue).

    *predicate* is called with the :class:`LogRecord` and its truthiness selects
    ``onMatch`` / ``onMismatch`` (defaults ``"accept"`` / ``"neutral"``).
    """

    def __init__(self, predicate, onMatch="accept", onMismatch="neutral") -> None:
        super().__init__(onMatch=onMatch, onMismatch=onMismatch)
        self.predicate = predicate

    def decide(self, record: LogRecord) -> FilterReply:
        return self._reply(bool(self.predicate(record)))

