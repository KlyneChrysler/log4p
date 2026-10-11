"""Network appenders: raw TCP socket, syslog (RFC 3164/5424), and HTTP.

The socket and syslog appenders reconnect lazily: a failed write closes the
socket and marks it dead, and the next event tries to reconnect. Connection
attempts are throttled by *reconnectDelay* seconds so a dead peer does not turn
every log call into a blocking connect attempt.
"""

from __future__ import annotations

import socket
import ssl
import time
import urllib.parse
import urllib.request
from typing import Dict, Optional, Union

from .appender import Appender
from .layout import JSONLayout, Layout, PatternLayout
from .levels import Level
from .record import LogRecord

_SYSLOG_FACILITY = {
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

_SYSLOG_SEVERITY = {
    "FATAL": 2,
    "CRITICAL": 2,
    "ERROR": 3,
    "WARN": 4,
    "WARNING": 4,
    "INFO": 6,
    "DEBUG": 7,
    "TRACE": 7,
}


class SocketAppender(Appender):
    """Send each rendered event over a TCP connection.

    The payload is whatever the layout produces (a newline is appended when
    missing). If the peer is unreachable the write raises, the socket is
    dropped, and reconnection is retried at most once every *reconnectDelay*
    seconds.
    """

    def __init__(
        self,
        host: str,
        port: int,
        layout: Optional[Layout] = None,
        reconnectDelay: float = 30.0,
        timeout: float = 5.0,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        self.host = host
        self.port = port
        self.reconnectDelay = reconnectDelay
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None
        self._last_attempt = 0.0

    def _connect(self) -> None:
        now = time.time()
        if self._last_attempt and now - self._last_attempt < self.reconnectDelay:
            raise ConnectionError(f"reconnect throttled for {self.host}:{self.port}")
        self._last_attempt = now
        self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout)

    def start(self) -> None:
        with self._lock:
            if self._socket is None:
                try:
                    self._connect()
                except OSError:
                    self._socket = None
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.close()
                except OSError:  # pragma: no cover
                    pass
                self._socket = None
            self._started = False

    def flush(self) -> None:
        pass

    def append(self, record: LogRecord) -> None:
        text = self._render(record)
        if not text.endswith("\n"):
            text += "\n"
        data = text.encode("utf-8")
        if self._socket is None:
            self._connect()
        try:
            assert self._socket is not None
            self._socket.sendall(data)
        except OSError:
            try:
                self._socket.close()
            except OSError:  # pragma: no cover
                pass
            self._socket = None
            raise


class HttpAppender(Appender):
    """POST (or GET) each rendered event to an HTTP endpoint.

    The layout defaults to :class:`~log4p.layout.JSONLayout`, so the body is a
    JSON object. *headers* adds request headers; ``verifyHostname=False`` skips
    TLS certificate verification.
    """

    def __init__(
        self,
        url: str,
        method: str = "POST",
        layout: Optional[Layout] = None,
        headers: Optional[Dict[str, str]] = None,
        connectTimeout: float = 5.0,
        readTimeout: float = 5.0,
        verifyHostname: bool = True,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        if layout is None:
            layout = JSONLayout()
        super().__init__(name=name, layout=layout, threshold=threshold)
        method = method.upper()
        if method not in ("POST", "GET"):
            raise ValueError("method must be 'POST' or 'GET'")
        self.url = url
        self.method = method
        self.headers: Dict[str, str] = dict(headers) if headers else {}
        self.connectTimeout = connectTimeout
        self.readTimeout = readTimeout
        self.verifyHostname = verifyHostname

    def _build_request(self, body: str) -> urllib.request.Request:
        if self.method == "GET":
            sep = "&" if "?" in self.url else "?"
            url = f"{self.url}{sep}{urllib.parse.urlencode({'msg': body})}"
            return urllib.request.Request(url, headers=self.headers, method="GET")
        data = body.encode("utf-8")
        headers = {"Content-Type": "application/json", **self.headers}
        return urllib.request.Request(
            self.url, data=data, headers=headers, method="POST"
        )

    def append(self, record: LogRecord) -> None:
        request = self._build_request(self._render(record))
        context = None
        if not self.verifyHostname:
            context = ssl._create_unverified_context()  # noqa: S323
        with urllib.request.urlopen(  # noqa: S310 - user-supplied URL
            request, timeout=self.readTimeout, context=context
        ) as response:
            response.read()


class SyslogAppender(Appender):
    """Emit syslog messages (UDP by default, or TCP).

    By default the RFC 3164 layout is used. Pass ``rfc5424=True`` for the modern
    RFC 5424 framing (``<PRI>1 TIMESTAMP HOST APP PROCID MSGID SD MSG``), which
    can carry an app name, process id, and message id.

    *facility* is a syslog facility name (`USER`, `DAEMON`, `LOCAL0`, ...); the
    severity is derived from the record level. The layout (default ``%m``)
    supplies the message body.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 514,
        facility: str = "USER",
        socktype: str = "UDP",
        layout: Optional[Layout] = None,
        timeout: float = 5.0,
        rfc5424: bool = False,
        appName: Optional[str] = None,
        procId: Optional[str] = None,
        msgId: Optional[str] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        if layout is None:
            layout = PatternLayout("%m")
        super().__init__(name=name, layout=layout, threshold=threshold)
        facility = facility.upper()
        if facility not in _SYSLOG_FACILITY:
            raise ValueError(f"unknown syslog facility: {facility!r}")
        socktype = socktype.upper()
        if socktype not in ("UDP", "TCP"):
            raise ValueError("socktype must be 'UDP' or 'TCP'")
        self.host = host
        self.port = port
        self.facility = facility
        self.socktype = socktype
        self.timeout = timeout
        self.rfc5424 = rfc5424
        self.appName = appName
        self.procId = procId
        self.msgId = msgId
        self._socket: Optional[socket.socket] = None

    def start(self) -> None:
        with self._lock:
            self._ensure_socket()
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.close()
                except OSError:  # pragma: no cover
                    pass
                self._socket = None
            self._started = False

    def flush(self) -> None:
        pass

    def _ensure_socket(self) -> None:
        if self._socket is not None:
            return
        if self.socktype == "UDP":
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout)

    def _severity(self, record: LogRecord) -> int:
        name = record.level.name.upper()
        if name in _SYSLOG_SEVERITY:
            return _SYSLOG_SEVERITY[name]
        return 7 if int(record.level) <= int(Level.DEBUG) else 3

    def _format_line(self, record: LogRecord) -> str:
        pri = _SYSLOG_FACILITY[self.facility] * 8 + self._severity(record)
        message = self._render(record).rstrip("\n")
        if self.rfc5424:
            return self._format_rfc5424(pri, record, message)
        when = time.strftime("%b %d %H:%M:%S", time.localtime(record.created))
        tag = record.name or "log4p"
        return f"<{pri}>{when} {socket.gethostname()} {tag}: {message}"

    def _format_rfc5424(self, pri: int, record: LogRecord, message: str) -> str:
        when = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created))
        millis = int(record.msecs)
        offset = time.strftime("%z", time.localtime(record.created))
        if offset:
            offset = offset[:3] + ":" + offset[3:]
        else:  # pragma: no cover - platforms without %z
            offset = "Z"
        timestamp = f"{when}.{millis:03d}{offset}"
        host = socket.gethostname()
        app = self.appName or record.name or "log4p"
        proc = self.procId if self.procId is not None else str(record.process)
        msgid = self.msgId or "-"
        return f"<{pri}>1 {timestamp} {host} {app} {proc} {msgid} - {message}"

    def append(self, record: LogRecord) -> None:
        line = self._format_line(record)
        data = line.encode("utf-8")
        if self._socket is None:
            self._ensure_socket()
        try:
            assert self._socket is not None
            if self.socktype == "UDP":
                self._socket.sendto(data, (self.host, self.port))
            else:
                self._socket.sendall(data + b"\n")
        except OSError:
            try:
                self._socket.close()
            except OSError:  # pragma: no cover
                pass
            self._socket = None
            raise
