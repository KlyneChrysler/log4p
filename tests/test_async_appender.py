import io

from log4p import (
    AsyncAppender,
    ConsoleAppender,
    Level,
    LogRecord,
    PatternLayout,
)


def record(message="hello", level=Level.INFO):
    return LogRecord(name="app", level=level, message=message)


def test_async_appender_delivers_after_flush():
    buf = io.StringIO()
    delegate = ConsoleAppender(PatternLayout("%m"), stream=buf)
    async_app = AsyncAppender(delegate)
    async_app.start()
    for i in range(50):
        async_app.doAppend(record(f"line-{i}"))
    async_app.flush()
    async_app.stop()
    lines = buf.getvalue().splitlines()
    assert lines[0] == "line-0"
    assert lines[-1] == "line-49"
    assert len(lines) == 50


def test_async_appender_stop_drains_queue():
    buf = io.StringIO()
    delegate = ConsoleAppender(PatternLayout("%m"), stream=buf)
    async_app = AsyncAppender(delegate)
    async_app.start()
    for i in range(20):
        async_app.doAppend(record(f"n{i}"))
    async_app.stop()  # must drain before returning
    assert len(buf.getvalue().splitlines()) == 20


def test_async_appender_overflow_discard_counts():
    buf = io.StringIO()
    delegate = ConsoleAppender(PatternLayout("%m"), stream=buf)
    app = AsyncAppender(delegate, queue_size=2, overflow="discard")
    app.start()
    for i in range(200):
        app.append(record(f"x{i}"))
    app.flush()
    app.stop()
    total = len(buf.getvalue().splitlines()) + app.dropped
    assert app.dropped >= 0
    assert total == 200


def test_async_appender_invalid_overflow():
    import pytest

    with pytest.raises(ValueError):
        AsyncAppender(ConsoleAppender(stream=io.StringIO()), overflow="maybe")


def test_async_appender_gets_layout_from_delegate():
    layout = PatternLayout("%p %m")
    app = AsyncAppender(ConsoleAppender(layout, stream=io.StringIO()))
    assert app.getLayout() is layout


def test_async_appender_buffer_size_and_blocking_aliases():
    delegate = ConsoleAppender(stream=io.StringIO())
    app = AsyncAppender(delegate, bufferSize=4, blocking=False)
    assert app.queue_size == 4
    assert app.overflow == "discard"
    assert AsyncAppender(delegate, blocking=True).overflow == "block"
    assert AsyncAppender(delegate).overflow == "block"


def test_async_appender_discarding_threshold():
    delegate = ConsoleAppender(PatternLayout("%m"), stream=io.StringIO())
    app = AsyncAppender(delegate, queue_size=2, discardingThreshold=1)
    app._started = True  # keep the worker idle so the queue fills deterministically
    for _ in range(10):
        app.append(record("info"))
    assert app.dropped == 9
    assert app._queue.qsize() == 1
