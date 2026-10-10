"""Appenders are the output destinations: console, files, rotating files.

Every appender owns a :class:`~log4p.layout.Layout` and an optional list of
:class:`~log4p.filter.Filter` objects that gate what it writes.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from typing import List, Optional, TextIO, Union

from .filter import Filter, FilterReply
from .layout import Layout, PatternLayout
from .levels import Level, getLevel
from .record import LogRecord


class Appender:
    """Base class for all appenders."""

    def __init__(
        self,
        name: Optional[str] = None,
        layout: Optional[Layout] = None,
        threshold: Optional[Union[str, int, Level]] = None,
    ) -> None:
        self._name = name or self.__class__.__name__
        self._layout: Layout = layout if layout is not None else PatternLayout()
        self._filters: List[Filter] = []
        self._threshold: Optional[Level] = getLevel(threshold) if threshold else None
        self._started = False
        self._lock = threading.RLock()

    # -- configuration -------------------------------------------------
    def setName(self, name: str) -> None:
        self._name = name

    def getName(self) -> str:
        return self._name

    def setLayout(self, layout: Layout) -> None:
        self._layout = layout

    def getLayout(self) -> Layout:
        return self._layout

    def addFilter(self, filt: Filter) -> None:
        self._filters.append(filt)

    def removeFilter(self, filt: Filter) -> None:
        if filt in self._filters:
            self._filters.remove(filt)

    def clearFilters(self) -> None:
        self._filters.clear()

    def setThreshold(self, level: Union[str, int, Level]) -> None:
        self._threshold = getLevel(level)

    def getThreshold(self) -> Optional[Level]:
        return self._threshold

    def isAsSevereAsThreshold(self, level: Level) -> bool:
        return self._threshold is None or int(level) >= int(self._threshold)

    # -- lifecycle -----------------------------------------------------
    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def isStarted(self) -> bool:
        return self._started

    def flush(self) -> None:
        pass

    # -- core ----------------------------------------------------------
    def _render(self, record: LogRecord) -> str:
        text = self._layout.format(record)
        if text is None:
            text = ""
        if record.exc_info and not self._layout.ignoresExceptions:
            exc = record.getExceptionText()
            if exc:
                if text and not text.endswith("\n"):
                    text += "\n"
                text += exc
        return text

    def _passes_filters(self, record: LogRecord) -> bool:
        for filt in self._filters:
            reply = filt.decide(record)
            if reply == FilterReply.DENY:
                return False
            if reply == FilterReply.ACCEPT:
                return True
        return True

    def doAppend(self, record: LogRecord) -> None:
        with self._lock:
            if not self.isAsSevereAsThreshold(record.level):
                return
            if not self._passes_filters(record):
                return
            if not self._started:
                self.start()
            try:
                self.append(record)
            except Exception:  # pragma: no cover - never let logging crash callers
                self.handleError(record)

    def handleError(self, record: LogRecord) -> None:
        sys.stderr.write("log4p: error appending record on %r\n" % self._name)
        traceback.print_exc(file=sys.stderr)

    def append(self, record: LogRecord) -> None:  # pragma: no cover
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self._name!r}>"


class ConsoleAppender(Appender):
    """Write to ``stdout`` (default) or ``stderr``.

    Pass ``stream`` to redirect output (useful in tests).
    """

    def __init__(
        self,
        layout: Optional[Layout] = None,
        target: str = "stdout",
        stream: Optional[TextIO] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        if target not in ("stdout", "stderr"):
            raise ValueError("target must be 'stdout' or 'stderr'")
        self.target = target
        self._stream = stream

    @property
    def stream(self) -> TextIO:
        if self._stream is not None:
            return self._stream
        return sys.stdout if self.target == "stdout" else sys.stderr

    def append(self, record: LogRecord) -> None:
        text = self._render(record)
        if not text.endswith("\n"):
            text += "\n"
        self.stream.write(text)
        self.stream.flush()


class FileAppender(Appender):
    """Append to a file, optionally truncating on startup."""

    def __init__(
        self,
        filename: str,
        layout: Optional[Layout] = None,
        append: bool = True,
        encoding: str = "utf-8",
        immediateFlush: bool = True,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        self.filename = filename
        self.append_mode = append
        self.encoding = encoding
        self.immediateFlush = immediateFlush
        self._stream: Optional[TextIO] = None

    def start(self) -> None:
        with self._lock:
            if self._stream is None:
                directory = os.path.dirname(os.path.abspath(self.filename))
                os.makedirs(directory, exist_ok=True)
                mode = "a" if self.append_mode else "w"
                self._stream = open(self.filename, mode, encoding=self.encoding)
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            self._started = False

    def flush(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._stream.flush()

    def _write(self, text: str) -> None:
        if self._stream is None:
            self.start()
        self._stream.write(text)
        if self.immediateFlush:
            self._stream.flush()

    def append(self, record: LogRecord) -> None:
        text = self._render(record)
        if not text.endswith("\n"):
            text += "\n"
        self._write(text)


class RotatingFileAppender(FileAppender):
    """Size-based rolling file appender (like log4j's ``RollingFileAppender``).

    Once the active file exceeds *maxBytes*, it is rotated: ``app.log`` becomes
    ``app.log.1``, ``app.log.1`` becomes ``app.log.2`` and so on, keeping at most
    *backupCount* backups.
    """

    def __init__(
        self,
        filename: str,
        maxBytes: int = 10 * 1024 * 1024,
        backupCount: int = 5,
        layout: Optional[Layout] = None,
        append: bool = True,
        encoding: str = "utf-8",
        immediateFlush: bool = True,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(
            filename=filename,
            layout=layout,
            append=append,
            encoding=encoding,
            immediateFlush=immediateFlush,
            threshold=threshold,
            name=name,
        )
        if maxBytes <= 0:
            raise ValueError("maxBytes must be positive")
        if backupCount < 0:
            raise ValueError("backupCount must be non-negative")
        self.maxBytes = maxBytes
        self.backupCount = backupCount

    def _write(self, text: str) -> None:
        if self._stream is None:
            self.start()
            if os.path.exists(self.filename):
                try:
                    self._stream.seek(0, os.SEEK_END)
                    if self._stream.tell() >= self.maxBytes:
                        self._rotate()
                except OSError:
                    pass
        encoded_len = len(text.encode(self.encoding))
        if self._stream.tell() + encoded_len > self.maxBytes:
            self._rotate()
        super()._write(text)

    def _rotate(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        for i in range(self.backupCount - 1, 0, -1):
            src = f"{self.filename}.{i}"
            dst = f"{self.filename}.{i + 1}"
            if os.path.exists(src):
                os.replace(src, dst)
        if self.backupCount > 0 and os.path.exists(self.filename):
            os.replace(self.filename, f"{self.filename}.1")
        elif os.path.exists(self.filename):
            os.remove(self.filename)
        self.start()
