import io

from log4p2 import (
    ConsoleAppender,
    FailoverAppender,
    Level,
    LogRecord,
    PatternLayout,
)
from log4p2.logger import getLoggerManager


def record(message="hi"):
    return LogRecord(name="app", level=Level.INFO, message=message)


class FlakyAppender(ConsoleAppender):
    """Fails while ``broken`` is True, otherwise writes to its stream."""

    def __init__(self, stream, broken=True):
        super().__init__(PatternLayout("%m"), stream=stream)
        self.broken = broken

    def append(self, rec):
        if self.broken:
            raise OSError("boom")
        super().append(rec)


def test_failover_uses_primary_when_healthy():
    primary = ConsoleAppender(PatternLayout("%m"), stream=io.StringIO())
    backup = ConsoleAppender(PatternLayout("%m"), stream=io.StringIO())
    app = FailoverAppender(primary, [backup])
    app.doAppend(record("hello"))
    app.stop()
    assert primary.stream.getvalue() == "hello\n"
    assert backup.stream.getvalue() == ""


def test_failover_falls_back_when_primary_fails():
    primary = FlakyAppender(io.StringIO(), broken=True)
    backup = ConsoleAppender(PatternLayout("%m"), stream=io.StringIO())
    app = FailoverAppender(primary, [backup])
    app.doAppend(record("hello"))
    app.stop()
    assert backup.stream.getvalue() == "hello\n"


def test_failover_sticks_with_recovered_active():
    primary = FlakyAppender(io.StringIO(), broken=True)
    backup = ConsoleAppender(PatternLayout("%m"), stream=io.StringIO())
    app = FailoverAppender(primary, [backup])
    app.doAppend(record("first"))
    primary.broken = False
    app.doAppend(record("second"))
    app.stop()
    assert backup.stream.getvalue() == "first\nsecond\n"


def test_failover_raises_when_all_fail():
    import pytest

    primary = FlakyAppender(io.StringIO(), broken=True)
    backup = FlakyAppender(io.StringIO(), broken=True)
    app = FailoverAppender(primary, [backup])
    with pytest.raises(RuntimeError):
        app.append(record("x"))


def test_failover_lifecycle_and_layout():
    primary = ConsoleAppender(PatternLayout("%p"), stream=io.StringIO())
    backup = ConsoleAppender(stream=io.StringIO())
    app = FailoverAppender(primary, [backup])
    app.start()
    assert primary.isStarted() and backup.isStarted()
    assert app.getLayout() is primary.getLayout()
    app.stop()
    assert not primary.isStarted()


def test_failover_config_builds_children():
    from log4p2 import config as log4p_config

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["failover"]},
            "appenders": {
                "dead": {
                    "class": "tests.test_failover_appender.FlakyAppender",
                    "stream": io.StringIO(),
                },
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                },
                "failover": {
                    "class": "FailoverAppender",
                    "primary": "dead",
                    "failovers": ["console"],
                },
            },
        }
    )
    root = getLoggerManager().root
    app = root.getAppenders()[0]
    assert isinstance(app, FailoverAppender)
    root.info("saved")
    app.stop()
    assert buf.getvalue() == "saved\n"
