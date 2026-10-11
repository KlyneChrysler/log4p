"""Syslog layouts: RFC 3164 (:class:`SyslogLayout`) and RFC 5424
(:class:`RFC5424Layout`).

Both render a complete syslog line (including the ``<PRI>`` header) from a
record, so they can be attached to any appender (a file, a socket, or
:class:`~log4p.net.SyslogAppender`) and the correct framing is produced. The
message body is rendered by a nested pattern (default ``%m``).
"""

from __future__ import annotations

import socket
import time
from typing import Optional

from .layout import Layout, PatternLayout
from .levels import Level
from .message import StructuredDataMessage
from .record import LogRecord

SYSLOG_FACILITY = {
    "KERN": 0,
    "USER": 1,
    "MAIL": 2,
    "DAEMON": 3,
    "AUTH": 4,
    "SYSLOG": 5,
    "LPR": 6,
    "NEWS": 7,
    "UUCP": 8,
    "CRON": 9,
    "AUTHPRIV": 10,
    "FTP": 11,
    "LOCAL0": 16,
    "LOCAL1": 17,
    "LOCAL2": 18,
    "LOCAL3": 19,
    "LOCAL4": 20,
    "LOCAL5": 21,
    "LOCAL6": 22,
    "LOCAL7": 23,
}

SYSLOG_SEVERITY = {
    "FATAL": 2,
    "CRITICAL": 2,
    "ERROR": 3,
    "WARN": 4,
    "WARNING": 4,
    "INFO": 6,
    "DEBUG": 7,
    "TRACE": 7,
}

_HOSTNAME = socket.gethostname()


def facility_index(facility: str) -> int:
    """Return the numeric syslog facility, raising ``ValueError`` if unknown."""
    name = str(facility).upper()
    try:
        return SYSLOG_FACILITY[name]
    except KeyError:
        raise ValueError(f"unknown syslog facility: {facility!r}") from None


def severity_for(record: LogRecord) -> int:
    """Map a record's level to a syslog severity (0-7)."""
    name = record.level.name.upper()
    if name in SYSLOG_SEVERITY:
        return SYSLOG_SEVERITY[name]
    return 7 if int(record.level) <= int(Level.DEBUG) else 3


def _with_exception(record: LogRecord, body: str) -> str:
    if not record.exc_info:
        return body
    exc = record.getExceptionText()
    if not exc:
        return body
    if body and not body.endswith("\n"):
        body += "\n"
    return body + exc


def _rfc5424_offset(created: float) -> str:
    offset = time.strftime("%z", time.localtime(created))
    if not offset:  # pragma: no cover - platforms without %z
        return "Z"
    return offset[:3] + ":" + offset[3:]


class SyslogLayout(Layout):
    """RFC 3164 (BSD) syslog framing: ``<PRI>Mmm dd HH:MM:SS host tag: msg``."""

    ignoresExceptions = True

    def __init__(
        self,
        facility: str = "USER",
        hostname: Optional[str] = None,
        tag: Optional[str] = None,
        pattern: str = "%m",
    ) -> None:
        self.facility = facility.upper()
        self.facility_index = facility_index(facility)
        self.hostname = hostname
        self.tag = tag
        self.pattern = pattern
        self._body = PatternLayout(pattern)

    def format(self, record: LogRecord) -> str:
        body = _with_exception(record, self._body.format(record).rstrip("\n"))
        return self.formatLine(record, body)

    def formatLine(self, record: LogRecord, body: str) -> str:
        """Frame a pre-rendered *body* (used when wrapping another layout)."""
        pri = self.facility_index * 8 + severity_for(record)
        when = time.strftime("%b %d %H:%M:%S", time.localtime(record.created))
        host = self.hostname or _HOSTNAME
        tag = self.tag or record.name or "log4p"
        return f"<{pri}>{when} {host} {tag}: {body}"


class RFC5424Layout(Layout):
    """RFC 5424 framing: ``<PRI>1 TIMESTAMP HOST APP PROCID MSGID SD MSG``.

    Structured data is taken from a :class:`StructuredDataMessage`; other events
    emit the ``-`` nil value.
    """

    ignoresExceptions = True

    def __init__(
        self,
        facility: str = "USER",
        hostname: Optional[str] = None,
        appName: Optional[str] = None,
        procId: Optional[str] = None,
        msgId: Optional[str] = None,
        pattern: str = "%m",
    ) -> None:
        self.facility = facility.upper()
        self.facility_index = facility_index(facility)
        self.hostname = hostname
        self.appName = appName
        self.procId = procId
        self.msgId = msgId
        self.pattern = pattern
        self._body = PatternLayout(pattern)

    def _structured_data(self, record: LogRecord) -> str:
        message = record.message
        if isinstance(message, StructuredDataMessage):
            return message.getFormattedMessage()
        return "-"

    def format(self, record: LogRecord) -> str:
        body = _with_exception(record, self._body.format(record).rstrip("\n"))
        return self.formatLine(record, body)

    def formatLine(self, record: LogRecord, body: str) -> str:
        """Frame a pre-rendered *body* (used when wrapping another layout)."""
        pri = self.facility_index * 8 + severity_for(record)
        when = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created))
        timestamp = f"{when}.{int(record.msecs):03d}{_rfc5424_offset(record.created)}"
        host = self.hostname or _HOSTNAME
        app = self.appName or record.name or "log4p"
        proc = self.procId if self.procId is not None else str(record.process)
        msgid = self.msgId or "-"
        sd = self._structured_data(record)
        return f"<{pri}>1 {timestamp} {host} {app} {proc} {msgid} {sd} {body}"
