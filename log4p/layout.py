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


def _logfmt_value(value: object) -> str:
    text = str(value)
    if text == "" or any(ch in text for ch in ' =\t\n"'):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


class LogfmtLayout(Layout):
    """Emit ``key=value`` pairs (logfmt), one line per record.

    Top-level fields come first, then MDC context entries.
    """

    ignoresExceptions = True

    def __init__(self, timestamp: bool = True) -> None:
        self.timestamp = timestamp

    def format(self, record: LogRecord) -> str:
        pairs = []
        if self.timestamp:
            pairs.append(("time", time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created))))
        pairs.append(("level", record.level.name.lower()))
        pairs.append(("logger", record.name))
        pairs.append(("msg", record.getMessage()))
        if record.marker is not None:
            pairs.append(("marker", str(record.marker)))
        if record.ndc:
            pairs.append(("ndc", record.ndc))
        for key, value in record.context.items():
            pairs.append((key, value))
        if record.exc_info:
            pairs.append(("exception", (record.getExceptionText() or "").strip()))
        return " ".join(f"{key}={_logfmt_value(value)}" for key, value in pairs)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class XMLLayout(Layout):
    """Wrap each record in an ``<event>`` element (one per line)."""

    ignoresExceptions = True

    def format(self, record: LogRecord) -> str:
        attrs = [
            f'logger="{_xml_escape(record.name)}"',
            f'level="{record.level.name}"',
            f'thread="{_xml_escape(record.threadName)}"',
            f"timestamp=\"{int(record.created * 1000)}\"",
        ]
        if record.marker is not None:
            attrs.append(f'marker="{_xml_escape(str(record.marker))}"')
        body = _xml_escape(record.getMessage())
        parts = [f"<event {' '.join(attrs)}>", f"<message>{body}</message>"]
        for key, value in record.context.items():
            parts.append(f'<data name="{_xml_escape(str(key))}">{_xml_escape(str(value))}</data>')
        exc = record.getExceptionText()
        if exc:
            parts.append(f"<exception>{_xml_escape(exc)}</exception>")
        parts.append("</event>")
        return "".join(parts)


class HTMLLayout(Layout):
    """Render a full HTML table, using :meth:`header` and :meth:`footer`."""

    ignoresExceptions = True

    def __init__(self, title: str = "log4p log") -> None:
        self.title = title

    def header(self) -> str:
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{_xml_escape(self.title)}</title>"
            "<style>body{font-family:monospace}td{padding:2px 6px;vertical-align:top}"
            ".ERROR,.FATAL{color:#b00}.WARN{color:#b60}.DEBUG,.TRACE{color:#888}"
            "</style></head><body><table><thead><tr>"
            "<th>Time</th><th>Level</th><th>Logger</th><th>Thread</th><th>Message</th>"
            "</tr></thead><tbody>\n"
        )

    def footer(self) -> str:
        return "</tbody></table></body></html>\n"

    def format(self, record: LogRecord) -> str:
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created))
        message = record.getMessage()
        exc = record.getExceptionText()
        if exc:
            message = message + "\n" + exc
        cells = (
            f"<td>{when}.{int(record.msecs):03d}</td>",
            f"<td class='{record.level.name}'>{record.level.name}</td>",
            f"<td>{_xml_escape(record.name)}</td>",
            f"<td>{_xml_escape(record.threadName)}</td>",
            f"<td>{_xml_escape(message)}</td>",
        )
        return "<tr>" + "".join(cells) + "</tr>\n"


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
    "throwable",
    "exception",
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
    "marker",
    "stack",
    "host",
    "pid",
    "tid",
    "ex",
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
    if name in ("T", "tid"):
        return wrap(lambda r: str(r.thread))
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
    if name in ("pid",):
        return wrap(lambda r: str(r.process))
    if name in ("n",):
        return wrap(lambda r: "\n")
    if name in ("marker",):
        return wrap(lambda r: str(r.marker) if r.marker is not None else "")
    if name in ("stack",):
        return wrap(lambda r: r.stack_info or "")
    if name in ("throwable", "exception", "ex"):
        return wrap(lambda r: r.getExceptionText() or "")
    if name in ("X", "mdc"):
        if option:
            return wrap(lambda r: str(r.context.get(option, "")))
        return wrap(lambda r: json.dumps(r.context, default=str))

    literal = raw
    return wrap(lambda r: literal)
