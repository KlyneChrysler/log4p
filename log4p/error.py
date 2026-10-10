"""Error handlers for appenders, in the spirit of log4j's ``ErrorHandler``.

An appender that raises while appending asks its error handler what to do. The
default (:class:`ErrorHandler`) reports to ``stderr``. A
:class:`FallbackErrorHandler` can additionally swap a failing primary appender
for one or more backups so logging keeps working when the primary target dies
(disk full, socket closed, permissions revoked).
"""

from __future__ import annotations

import sys
import traceback
from typing import List, Optional

from .record import LogRecord


class ErrorHandler:
    """Default handler: write the failure and traceback to ``stderr``."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def handle(self, record: Optional[LogRecord], exc_info) -> None:
        if self.enabled:
            self.emit(record, exc_info)

    def emit(self, record: Optional[LogRecord], exc_info) -> None:
        where = record.name if record is not None else "?"
        sys.stderr.write(f"log4p: error appending record for logger {where!r}\n")
        if exc_info is not None and exc_info[0] is not None:
            traceback.print_exception(*exc_info, file=sys.stderr)
        else:
            sys.stderr.write("log4p: (no exception info available)\n")


class FallbackErrorHandler(ErrorHandler):
    """On failure of the primary appender, activate backup appenders.

    The primary is detached from every logger it was attached to and the
    backups are attached in its place, so subsequent records go to the
    fallback destination.
    """

    def __init__(self, enabled: bool = True) -> None:
        super().__init__(enabled)
        self._primary = None
        self._backups: List = []
        self._activated = False

    def setAppender(self, appender) -> None:
        self._primary = appender

    def setBackupAppender(self, appender) -> None:
        self._backups.append(appender)

    def getBackups(self) -> List:
        return list(self._backups)

    def isActivated(self) -> bool:
        return self._activated

    def handle(self, record: Optional[LogRecord], exc_info) -> None:
        super().handle(record, exc_info)
        if self._activated or self._primary is None or not self._backups:
            return
        self._activated = True

        from .logger import getLoggerManager

        manager = getLoggerManager()
        for logger in manager.allLoggers():
            if self._primary in logger.getAppenders():
                logger.removeAppender(self._primary)
                for backup in self._backups:
                    logger.addAppender(backup)
        sys.stderr.write(
            "log4p: FallbackErrorHandler activated backups for appender %r\n"
            % getattr(self._primary, "getName", lambda: "?")()
        )
