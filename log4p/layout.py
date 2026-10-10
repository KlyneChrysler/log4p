"""Layouts turn a :class:`~log4p.record.LogRecord` into text.

Provided layouts: :class:`SimpleLayout`, :class:`PatternLayout` (log4j pattern
syntax), and :class:`JSONLayout`.
"""

from __future__ import annotations

import json
import socket
import time
from typing import Callable, List, Optional

from .record import LogRecord

_HOSTNAME = socket.gethostname()

_TIME_PRESETS = {
    "DEFAULT": "%Y-%m-%d %H:%M:%S",
    "ISO8601": "%Y-%m-%d %H:%M:%S",
    "ISO8601_DAYS": "%Y-%m-%d %H:%M:%S",
    "ABS": "%H:%M:%S",
    "ABSOLUTE": "%H:%M:%S",
    "DATE": "%d %b %Y %H:%M:%S",
    "COMPACT": "%Y%m%d%H%M%S",
}

# Java date-pattern tokens, longest first so "SSS" wins over "S".
_JAVA_TIME_TOKENS = [
    ("yyyy", "%Y"),
    ("yyy", "%Y"),
    ("yy", "%y"),
    ("SSS", "\x01A\x01"),
    ("SS", "\x01B\x01"),
    ("S", "\x01C\x01"),
    ("MMM", "%b"),
    ("MM", "%m"),
    ("dd", "%d"),
    ("HH", "%H"),
    ("hh", "%I"),
    ("mm", "%M"),
    ("ss", "%S"),
    ("a", "%p"),
    ("Z", "%z"),
    ("EEE", "%a"),
]


def _java_to_strftime(fmt: str) -> str:
    for token, replacement in _JAVA_TIME_TOKENS:
        fmt = fmt.replace(token, replacement)
    return fmt


def _strftime_with_millis(created: float, fmt: str) -> str:
    text = time.strftime(fmt, time.localtime(created))
    millis = int((created - int(created)) * 1000)
    text = text.replace("\x01A\x01", f"{millis:03d}")
    text = text.replace("\x01B\x01", f"{millis // 10:02d}")
    text = text.replace("\x01C\x01", str(millis // 100))
    return text


def format_timestamp(created: float, fmt: Optional[str] = None) -> str:
    """Format *created* using a preset name, a Java pattern, or strftime."""
    if not fmt:
        fmt = "DEFAULT"
    preset = _TIME_PRESETS.get(fmt.upper())
    if preset is not None:
        fmt = preset
    if "%" in fmt:
        return _strftime_with_millis(created, fmt)
    return _strftime_with_millis(created, _java_to_strftime(fmt))


class Layout:
    """Base class for layouts."""

    ignoresExceptions: bool = False

    def format(self, record: LogRecord) -> Optional[str]:
        raise NotImplementedError

    def header(self) -> Optional[str]:
        return None

    def footer(self) -> Optional[str]:
        return None


class SimpleLayout(Layout):
    """``LEVEL - message``."""

    def format(self, record: LogRecord) -> str:
        return f"{record.level.name} - {record.getMessage()}"


class JSONLayout(Layout):
    """Render each record as a single-line JSON object."""

    ignoresExceptions = True

    def __init__(self, ensure_ascii: bool = False, sort_keys: bool = False) -> None:
        self.ensure_ascii = ensure_ascii
        self.sort_keys = sort_keys

    def format(self, record: LogRecord) -> str:
        return json.dumps(
            record.toDict(),
            ensure_ascii=self.ensure_ascii,
            sort_keys=self.sort_keys,
            default=str,
        )


def _logger_name(record: LogRecord, precision: Optional[int], full: bool) -> str:
    name = record.name if full else record.name.split(".")[-1]
    if precision is not None and precision > 0:
        parts = name.split(".")
        if len(parts) > precision:
            return ".".join(parts[-precision:])
    return name


class PatternLayout(Layout):
    """log4j-style pattern layout.

    Supported conversions::

        %c{precision} / %logger   logger name (optionally rightmost segments)
        %d{format}   / %date      timestamp (preset, Java pattern, or strftime)
        %m / %msg / %message      formatted message
        %p / %level               level name
        %t / %thread              thread name
        %r / %relative            milliseconds since start
        %F / %file                source filename
        %L / %line                source line number
        %M / %method              source function name
        %C / %class               source module name
        %X{key} / %mdc{key}       MDC value (or whole map when no key)
        %x / %ndc                 NDC stack joined by spaces
        %h / %host                hostname
        %n                        platform newline
        %%                        literal percent

    Format modifiers ``%[-][min][.max]`` are honoured, e.g. ``%-5p`` or
    ``%.30c``.
    """

    def __init__(self, pattern: str = "%m%n") -> None:
        self.pattern = pattern
        self._tokens: List[Callable[[LogRecord], str]] = _compile(pattern)

    def format(self, record: LogRecord) -> str:
        return "".join(token(record) for token in self._tokens)


_LONG_NAMES = [
    "message",
    "logger",
    "level",
    "thread",
    "relative",
    "date",
    "file",
    "line",
    "method",
    "class",
    "mdc",
    "ndc",
    "host",
]


def _apply_width(text: str, left: bool, min_width: Optional[int], max_width: Optional[int]) -> str:
    if max_width is not None and len(text) > max_width:
        text = text[len(text) - max_width :]
    if min_width is not None and len(text) < min_width:
        text = text.ljust(min_width) if left else text.rjust(min_width)
    return text


def _compile(pattern: str) -> List[Callable[[LogRecord], str]]:
    tokens: List[Callable[[LogRecord], str]] = []
    i = 0
    literal: List[str] = []

    def flush() -> None:
        if literal:
            text = "".join(literal)
            literal.clear()
            tokens.append(lambda _r, _t=text: _t)

    while i < len(pattern):
        ch = pattern[i]
        if ch != "%":
            literal.append(ch)
            i += 1
            continue

        if i + 1 < len(pattern) and pattern[i + 1] == "%":
            literal.append("%")
            i += 2
            continue

        j = i + 1
        left = False
        if j < len(pattern) and pattern[j] == "-":
            left = True
            j += 1
        min_start = j
        while j < len(pattern) and pattern[j].isdigit():
            j += 1
        min_width = int(pattern[min_start:j]) if j > min_start else None
        max_width = None
        if j < len(pattern) and pattern[j] == ".":
            j += 1
            max_start = j
            while j < len(pattern) and pattern[j].isdigit():
                j += 1
            if j > max_start:
                max_width = int(pattern[max_start:j])

        name = None
        for candidate in _LONG_NAMES:
            if pattern.startswith(candidate, j):
                name = candidate
                j += len(candidate)
                break
        if name is None:
            if j < len(pattern):
                name = pattern[j]
                j += 1
            else:
                literal.append("%")
                i += 1
                continue

        option = None
        if j < len(pattern) and pattern[j] == "{":
            end = pattern.find("}", j)
            if end != -1:
                option = pattern[j + 1 : end]
                j = end + 1

        flush()
        tokens.append(
            _make_converter(name, option, left, min_width, max_width, pattern[i:j])
        )
        i = j

    flush()
    return tokens


def _make_converter(
    name: str,
    option: Optional[str],
    left: bool,
    min_width: Optional[int],
    max_width: Optional[int],
    raw: str,
) -> Callable[[LogRecord], str]:
    def wrap(fn: Callable[[LogRecord], str]) -> Callable[[LogRecord], str]:
        def token(record: LogRecord) -> str:
            return _apply_width(fn(record), left, min_width, max_width)

        return token

    if name in ("c", "logger"):
        precision = int(option) if option and option.isdigit() else None
        return wrap(lambda r: _logger_name(r, precision, full=True))
    if name in ("d", "date"):
        fmt = option
        return wrap(lambda r: format_timestamp(r.created, fmt))
    if name in ("m", "msg", "message"):
        return wrap(lambda r: r.getMessage())
    if name in ("p", "level"):
        return wrap(lambda r: r.level.name)
    if name in ("t", "thread"):
        return wrap(lambda r: r.threadName)
    if name in ("r", "relative"):
        return wrap(lambda r: str(int(r.relativeCreated)))
    if name in ("F", "file"):
        return wrap(lambda r: r.filename)
    if name in ("L", "line"):
        return wrap(lambda r: str(r.lineno))
    if name in ("M", "method"):
        return wrap(lambda r: r.funcName)
    if name in ("C", "class"):
        return wrap(lambda r: r.module)
    if name in ("x", "ndc"):
        return wrap(lambda r: r.ndc)
    if name in ("h", "host"):
        return wrap(lambda r: _HOSTNAME)
    if name in ("n",):
        return wrap(lambda r: "\n")
    if name in ("X", "mdc"):
        if option:
            return wrap(lambda r: str(r.context.get(option, "")))
        return wrap(lambda r: json.dumps(r.context, default=str))

    literal = raw
    return wrap(lambda r: literal)
