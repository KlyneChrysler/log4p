"""The :class:`LogRecord` - the unit of data flowing from loggers to appenders."""

from __future__ import annotations

import os
import threading
import time
import traceback
from typing import Any, Dict, Mapping, Optional

from .levels import Level


class LogRecord:
    """A single logging event.

    Instances are created by :class:`~log4p.logger.Logger` and passed to every
    appender in the logger hierarchy.  The shape deliberately mirrors log4j's
    ``LoggingEvent`` (and Python's ``logging.LogRecord``) so layouts have a
    stable contract to read from.
    """

    __slots__ = (
        "name",
        "level",
        "message",
        "args",
        "exc_info",
        "exc_text",
        "pathname",
        "filename",
        "module",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "process",
        "processName",
        "context",
        "ndc",
        "_formatted",
    )

    def __init__(
        self,
        name: str,
        level: Level,
        message: str,
        args: Any = None,
        exc_info: Any = None,
        pathname: str = "",
        lineno: int = 0,
        funcName: str = "",
        context: Optional[Mapping[str, Any]] = None,
        ndc: str = "",
    ) -> None:
        self.name = name
        self.level = level
        self.message = message
        self.args = args
        self.exc_info = exc_info
        self.exc_text: Optional[str] = None
        self.pathname = pathname or ""
        self.filename = os.path.basename(self.pathname) if pathname else ""
        base = self.filename
        if base.endswith(".py"):
            base = base[:-3]
        self.module = base
        self.lineno = lineno or 0
        self.funcName = funcName or ""
        self.created = time.time()
        self.msecs = (self.created - int(self.created)) * 1000.0
        self.relativeCreated = (self.created - _START_TIME) * 1000.0
        current = threading.current_thread()
        self.thread = current.ident if current.ident is not None else 0
        self.threadName = current.name
        self.process = os.getpid()
        self.processName = "MainProcess"
        self.context: Dict[str, Any] = dict(context) if context else {}
        self.ndc = ndc
        self._formatted: Optional[str] = None

    def getMessage(self) -> str:
        """Merge the message template with its arguments (``%`` style)."""
        if self._formatted is None:
            msg = str(self.message)
            if self.args:
                try:
                    msg = msg % self.args
                except Exception:  # pragma: no cover - defensive
                    msg = f"{msg} {self.args}"
            self._formatted = msg
        return self._formatted

    def getExceptionText(self) -> Optional[str]:
        """Return formatted traceback text, caching the result."""
        if self.exc_info:
            if self.exc_text is None:
                self.exc_text = "".join(traceback.format_exception(*self.exc_info))
            return self.exc_text
        return None

    def toDict(self) -> Dict[str, Any]:
        """A JSON-serialisable view used by :class:`~log4p.layout.JSONLayout`."""
        data: Dict[str, Any] = {
            "time": self.created,
            "level": self.level.name,
            "logger": self.name,
            "message": self.getMessage(),
            "thread": self.threadName,
            "process": self.processName,
            "module": self.module,
            "func": self.funcName,
            "line": self.lineno,
        }
        if self.context:
            data["context"] = self.context
        if self.ndc:
            data["ndc"] = self.ndc
        exc = self.getExceptionText()
        if exc:
            data["exception"] = exc
        return data

    def __repr__(self) -> str:
        return (
            f"<LogRecord {self.level.name} {self.name!r} "
            f"{self.getMessage()!r} at {self.filename}:{self.lineno}>"
        )


_START_TIME = time.time()


def resetStartTime() -> float:
    """Reset the reference point used for ``%r``/relative timestamps."""
    global _START_TIME
    _START_TIME = time.time()
    return _START_TIME
