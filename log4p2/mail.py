"""``SMTPAppender``: buffer recent events and email them when one is severe.

Like log4j's ``SMTPAppender``: every event that reaches the appender is kept in
a fixed-size ring buffer; when an event at or above *triggerLevel* arrives, the
whole buffer (plus that event's stack trace) is emailed to the configured
recipients.
"""

from __future__ import annotations

import smtplib
from collections import deque
from email.message import EmailMessage
from typing import Deque, Iterable, List, Optional, Union

from .appender import Appender
from .layout import Layout, PatternLayout
from .levels import Level, getLevel
from .record import LogRecord


class SMTPAppender(Appender):
    """Email buffered events when one at or above *triggerLevel* is logged.

    *subject* may be a plain string or a PatternLayout pattern (anything
    containing ``%``), evaluated against the triggering record.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 25,
        fromaddr: str = "log4p@localhost",
        toaddrs: Optional[Iterable[str]] = None,
        subject: str = "%p %c - %m",
        bufferSize: int = 64,
        triggerLevel: Union[str, int, Level] = "ERROR",
        starttls: bool = False,
        ssl: bool = False,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
        layout: Optional[Layout] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        if bufferSize <= 0:
            raise ValueError("bufferSize must be positive")
        self.host = host
        self.port = port
        self.fromaddr = fromaddr
        self.toaddrs: List[str] = list(toaddrs) if toaddrs else []
        self.subject = subject
        self.triggerLevel = getLevel(triggerLevel)
        self.starttls = starttls
        self.ssl = ssl
        self.username = username
        self.password = password
        self.timeout = timeout
        self._buffer: Deque[LogRecord] = deque(maxlen=bufferSize)
        self._subject_layout = (
            PatternLayout(subject) if "%" in subject else None
        )

    def append(self, record: LogRecord) -> None:
        self._buffer.append(record)
        if int(record.level) >= int(self.triggerLevel):
            self._send(record)

    def _render_body(self) -> str:
        return "\n".join(self._render(record) for record in self._buffer)

    def _render_subject(self, record: LogRecord) -> str:
        if self._subject_layout is not None:
            return self._subject_layout.format(record)
        return self.subject

    def _send(self, record: LogRecord) -> None:
        message = EmailMessage()
        message["Subject"] = self._render_subject(record)
        message["From"] = self.fromaddr
        message["To"] = ", ".join(self.toaddrs)
        message.set_content(self._render_body())
        if self.ssl:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                self.host, self.port, timeout=self.timeout
            )
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        try:
            if self.starttls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password or "")
            server.send_message(message)
        finally:
            try:
                server.quit()
            except smtplib.SMTPException:  # pragma: no cover
                server.close()

    def flush(self) -> None:
        self._buffer.clear()
