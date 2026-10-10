"""Filters decide whether a record reaches an appender, using log4j's tri-state
``ACCEPT`` / ``DENY`` / ``NEUTRAL`` protocol."""

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


class Filter:
    """Base class. Return one of :class:`FilterReply` from :meth:`decide`."""

    def decide(self, record: LogRecord) -> FilterReply:  # pragma: no cover
        return FilterReply.NEUTRAL


class ThresholdFilter(Filter):
    """Deny records below *level*; let everything else pass through."""

    def __init__(self, level: Union[str, int, Level]) -> None:
        self.level = getLevel(level)

    def decide(self, record: LogRecord) -> FilterReply:
        if int(record.level) >= int(self.level):
            return FilterReply.NEUTRAL
        return FilterReply.DENY


class LevelRangeFilter(Filter):
    """Accept records whose level falls within ``[min_level, max_level]``."""

    def __init__(
        self,
        min_level: Union[str, int, Level] = "ALL",
        max_level: Union[str, int, Level] = "OFF",
    ) -> None:
        self.min_level = getLevel(min_level)
        self.max_level = getLevel(max_level)

    def decide(self, record: LogRecord) -> FilterReply:
        if int(self.min_level) <= int(record.level) <= int(self.max_level):
            return FilterReply.NEUTRAL
        return FilterReply.DENY


class RegexFilter(Filter):
    """Match a regex against a record field.

    *field* is one of the ``LogRecord`` attributes, most commonly ``message``
    (the default) or ``name``.  By default a match lets the record through and
    a miss denies it; set ``on_match='deny'`` to invert.
    """

    def __init__(self, pattern: str, field: str = "message", on_match: str = "accept") -> None:
        self.regex = re.compile(pattern)
        self.field = field
        if on_match not in ("accept", "deny"):
            raise ValueError("on_match must be 'accept' or 'deny'")
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
        matched = bool(self.regex.search(value))
        if matched == (self.on_match == "accept"):
            return FilterReply.NEUTRAL
        return FilterReply.DENY
