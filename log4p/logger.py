"""Loggers and the hierarchy that connects them.

Mirrors log4j: loggers are named with dots (``app.db.pool``), inherit their
level from the nearest ancestor that sets one, and propagate events up the
chain unless ``additivity`` is turned off.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Any, List, Optional, Sequence, Union

from .appender import Appender
from .context import MDC, NDC
from .filter import Filter, FilterReply
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
from .record import LogRecord


class Logger:
    """A named logger. Create these via :func:`getLogger`, not directly."""

    def __init__(self, name: str, manager: "LoggerManager") -> None:
        self.name = name
        self.manager = manager
        self.parent: Optional[Logger] = None
        self.level: Optional[Level] = None
        self.additivity: bool = True
        self._appenders: List[Appender] = []
        self._filters: List[Filter] = []
        self._lock = threading.RLock()

    # -- identity ------------------------------------------------------
    def getName(self) -> str:
        return self.name

    def getParent(self) -> Optional["Logger"]:
        return self.parent

    def getChild(self, suffix: str) -> "Logger":
        base = f"{self.name}.{suffix}" if self.name else suffix
        return self.manager.getLogger(base)

    # -- level ---------------------------------------------------------
    def setLevel(self, level: Union[str, int, Level, None]) -> None:
        self.level = None if level is None else getLevel(level)

    def getLevel(self) -> Optional[Level]:
        return self.level

    def getEffectiveLevel(self) -> Level:
        logger: Optional[Logger] = self
        while logger is not None:
            if logger.level is not None:
                return logger.level
            logger = logger.parent
        return WARN

    def isEnabledFor(self, level: Union[str, int, Level]) -> bool:
        return int(getLevel(level)) >= int(self.getEffectiveLevel())

    # -- appenders -----------------------------------------------------
    def addAppender(self, appender: Appender) -> None:
        with self._lock:
            self._appenders.append(appender)

    def removeAppender(self, appender: Appender) -> None:
        with self._lock:
            if appender in self._appenders:
                self._appenders.remove(appender)

    def removeAllAppenders(self) -> None:
        with self._lock:
            self._appenders.clear()

    def getAppenders(self) -> List[Appender]:
        return list(self._appenders)

    def setAdditivity(self, additive: bool) -> None:
        self.additivity = additive

    def getAdditivity(self) -> bool:
        return self.additivity

    # -- filters -------------------------------------------------------
    def addFilter(self, filt: Filter) -> None:
        self._filters.append(filt)

    def getFilters(self) -> List[Filter]:
        return list(self._filters)

    def clearFilters(self) -> None:
        self._filters.clear()

    def _passes_filters(self, record: LogRecord) -> bool:
        for filt in self._filters:
            reply = filt.decide(record)
            if reply == FilterReply.DENY:
                return False
            if reply == FilterReply.ACCEPT:
                return True
        return True

    # -- logging -------------------------------------------------------
    def trace(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if int(TRACE) >= int(self.getEffectiveLevel()):
            self._log(TRACE, msg, args, **kwargs)

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if int(DEBUG) >= int(self.getEffectiveLevel()):
            self._log(DEBUG, msg, args, **kwargs)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if int(INFO) >= int(self.getEffectiveLevel()):
            self._log(INFO, msg, args, **kwargs)

    def warn(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if int(WARN) >= int(self.getEffectiveLevel()):
            self._log(WARN, msg, args, **kwargs)

    warning = warn

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if int(ERROR) >= int(self.getEffectiveLevel()):
            self._log(ERROR, msg, args, **kwargs)

    def fatal(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if int(FATAL) >= int(self.getEffectiveLevel()):
            self._log(FATAL, msg, args, **kwargs)

    critical = fatal

    def log(self, level: Union[str, int, Level], msg: Any, *args: Any, **kwargs: Any) -> None:
        lvl = getLevel(level)
        if int(lvl) >= int(self.getEffectiveLevel()):
            self._log(lvl, msg, args, **kwargs)

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("exc_info", True)
        self.error(msg, *args, **kwargs)

    # -- internals -----------------------------------------------------
    def _log(
        self,
        level: Level,
        msg: Any,
        args: Sequence[Any],
        *,
        exc_info: Any = None,
        extra: Optional[dict] = None,
        stacklevel: int = 0,
    ) -> None:
        caller = _find_caller(stacklevel)
        if exc_info is True:
            exc_info = sys.exc_info()
        elif exc_info and not isinstance(exc_info, tuple):
            exc_info = sys.exc_info()
        if exc_info and exc_info[0] is None:
            exc_info = None

        context = MDC.getCopy()
        if extra:
            context.update(extra)
        record = LogRecord(
            name=self.name,
            level=level,
            message=msg,
            args=args or None,
            exc_info=exc_info,
            pathname=caller[0],
            lineno=caller[1],
            funcName=caller[2],
            context=context,
            ndc=NDC.get(),
        )

        if self._filters and not self._passes_filters(record):
            return
        self._callHandlers(record)

    def _callHandlers(self, record: LogRecord) -> None:
        logger: Optional[Logger] = self
        found = False
        while logger is not None:
            for appender in logger._appenders:
                found = True
                appender.doAppend(record)
            if not logger.additivity:
                break
            logger = logger.parent
        if not found:
            self.manager.warnNoAppenders(self.name)

    def __repr__(self) -> str:
        return f"<Logger {self.name!r} level={self.level}>"


_LOGGER_FILE = os.path.normcase(os.path.abspath(__file__))


def _find_caller(stacklevel: int = 0):
    """Return ``(filename, lineno, funcname)`` of the user's logging call.

    Frames belonging to this module (the convenience methods and ``_log``)
    are skipped, so callers get attributed to their own code regardless of
    which entry point they used.  *stacklevel* adds extra frames to skip for
    wrappers around the logger.
    """
    try:
        frame = sys._getframe(1)
    except ValueError:  # pragma: no cover
        return ("", 0, "")
    remaining = stacklevel
    while frame is not None:
        if os.path.normcase(frame.f_code.co_filename) == _LOGGER_FILE:
            frame = frame.f_back
            continue
        if remaining > 0:
            remaining -= 1
            frame = frame.f_back
            continue
        code = frame.f_code
        return (code.co_filename, frame.f_lineno, code.co_name)
    return ("", 0, "")


class LoggerManager:
    """Registry that owns every :class:`Logger` and their parent links."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._loggers: dict[str, Logger] = {}
        self.root: Logger = Logger("", self)
        self.root.level = WARN
        self._loggers[""] = self.root
        self.warn_on_no_appenders: bool = True
        self._warned: set = set()

    def getLogger(self, name: Union[str, None] = None) -> Logger:
        if name is None:
            name = ""
        if not isinstance(name, str):
            name = str(name)
        if name and name.endswith("."):
            name = name[:-1]
        with self._lock:
            existing = self._loggers.get(name)
            if existing is not None:
                return existing
            logger = Logger(name, self)
            logger.parent = self._find_parent(name)
            self._loggers[name] = logger
            self._reparent_children(logger)
            return logger

    def _find_parent(self, name: str) -> Logger:
        parent_name = name
        while parent_name:
            idx = parent_name.rfind(".")
            parent_name = parent_name[:idx] if idx > -1 else ""
            candidate = self._loggers.get(parent_name)
            if candidate is not None:
                return candidate
        return self.root

    def _reparent_children(self, logger: Logger) -> None:
        prefix = logger.name + "."
        for other in self._loggers.values():
            if other.name.startswith(prefix):
                other.parent = self._find_parent(other.name)

    def getLoggerNames(self) -> List[str]:
        return sorted(self._loggers.keys())

    def warnNoAppenders(self, name: str) -> None:
        if not self.warn_on_no_appenders or name in self._warned:
            return
        self._warned.add(name)
        sys.stderr.write(
            "log4p: no appenders could be found for logger (%s). "
            "Configure log4p or call addAppender().\n" % (name or "root")
        )

    def shutdown(self) -> None:
        with self._lock:
            for logger in self._loggers.values():
                for appender in logger.getAppenders():
                    try:
                        appender.flush()
                        appender.stop()
                    except Exception:  # pragma: no cover
                        pass

    def clear(self) -> None:
        """Detach and stop every appender and reset logger levels/additivity.

        Keeps existing :class:`Logger` instances valid so references held by
        application code keep working after a reconfiguration.
        """
        with self._lock:
            self._warned.clear()
            for logger in self._loggers.values():
                for appender in logger.getAppenders():
                    try:
                        appender.flush()
                        appender.stop()
                    except Exception:  # pragma: no cover
                        pass
                    logger.removeAppender(appender)
                logger.clearFilters()
                logger.setAdditivity(True)
                logger.setLevel(None)
            self.root.setAdditivity(True)
            self.root.setLevel(WARN)

    def reset(self) -> None:  # pragma: no cover - test helper
        self.shutdown()
        self._loggers.clear()
        self._warned.clear()
        self.root = Logger("", self)
        self.root.level = WARN
        self._loggers[""] = self.root


_DEFAULT = LoggerManager()


def getLogger(name: Union[str, None] = None) -> Logger:
    """Return (creating if needed) the logger called *name*."""
    return _DEFAULT.getLogger(name)


def getRootLogger() -> Logger:
    return _DEFAULT.root


def getLoggerManager() -> LoggerManager:
    return _DEFAULT


def shutdown() -> None:
    """Flush and stop every appender across the hierarchy."""
    _DEFAULT.shutdown()
