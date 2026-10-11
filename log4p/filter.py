"""Filters decide whether a record reaches an appender, using log4j's tri-state
``ACCEPT`` / ``DENY`` / ``NEUTRAL`` protocol.

Filters that test a condition accept ``onMatch`` / ``onMismatch`` (each one of
``"accept"``, ``"deny"``, ``"neutral"``) so they compose cleanly with
``AndFilter`` / ``OrFilter`` / ``NotFilter``.
"""

from __future__ import annotations

import re
from enum import IntEnum
from typing import Union

from .levels import Level, getLevel
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
