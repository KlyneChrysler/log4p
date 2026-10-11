"""Appenders are the output destinations: console, files, rotating files.

Every appender owns a :class:`~log4p2.layout.Layout` and an optional list of
:class:`~log4p2.filter.Filter` objects that gate what it writes.
"""

from __future__ import annotations

import gzip
import os
import queue
import shutil
import sys
import threading
import time
from typing import List, Optional, TextIO, Tuple, Union

from .cron import CronExpression
from .error import ErrorHandler
from .filter import Filter, FilterReply
from .layout import Layout, PatternLayout
from .levels import WARN, Level, getLevel
from .record import LogRecord

_SIZE_UNITS = {
    "": 1,
    "b": 1,
    "k": 1024,
    "kb": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "t": 1024**4,
    "tb": 1024**4,
}


def parse_size(value: Union[int, str]) -> int:
    """Turn ``"10MB"`` (or ``"10 MB"``, ``"1024"``, an int) into a byte count."""
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(" ", "")
    number = ""
    unit = ""
    for index, ch in enumerate(text):
        if ch.isdigit() or ch == ".":
            number += ch
        else:
            unit = text[index:].lower()
            break
    if not number:
        raise ValueError(f"invalid size: {value!r}")
    if unit not in _SIZE_UNITS:
        raise ValueError(f"unknown size unit: {unit!r}")
    return int(float(number) * _SIZE_UNITS[unit])


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

    def getFilters(self) -> List[Filter]:
        return list(self._filters)

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
        immediateFlush: bool = True,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        if target not in ("stdout", "stderr"):
            raise ValueError("target must be 'stdout' or 'stderr'")
        self.target = target
        self.immediateFlush = immediateFlush
        self._stream = stream

    @property
    def stream(self) -> TextIO:
        if self._stream is not None:
            return self._stream
        return sys.stdout if self.target == "stdout" else sys.stderr

    def start(self) -> None:
        with self._lock:
            if not self._started:
                header = self._layout.header()
                if header:
                    self.stream.write(header)
                    self.stream.flush()
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if self._started:
                footer = self._layout.footer()
                if footer:
                    self.stream.write(footer)
                if self.immediateFlush or footer:
                    self.stream.flush()
            self._started = False

    def flush(self) -> None:
        self.stream.flush()

    def append(self, record: LogRecord) -> None:
        text = self._render(record)
        if not text.endswith("\n"):
            text += "\n"
        self.stream.write(text)
        if self.immediateFlush:
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
        onStartup: bool = False,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        self.filename = filename
        self.append_mode = append
        self.encoding = encoding
        self.immediateFlush = immediateFlush
        self.onStartup = onStartup
        self._startup_rolled = False
        self._stream: Optional[TextIO] = None
        self._header_written = False

    def _has_existing_data(self) -> bool:
        try:
            return os.path.exists(self.filename) and os.path.getsize(self.filename) > 0
        except OSError:  # pragma: no cover
            return False

    def _needs_startup_roll(self) -> bool:
        if not self.onStartup or self._startup_rolled:
            return False
        self._startup_rolled = True
        return self._has_existing_data()

    def start(self) -> None:
        with self._lock:
            if self._stream is None:
                directory = os.path.dirname(os.path.abspath(self.filename))
                os.makedirs(directory, exist_ok=True)
                mode = "a" if self.append_mode else "w"
                self._stream = open(self.filename, mode, encoding=self.encoding)
                self._write_header_if_empty()
            self._started = True

    def _write_header_if_empty(self) -> None:
        if self._header_written or self._stream is None:
            return
        try:
            self._stream.seek(0, os.SEEK_END)
            empty = self._stream.tell() == 0
        except OSError:
            empty = True
        header = self._layout.header()
        if empty and header:
            self._stream.write(header)
            self._stream.flush()
        self._header_written = True

    def stop(self) -> None:
        with self._lock:
            if self._stream is not None:
                footer = self._layout.footer()
                if footer:
                    self._stream.write(footer)
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
        maxBytes: Union[int, str] = 10 * 1024 * 1024,
        backupCount: int = 5,
        layout: Optional[Layout] = None,
        append: bool = True,
        encoding: str = "utf-8",
        immediateFlush: bool = True,
        onStartup: bool = False,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(
            filename=filename,
            layout=layout,
            append=append,
            encoding=encoding,
            immediateFlush=immediateFlush,
            onStartup=onStartup,
            threshold=threshold,
            name=name,
        )
        maxBytes = parse_size(maxBytes)
        if maxBytes <= 0:
            raise ValueError("maxBytes must be positive")
        if backupCount < 0:
            raise ValueError("backupCount must be non-negative")
        self.maxBytes = maxBytes
        self.backupCount = backupCount

    def start(self) -> None:
        with self._lock:
            fresh = self._stream is None
            super().start()
            if not fresh:
                return
            if self._needs_startup_roll():
                self._rotate()
                return
            try:
                self._stream.seek(0, os.SEEK_END)
                if self._stream.tell() >= self.maxBytes:
                    self._rotate()
            except OSError:
                pass

    def _write(self, text: str) -> None:
        if self._stream is None:
            self.start()
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
        self._header_written = False
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
        overflow: Optional[str] = None,
        layout: Optional[Layout] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
        bufferSize: Optional[int] = None,
        blocking: bool = True,
        discardingThreshold: int = 0,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        if bufferSize is not None:
            queue_size = bufferSize
        if overflow is None:
            overflow = "block" if blocking else "discard"
        if overflow not in ("block", "discard"):
            raise ValueError("overflow must be 'block' or 'discard'")
        self.appender = appender
        self.queue_size = queue_size
        self.overflow = overflow
        self.discardingThreshold = discardingThreshold
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
        if (
            self.discardingThreshold
            and int(record.level) < int(WARN)
            and self._queue.qsize() >= self.queue_size - self.discardingThreshold
        ):
            self._dropped += 1
            return
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


class RoutingAppender(Appender):
    """Route each event to a child appender chosen by a context value.

    *routes* maps a context value to an appender. When the record's value for
    *key* has no route, *default* names the fallback route (a key in *routes*);
    unmatched events are dropped when no default is set.
    """

    def __init__(
        self,
        routes,
        key: str = "route",
        default: Optional[str] = None,
        layout: Optional[Layout] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        self.routes = dict(routes)
        self.key = key
        self.default = default

    def start(self) -> None:
        with self._lock:
            for appender in self.routes.values():
                appender.start()
            self._started = True

    def stop(self) -> None:
        with self._lock:
            for appender in self.routes.values():
                appender.stop()
            self._started = False

    def flush(self) -> None:
        for appender in self.routes.values():
            appender.flush()

    def getRoute(self, record: LogRecord) -> Optional[Appender]:
        value = str(record.context.get(self.key, ""))
        appender = self.routes.get(value)
        if appender is None and self.default is not None:
            appender = self.routes.get(self.default)
        return appender

    def append(self, record: LogRecord) -> None:
        appender = self.getRoute(record)
        if appender is not None:
            appender.doAppend(record)


class FailoverAppender(Appender):
    """Try a *primary* appender and fall back through *failovers* on error.

    The first appender that successfully writes an event becomes the active one
    and is tried first on the next event (log4j's ``FailoverAppender``).
    """

    def __init__(
        self,
        primary: Appender,
        failovers: Optional[List[Appender]] = None,
        layout: Optional[Layout] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        self.primary = primary
        self.failovers: List[Appender] = list(failovers) if failovers else []
        self._active = 0

    def _appenders(self) -> List[Appender]:
        return [self.primary] + self.failovers

    def getLayout(self) -> Layout:
        return self._appenders()[self._active].getLayout()

    def start(self) -> None:
        with self._lock:
            for appender in self._appenders():
                appender.start()
            self._started = True

    def stop(self) -> None:
        with self._lock:
            for appender in self._appenders():
                appender.stop()
            self._started = False

    def flush(self) -> None:
        for appender in self._appenders():
            appender.flush()

    def append(self, record: LogRecord) -> None:
        appenders = self._appenders()
        count = len(appenders)
        for offset in range(count):
            index = (self._active + offset) % count
            appender = appenders[index]
            try:
                if not appender.isStarted():
                    appender.start()
                appender.append(record)
            except Exception:  # pragma: no cover - depends on the peer
                continue
            self._active = index
            return
        raise RuntimeError("all failover appenders failed")


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
        onStartup: bool = False,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(
            filename=filename,
            layout=layout,
            append=True,
            encoding=encoding,
            immediateFlush=immediateFlush,
            onStartup=onStartup,
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
                if self._needs_startup_roll():
                    self._rollover(time.time())

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
        self._header_written = False
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


class SizeAndTimeBasedAppender(TimedRotatingFileAppender):
    """Roll when *either* the time period elapses *or* the file exceeds *maxBytes*.

    Combines :class:`TimedRotatingFileAppender` and
    :class:`RotatingFileAppender` (log4j's ``SizeAndTimeBasedRollingPolicy``).
    Rotated files are named ``<file>.<timestamp>``; if that name is taken (for
    example several size rolls within one period) a numeric suffix is appended.
    """

    def __init__(
        self,
        filename: str,
        maxBytes: Union[int, str] = 10 * 1024 * 1024,
        when: str = "d",
        interval: int = 1,
        backupCount: int = 7,
        utc: bool = False,
        compress: bool = False,
        layout: Optional[Layout] = None,
        encoding: str = "utf-8",
        immediateFlush: bool = True,
        onStartup: bool = False,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(
            filename=filename,
            when=when,
            interval=interval,
            backupCount=backupCount,
            utc=utc,
            compress=compress,
            layout=layout,
            encoding=encoding,
            immediateFlush=immediateFlush,
            onStartup=onStartup,
            threshold=threshold,
            name=name,
        )
        maxBytes = parse_size(maxBytes)
        if maxBytes <= 0:
            raise ValueError("maxBytes must be positive")
        self.maxBytes = maxBytes

    def _write(self, text: str) -> None:
        if self._stream is None:
            self.start()
        now = time.time()
        encoded_len = len(text.encode(self.encoding))
        if now >= self.rollover_at or self._stream.tell() + encoded_len > self.maxBytes:
            self._rollover(now)
        FileAppender._write(self, text)

    def _rollover(self, now: float) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        suffix = self._suffix_for(now)
        index = 1
        rotated = f"{self.filename}.{suffix}.{index}"
        while os.path.exists(rotated) or os.path.exists(rotated + ".gz"):
            index += 1
            rotated = f"{self.filename}.{suffix}.{index}"
        if os.path.exists(self.filename):
            os.replace(self.filename, rotated)
            if self.compress:
                with open(rotated, "rb") as src, gzip.open(rotated + ".gz", "wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.remove(rotated)
        self._expire_backups()
        self.rollover_at = self._compute_rollover(now)
        self._header_written = False
        self.start()

    def _expire_backups(self) -> None:
        if self.backupCount <= 0:
            return
        directory = os.path.dirname(os.path.abspath(self.filename)) or "."
        base = os.path.basename(self.filename) + "."
        candidates = [
            os.path.join(directory, entry)
            for entry in os.listdir(directory)
            if entry.startswith(base)
        ]

        def sort_key(path: str) -> Tuple[str, int]:
            stem = os.path.basename(path)[len(base) :]
            if stem.endswith(".gz"):
                stem = stem[:-3]
            suffix, _, index = stem.rpartition(".")
            return (suffix, int(index) if index.isdigit() else 0)

        candidates.sort(key=sort_key)
        for stale in candidates[: -self.backupCount]:
            try:
                os.remove(stale)
            except OSError:  # pragma: no cover
                pass


class NullAppender(Appender):
    """Discard every event (log4j's ``NullAppender``) - a ``/dev/null`` sink."""

    def append(self, record: LogRecord) -> None:
        pass


class CallableAppender(Appender):
    """Forward each record to a Python callable (the log4j2 ``ScriptAppender``
    analogue).

    *function* is called with the :class:`~log4p2.record.LogRecord`; anything it
    does with the event (or the rendered ``self._render(record)``) is up to the
    caller. Exceptions raised by *function* are routed to the error handler.
    """

    def __init__(
        self,
        function,
        layout: Optional[Layout] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        self.function = function

    def append(self, record: LogRecord) -> None:
        self.function(record)

    def flush(self) -> None:
        pass


class CronRollingFileAppender(TimedRotatingFileAppender):
    """Roll the file when a cron expression matches (log4j's
    ``CronTriggeringPolicy``).

    *cron* is a five- or six-field expression (see
    :class:`~log4p2.cron.CronExpression`). Rotated files are named
    ``<file>.<suffix>`` where *suffix* is a ``strftime`` format applied to the
    period start.
    """

    def __init__(
        self,
        filename: str,
        cron: str,
        suffix: str = "%Y-%m-%d_%H-%M-%S",
        backupCount: int = 0,
        utc: bool = False,
        compress: bool = False,
        layout: Optional[Layout] = None,
        encoding: str = "utf-8",
        immediateFlush: bool = True,
        onStartup: bool = False,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(
            filename=filename,
            when="d",
            interval=1,
            backupCount=backupCount,
            utc=utc,
            compress=compress,
            layout=layout,
            encoding=encoding,
            immediateFlush=immediateFlush,
            onStartup=onStartup,
            threshold=threshold,
            name=name,
        )
        self.cron = CronExpression(cron)
        self.suffix_format = suffix

    def _suffix_for(self, timestamp: float) -> str:
        converter = time.gmtime if self.utc else time.localtime
        return time.strftime(self.suffix_format, converter(timestamp))

    def _compute_rollover(self, ts: float) -> float:
        return self.cron.next_after(ts)


class MemoryAppender(Appender):
    """Capture rendered events in memory (handy for tests and assertions).

    *maxSize* keeps only the most recent N events/records when positive.
    """

    def __init__(
        self,
        layout: Optional[Layout] = None,
        maxSize: int = 0,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        self.maxSize = maxSize
        self.events: List[str] = []
        self.records: List[LogRecord] = []

    def append(self, record: LogRecord) -> None:
        self.events.append(self._render(record))
        self.records.append(record)
        if self.maxSize and len(self.events) > self.maxSize:
            del self.events[: -self.maxSize]
            del self.records[: -self.maxSize]

    def getEvents(self) -> List[str]:
        return list(self.events)

    def getRecords(self) -> List[LogRecord]:
        return list(self.records)

    def clear(self) -> None:
        self.events.clear()
        self.records.clear()

    def flush(self) -> None:
        pass
