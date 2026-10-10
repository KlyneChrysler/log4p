"""Layouts turn a :class:`~log4p.record.LogRecord` into text.

Provided layouts: :class:`SimpleLayout`, :class:`PatternLayout` (log4j pattern
syntax), and :class:`JSONLayout`.
"""

from __future__ import annotations

import json
import re
import socket
import time
from typing import Callable, Dict, List, Optional, Tuple

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


_ANSI_RESET = "\x1b[0m"

_ANSI_CODES: Dict[str, str] = {
    "normal": "0",
    "reset": "0",
    "bright": "1",
    "bold": "1",
    "dim": "2",
    "underline": "4",
    "blink": "5",
    "reverse": "7",
    "hidden": "8",
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "default": "39",
    "bright_black": "90",
    "bright_red": "91",
    "bright_green": "92",
    "bright_yellow": "93",
    "bright_blue": "94",
    "bright_magenta": "95",
    "bright_cyan": "96",
    "bright_white": "97",
    "bg_black": "40",
    "bg_red": "41",
    "bg_green": "42",
    "bg_yellow": "43",
    "bg_blue": "44",
    "bg_magenta": "45",
    "bg_cyan": "46",
    "bg_white": "47",
    "bg_default": "49",
}

_HIGHLIGHT_DEFAULT: Dict[str, str] = {
    "FATAL": "bright_red",
    "ERROR": "bright_red",
    "WARN": "yellow",
    "INFO": "green",
    "DEBUG": "cyan",
    "TRACE": "black",
}


def _ansi_style(spec: str) -> str:
    """Turn a comma-separated list of ANSI style names into an escape code."""
    codes = []
    for name in spec.replace(" ", "").split(","):
        if not name:
            continue
        code = _ANSI_CODES.get(name.lower())
        if code:
            codes.append(code)
    if not codes:
        return ""
    return "\x1b[" + ";".join(codes) + "m"


def _wrap_ansi(text: str, spec: str) -> str:
    code = _ansi_style(spec)
    if not code or not text:
        return text
    return code + text + _ANSI_RESET


def _parse_highlight_style(option: Optional[str]) -> Dict[str, str]:
    """Parse ``{ERROR=red, WARN=blue}`` into a level->color map."""
    override: Dict[str, str] = {}
    if not option:
        return override
    for pair in option.split(","):
        if "=" not in pair:
            continue
        level, _, color = pair.partition("=")
        override[level.strip().upper()] = color.strip()
    return override


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


def _logger_name(
    record: LogRecord,
    precision: Optional[int],
    full: bool,
    abbreviate: bool = False,
) -> str:
    name = record.name if full else record.name.split(".")[-1]
    if precision is not None:
        parts = name.split(".")
        if abbreviate:
            if len(parts) > precision:
                head = [part[:1] for part in parts[:-precision]]
                return ".".join(head + parts[-precision:])
            return name
        if precision > 0 and len(parts) > precision:
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
        %K{key}                   map/context value (or whole map)
        %x / %ndc                 NDC stack joined by spaces
        %h / %host                hostname
        %n                        platform newline
        %%                        literal percent

    Selectors and colour (log4j style)::

        %replace{p}{regex}{sub}      regex substitution over a sub-pattern
        %equals{p}{test}{sub}        literal replacement
        %equalsIgnoreCase{p}{test}{sub}
        %notEmpty{p}                 emit only when all variables are non-empty
        %style{p}{bold,red}          wrap in ANSI codes
        %highlight{p}{ERROR=red,...} colour by level
        %red{p} ... %green{p}        colour shorthand
        %maxLen{p}{N}                truncate (adds "..." when N > 20)
        %encode{p}{HTML|XML|JSON|CRLF}

    ``%c{1.}`` abbreviates ancestors to their first letter (e.g.
    ``o.a.c.Foo``). Format modifiers ``%[-][min][.max]`` are honoured, e.g.
    ``%-5p`` or ``%.30c``.
    """

    def __init__(self, pattern: str = "%m%n") -> None:
        self.pattern = pattern
        self._tokens: List[Callable[[LogRecord], str]] = _compile(pattern)

    def format(self, record: LogRecord) -> str:
        return "".join(token(record) for token in self._tokens)


_SELECTOR_NAMES = [
    "equalsIgnoreCase",
    "variablesNotEmpty",
    "varsNotEmpty",
    "notEmpty",
    "highlight",
    "maxLength",
    "maxLen",
    "replace",
    "equals",
    "encode",
    "style",
]

# Shorthand colour converters, e.g. ``%red{%m}``.
_COLOR_NAMES = [
    "default",
    "magenta",
    "yellow",
    "black",
    "green",
    "white",
    "blue",
    "cyan",
    "red",
]

_LONG_NAMES = _SELECTOR_NAMES + [
    "throwable",
    "exception",
    "message",
    "msg",
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


def _literal_token(text: str) -> Callable[[LogRecord], str]:
    def token(_record: LogRecord) -> str:
        return text

    token._log4p_literal = True  # type: ignore[attr-defined]
    return token


def _read_braced(pattern: str, start: int) -> Tuple[Optional[str], int]:
    """Read a ``{...}`` group starting at *start*, honouring nesting.

    Returns ``(content, index_after_close)``; ``(None, start)`` if unbalanced.
    Backslashes escape the following character so ``\\{`` and ``\\}`` are literal.
    """
    if start >= len(pattern) or pattern[start] != "{":
        return None, start
    depth = 0
    i = start
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\" and i + 1 < len(pattern):
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return pattern[start + 1 : i], i + 1
        i += 1
    return None, start


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
            tokens.append(_literal_token(text))

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
        for candidate in _COLOR_NAMES:
            end = j + len(candidate)
            if pattern.startswith(candidate, j) and end < len(pattern) and pattern[end] == "{":
                name = candidate
                j = end
                break
        if name is None:
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

        options: List[str] = []
        while j < len(pattern) and pattern[j] == "{":
            content, next_j = _read_braced(pattern, j)
            if content is None:
                break
            options.append(content)
            j = next_j

        flush()
        tokens.append(
            _make_converter(name, options, left, min_width, max_width, pattern[i:j])
        )
        i = j

    flush()
    return tokens


def _make_converter(
    name: str,
    options: List[str],
    left: bool,
    min_width: Optional[int],
    max_width: Optional[int],
    raw: str,
) -> Callable[[LogRecord], str]:
    def wrap(fn: Callable[[LogRecord], str]) -> Callable[[LogRecord], str]:
        def token(record: LogRecord) -> str:
            return _apply_width(fn(record), left, min_width, max_width)

        return token

    option = options[0] if options else None

    if name == "replace":
        if len(options) < 3:
            return wrap(lambda r: raw)
        sub = _compile(options[0])
        regex = re.compile(options[1])
        replacement = options[2]
        return wrap(lambda r: regex.sub(replacement, "".join(t(r) for t in sub)))

    if name in ("equals", "equalsIgnoreCase"):
        if len(options) < 3:
            return wrap(lambda r: raw)
        sub = _compile(options[0])
        test = options[1]
        replacement = options[2]
        if name == "equalsIgnoreCase":
            pattern = re.compile(re.escape(test), re.IGNORECASE)
            return wrap(
                lambda r: pattern.sub(lambda _m: replacement, "".join(t(r) for t in sub))
            )
        return wrap(lambda r: "".join(t(r) for t in sub).replace(test, replacement))

    if name in ("notEmpty", "variablesNotEmpty", "varsNotEmpty"):
        if not options:
            return wrap(lambda r: raw)
        sub = _compile(options[0])

        def not_empty(record: LogRecord) -> str:
            parts = []
            empty_variable = False
            for tok in sub:
                value = tok(record)
                if not getattr(tok, "_log4p_literal", False) and value == "":
                    empty_variable = True
                parts.append(value)
            return "" if empty_variable else "".join(parts)

        return wrap(not_empty)

    if name == "style":
        if len(options) < 2:
            return wrap(lambda r: raw)
        sub = _compile(options[0])
        spec = options[1]
        return wrap(lambda r: _wrap_ansi("".join(t(r) for t in sub), spec))

    if name == "highlight":
        if not options:
            return wrap(lambda r: raw)
        sub = _compile(options[0])
        override = _parse_highlight_style(options[1] if len(options) > 1 else None)

        def highlight(record: LogRecord) -> str:
            color = override.get(record.level.name) or _HIGHLIGHT_DEFAULT.get(
                record.level.name, ""
            )
            return _wrap_ansi("".join(t(record) for t in sub), color)

        return wrap(highlight)

    if name in ("maxLen", "maxLength"):
        if len(options) < 2:
            return wrap(lambda r: raw)
        sub = _compile(options[0])
        limit = int(options[1])

        def truncate(record: LogRecord) -> str:
            text = "".join(t(record) for t in sub)
            if len(text) <= limit:
                return text
            if limit > 20:
                return text[: limit - 3] + "..."
            return text[:limit]

        return wrap(truncate)

    if name == "encode":
        if len(options) < 2:
            return wrap(lambda r: raw)
        sub = _compile(options[0])
        kind = options[1].upper()

        def encode(record: LogRecord) -> str:
            text = "".join(t(record) for t in sub)
            if kind in ("HTML", "XML"):
                return _xml_escape(text)
            if kind == "JSON":
                return json.dumps(text)[1:-1]
            if kind == "CRLF":
                return text.replace("\r", "\\r").replace("\n", "\\n")
            return text

        return wrap(encode)

    if name in _COLOR_NAMES:
        if not options:
            return wrap(lambda r: raw)
        sub = _compile(options[0])
        color = name
        return wrap(lambda r: _wrap_ansi("".join(t(r) for t in sub), color))

    if name in ("c", "logger"):
        abbreviate = bool(option) and option.endswith(".")
        digits = option[:-1] if abbreviate else option
        if abbreviate:
            precision = int(digits) if digits.isdigit() else 1
        else:
            precision = int(digits) if digits and digits.isdigit() else None
        return wrap(lambda r: _logger_name(r, precision, full=True, abbreviate=abbreviate))
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
    if name == "K":
        if option:
            return wrap(lambda r: str(r.context.get(option, "")))
        return wrap(lambda r: json.dumps(r.context, default=str))

    return wrap(lambda r: raw)
