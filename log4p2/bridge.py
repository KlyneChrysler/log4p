"""Interoperate with the standard library's :mod:`logging`.

* :class:`StdlibToLog4pHandler` is a stdlib ``logging.Handler`` that forwards
  records into a log4p2 :class:`~log4p2.logger.Logger`, preserving level, caller
  info, and exception details.
* :class:`StdlibLoggingAppender` is a log4p appender that forwards records into
  the stdlib ``logging`` system.
* :func:`capture_stdlib` installs the inbound handler on the stdlib root logger
  in one call.

This lets a codebase (or its dependencies) keep using ``logging.getLogger(...)``
while everything ultimately lands in log4p's appenders.
"""

from __future__ import annotations

import logging
from typing import Optional, Union

from .appender import Appender
from .context import MDC, NDC
from .layout import Layout
from .levels import (
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    TRACE,
    WARN,
    Level,
    getLevel,
)
from .logger import Logger, getLogger
from .record import LogRecord

# Attribute names stdlib sets on every record; everything else is treated as
# user-supplied "extra" data.
_STDLIB_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime", "taskName"}

_LOG4P_TO_STDLIB = {
    "TRACE": logging.DEBUG,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "FATAL": logging.CRITICAL,
}


def _to_log4p_level(levelno: int) -> Level:
    if levelno >= logging.CRITICAL:
        return FATAL
    if levelno >= logging.ERROR:
        return ERROR
    if levelno >= logging.WARNING:
        return WARN
    if levelno >= logging.INFO:
        return INFO
    if levelno >= logging.DEBUG:
        return DEBUG
    return TRACE


def _to_stdlib_level(level: Union[str, int, Level]) -> int:
    lvl = getLevel(level)
    return _LOG4P_TO_STDLIB.get(lvl.name, logging.INFO)


class StdlibToLog4pHandler(logging.Handler):
    """A stdlib logging handler that routes records into a log4p logger."""

    def __init__(self, logger: Union[str, Logger, None] = None, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self._target: Logger = (
            logger if isinstance(logger, Logger) else getLogger(logger if logger else "")
        )

    @property
    def target(self) -> Logger:
        return self._target

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _to_log4p_level(record.levelno)
            if not self._target.isEnabledFor(level):
                return
            context = MDC.getCopy()
            for key, value in record.__dict__.items():
                if key not in _STDLIB_ATTRS and not key.startswith("_"):
                    context.setdefault(key, value)
            event = LogRecord(
                name=self._target.name,
                level=level,
                message=record.getMessage(),
                args=None,
                exc_info=record.exc_info,
                pathname=record.pathname,
                lineno=record.lineno,
                funcName=record.funcName,
                context=context,
                ndc=NDC.get(),
            )
            if self._target.getFilters() and not self._target._passes_filters(event):
                return
            self._target._callHandlers(event)
        except Exception:  # pragma: no cover - never let logging crash the app
            self.handleError(record)


class StdlibLoggingAppender(Appender):
    """A log4p appender that forwards records into stdlib ``logging``."""

    def __init__(
        self,
        logger: Union[str, logging.Logger, None] = None,
        layout: Optional[Layout] = None,
        threshold=None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        if isinstance(logger, logging.Logger) or (logger is not None and hasattr(logger, "log")):
            self._target = logger
        else:
            self._target = logging.getLogger(logger)

    def append(self, record: LogRecord) -> None:
        std_level = _to_stdlib_level(record.level)
        extra = {
            key: value
            for key, value in record.context.items()
            if key not in _STDLIB_ATTRS and not key.startswith("_")
        }
        self._target.log(
            std_level,
            record.getMessage(),
            exc_info=record.exc_info,
            extra=extra or None,
        )


def capture_stdlib(
    level: str = "WARNING",
    logger: Union[str, Logger, None] = None,
) -> StdlibToLog4pHandler:
    """Attach an inbound handler to the stdlib root logger.

    Records at or above *level* (a log4p level name) are forwarded to the
    log4p *logger* (the root logger by default). Returns the installed handler.
    """
    handler = StdlibToLog4pHandler(logger, level=_to_stdlib_level(level))
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > _to_stdlib_level(level):
        root.setLevel(_to_stdlib_level(level))
    root.addHandler(handler)
    return handler
