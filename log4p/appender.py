"""Appenders are the output destinations: console, files, rotating files.

Every appender owns a :class:`~log4p.layout.Layout` and an optional list of
:class:`~log4p.filter.Filter` objects that gate what it writes.
"""

from __future__ import annotations

import gzip
import os
import queue
import shutil
import sys
import threading
import time
from typing import List, Optional, TextIO, Union

from .error import ErrorHandler
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
        self._error_handler: ErrorHandler = ErrorHandler()

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

    def setErrorHandler(self, handler: ErrorHandler) -> None:
        self._error_handler = handler

    def getErrorHandler(self) -> ErrorHandler:
        return self._error_handler

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
        self._error_handler.handle(record, sys.exc_info())

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


class AsyncAppender(Appender):
    """Wrap another appender and hand off records to a background thread.

    The logging call returns immediately while a daemon worker writes to the
    wrapped appender, so slow destinations (sockets, spinning disks) never
    block application threads.

    *overflow* controls what happens when the queue is full: ``"block"`` waits
    for space (no loss, may slow the caller) or ``"discard"`` drops the record
    and increments :attr:`dropped`.
    """

    _STOP = object()

    def __init__(
        self,
        appender: Appender,
        queue_size: int = 1024,
        overflow: str = "block",
        layout: Optional[Layout] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        if overflow not in ("block", "discard"):
            raise ValueError("overflow must be 'block' or 'discard'")
        self.appender = appender
        self.queue_size = queue_size
        self.overflow = overflow
        self._queue: "queue.Queue" = queue.Queue(maxsize=queue_size)
        self._worker: Optional[threading.Thread] = None
        self._dropped = 0

    @property
    def dropped(self) -> int:
        return self._dropped

    def getLayout(self) -> Layout:
        return self.appender.getLayout()

    def start(self) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self.appender.start()
                self._worker = threading.Thread(
                    target=self._run_worker,
                    name=f"log4p-async-{self._name}",
                    daemon=True,
                )
                self._worker.start()
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                self._queue.put(self._STOP)
                self._worker.join()
            self._worker = None
            self.appender.stop()
            self._started = False

    def flush(self) -> None:
        self._queue.join()
        self.appender.flush()

    def append(self, record: LogRecord) -> None:
        if not self._started:
            self.start()
        if self.overflow == "block":
            self._queue.put(record)
        else:
            try:
                self._queue.put_nowait(record)
            except queue.Full:
                self._dropped += 1

    def _run_worker(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is self._STOP:
                    break
                self.appender.doAppend(item)
            except Exception:  # pragma: no cover - delegate handles its own errors
                pass
            finally:
                self._queue.task_done()


class TimedRotatingFileAppender(FileAppender):
    """Roll the file on a time schedule (like log4j's ``TimeBasedRollingPolicy``).

    *when* is one of ``S`` (seconds), ``M`` (minutes), ``H`` (hours), ``D`` or
    ``midnight`` (days), or ``W0``..``W6`` (weekly, Monday = 0). *interval*
    multiplies the unit. Rotated files are named ``<file>.<timestamp>`` and,
    when *compress* is set, gzipped. At most *backupCount* are kept (0 = keep
    all).
    """

    _SUFFIXES = {
        "S": "%Y-%m-%d_%H-%M-%S",
        "M": "%Y-%m-%d_%H-%M",
        "H": "%Y-%m-%d_%H",
        "D": "%Y-%m-%d",
        "MIDNIGHT": "%Y-%m-%d",
        "W": "%Y-%m-%d",
    }

    def __init__(
        self,
        filename: str,
        when: str = "h",
        interval: int = 1,
        backupCount: int = 0,
        utc: bool = False,
        compress: bool = False,
        layout: Optional[Layout] = None,
        encoding: str = "utf-8",
        immediateFlush: bool = True,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(
            filename=filename,
            layout=layout,
            append=True,
            encoding=encoding,
            immediateFlush=immediateFlush,
            threshold=threshold,
            name=name,
        )
        self.when = when.upper()
        self.interval = interval
        self.backupCount = backupCount
        self.utc = utc
        self.compress = compress
        if self.when not in ("S", "M", "H", "D", "MIDNIGHT") and not self.when.startswith("W"):
            raise ValueError(f"invalid 'when' value: {when!r}")
        if self.when.startswith("W"):
            if len(self.when) != 2 or not self.when[1].isdigit() or not 0 <= int(self.when[1]) <= 6:
                raise ValueError("weekly 'when' must be W0..W6")
            self._day_of_week = int(self.when[1])
        self.rollover_at = 0.0

    def start(self) -> None:
        with self._lock:
            fresh = self._stream is None
            super().start()
            if fresh:
                self.rollover_at = self._compute_rollover(time.time())

    def _write(self, text: str) -> None:
        if self._stream is None:
            self.start()
        now = time.time()
        if now >= self.rollover_at:
            self._rollover(time.time())
        super()._write(text)

    def _suffix_for(self, timestamp: float) -> str:
        prefix = "W" if self.when.startswith("W") else self.when
        fmt = self._SUFFIXES.get(prefix, "%Y-%m-%d")
        converter = time.gmtime if self.utc else time.localtime
        return time.strftime(fmt, converter(timestamp))

    def _compute_rollover(self, ts: float) -> float:
        when = self.when
        if when == "S":
            period = self.interval
            return ts - (ts % period) + period
        if when == "M":
            period = 60 * self.interval
            return ts - (ts % period) + period
        if when == "H":
            period = 3600 * self.interval
            return ts - (ts % period) + period

        converter = time.gmtime if self.utc else time.localtime
        lt = converter(ts)
        seconds_into_day = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec
        next_midnight = ts - seconds_into_day + 86400

        if when in ("D", "MIDNIGHT"):
            return next_midnight + (self.interval - 1) * 86400

        days_ahead = (self._day_of_week - lt.tm_wday) % 7
        candidate = ts - seconds_into_day + days_ahead * 86400
        if candidate <= ts:
            candidate += 7 * 86400
        return candidate + (self.interval - 1) * 7 * 86400

    def _rollover(self, now: float) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        suffix = self._suffix_for(self.rollover_at - 1)
        rotated = f"{self.filename}.{suffix}"
        if os.path.exists(self.filename):
            if os.path.exists(rotated):
                os.remove(rotated)
            os.replace(self.filename, rotated)
            if self.compress:
                with open(rotated, "rb") as src, gzip.open(rotated + ".gz", "wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.remove(rotated)
        self._expire_backups()
        self.rollover_at = self._compute_rollover(now)
        self.start()

    def _expire_backups(self) -> None:
        if self.backupCount <= 0:
            return
        directory = os.path.dirname(os.path.abspath(self.filename)) or "."
        base = os.path.basename(self.filename) + "."
        candidates = []
        for entry in os.listdir(directory):
            if entry.startswith(base):
                candidates.append(os.path.join(directory, entry))
        candidates.sort()
        for stale in candidates[:-self.backupCount]:
            try:
                os.remove(stale)
            except OSError:  # pragma: no cover
                pass
