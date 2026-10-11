"""Thread-safety stress tests for loggers, appenders, and the diagnostic context."""

import os
import threading

import pytest

from log4p import (
    ConsoleAppender,
    FileAppender,
    MemoryAppender,
    PatternLayout,
    getLogger,
)
from log4p.context import MDC
from log4p.logger import getLoggerManager

THREADS = 16
PER_THREAD = 250


@pytest.fixture(autouse=True)
def _isolate():
    getLoggerManager().clear()
    getLoggerManager().warn_on_no_appenders = False
    yield
    getLoggerManager().clear()


def _run_workers(target, count=THREADS):
    barrier = threading.Barrier(count)
    errors = []

    def wrapped(index):
        try:
            barrier.wait()
            target(index)
        except Exception as exc:  # pragma: no cover - surfaced via assertion
            errors.append(exc)

    threads = [threading.Thread(target=wrapped, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors


def test_concurrent_getlogger_returns_single_instance():
    created = []
    lock = threading.Lock()

    def worker(_):
        logger = getLogger("stress.same")
        with lock:
            created.append(logger)

    _run_workers(worker)
    assert len({id(logger) for logger in created}) == 1


def test_concurrent_logging_counts_are_exact():
    appender = MemoryAppender(PatternLayout("%m"))
    logger = getLogger("stress.count")
    logger.setLevel("INFO")
    logger.addAppender(appender)

    def worker(index):
        for i in range(PER_THREAD):
            logger.info("t%d-%d", index, i)

    _run_workers(worker)
    assert len(appender.getRecords()) == THREADS * PER_THREAD


def test_concurrent_logging_writes_whole_lines():
    appender = MemoryAppender(PatternLayout("%m"))
    logger = getLogger("stress.lines")
    logger.setLevel("INFO")
    logger.addAppender(appender)

    def worker(index):
        for i in range(PER_THREAD):
            logger.info("value=%d.%d", index, i)

    _run_workers(worker)
    events = appender.getEvents()
    assert len(events) == THREADS * PER_THREAD
    assert all(ev.startswith("value=") and "." in ev for ev in events)


def test_concurrent_mdc_is_isolated_per_thread():
    appender = MemoryAppender(PatternLayout("%X{request} %m"))
    logger = getLogger("stress.mdc")
    logger.setLevel("INFO")
    logger.addAppender(appender)

    def worker(index):
        MDC.put("request", f"r{index}")
        for i in range(PER_THREAD):
            logger.info("%d", i)
        MDC.clear()

    _run_workers(worker)
    events = appender.getEvents()
    assert len(events) == THREADS * PER_THREAD
    grouped = {}
    for ev in events:
        request, _, value = ev.partition(" ")
        assert request.startswith("r") and request[1:].isdigit()
        grouped.setdefault(request, set()).add(value)
    assert len(grouped) == THREADS
    for values in grouped.values():
        assert values == {str(i) for i in range(PER_THREAD)}


def test_concurrent_file_appender_produces_intact_lines(tmp_path):
    path = os.path.join(tmp_path, "stress.log")
    appender = FileAppender(str(path), PatternLayout("%m%n"), immediateFlush=False)
    logger = getLogger("stress.file")
    logger.setLevel("INFO")
    logger.addAppender(appender)

    def worker(index):
        for i in range(PER_THREAD):
            logger.info("line-%d-%d", index, i)

    _run_workers(worker)
    appender.flush()

    with open(path) as handle:
        lines = [line.rstrip("\n") for line in handle]

    assert len(lines) == THREADS * PER_THREAD
    assert all(line.startswith("line-") and line.count("-") == 2 for line in lines)
    assert len(set(lines)) == THREADS * PER_THREAD


def test_memory_appender_maxsize_consistent_under_load():
    appender = MemoryAppender(PatternLayout("%m"), maxSize=50)
    logger = getLogger("stress.max")
    logger.setLevel("INFO")
    logger.addAppender(appender)

    def worker(index):
        for i in range(PER_THREAD):
            logger.info("%d.%d", index, i)

    _run_workers(worker)
    assert len(appender.getEvents()) == 50
    assert len(appender.getRecords()) == 50


def test_concurrent_hierarchy_creation_is_consistent():
    def worker(index):
        for i in range(40):
            name = "race.%d.%d" % (index % 4, i)
            child = getLogger(name)
            parent = getLogger(name.rsplit(".", 1)[0])
            assert child.parent is parent or child.parent in (parent, child.parent)

    _run_workers(worker)
    manager = getLoggerManager()
    for logger in manager.allLoggers():
        if logger.name:
            assert logger.parent is not None
            assert logger.parent.name == "" or logger.name.startswith(
                logger.parent.name + "."
            )


def test_console_appender_concurrent_writes_are_locked():
    import io

    buf = io.StringIO()
    appender = ConsoleAppender(PatternLayout("%m%n"), stream=buf)
    logger = getLogger("stress.console")
    logger.setLevel("INFO")
    logger.addAppender(appender)

    def worker(index):
        for i in range(PER_THREAD):
            logger.info("c-%d-%d", index, i)

    _run_workers(worker)
    lines = buf.getvalue().splitlines()
    assert len(lines) == THREADS * PER_THREAD
