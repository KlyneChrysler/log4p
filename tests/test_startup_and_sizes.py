import glob

import pytest

from log4p2 import (
    Level,
    LogRecord,
    PatternLayout,
    RotatingFileAppender,
    SizeAndTimeBasedAppender,
    TimedRotatingFileAppender,
)
from log4p2.appender import parse_size


def record(message="line", level=Level.INFO):
    return LogRecord(name="app", level=level, message=message)


def test_parse_size_units():
    assert parse_size(1024) == 1024
    assert parse_size("1024") == 1024
    assert parse_size("1KB") == 1024
    assert parse_size("1 kb") == 1024
    assert parse_size("2MB") == 2 * 1024**2
    assert parse_size("1G") == 1024**3
    assert parse_size("1TB") == 1024**4
    assert parse_size("1.5KB") == 1536


def test_parse_size_rejects_bad_values():
    with pytest.raises(ValueError):
        parse_size("nosize")
    with pytest.raises(ValueError):
        parse_size("10XB")


def test_rotating_accepts_size_string(tmp_path):
    app = RotatingFileAppender(str(tmp_path / "a.log"), maxBytes="1MB")
    assert app.maxBytes == 1024**2


def test_rotating_on_startup_rolls_existing(tmp_path):
    path = tmp_path / "app.log"
    RotatingFileAppender(
        str(path), maxBytes="1MB", backupCount=3, layout=PatternLayout("%m")
    ).doAppend(record("previous run"))

    app = RotatingFileAppender(
        str(path),
        maxBytes="1MB",
        backupCount=3,
        onStartup=True,
        layout=PatternLayout("%m"),
    )
    app.doAppend(record("new run"))
    app.stop()

    assert path.read_text() == "new run\n"
    assert (tmp_path / "app.log.1").read_text() == "previous run\n"


def test_rotating_without_on_startup_appends(tmp_path):
    path = tmp_path / "app.log"
    RotatingFileAppender(
        str(path), maxBytes="1MB", backupCount=3, layout=PatternLayout("%m")
    ).doAppend(record("previous run"))

    app = RotatingFileAppender(
        str(path), maxBytes="1MB", backupCount=3, layout=PatternLayout("%m")
    )
    app.doAppend(record("new run"))
    app.stop()

    assert path.read_text() == "previous run\nnew run\n"
    assert not (tmp_path / "app.log.1").exists()


def test_rotating_on_startup_rolls_only_once(tmp_path):
    path = tmp_path / "app.log"
    app = RotatingFileAppender(
        str(path),
        maxBytes="1MB",
        backupCount=5,
        onStartup=True,
        layout=PatternLayout("%m"),
    )
    app.doAppend(record("one"))
    app.doAppend(record("two"))
    app.stop()
    # First-ever start had no existing data, so no backup should exist.
    assert path.read_text() == "one\ntwo\n"
    assert not (tmp_path / "app.log.1").exists()


def test_timed_on_startup_rolls_existing(tmp_path):
    path = tmp_path / "app.log"
    TimedRotatingFileAppender(
        str(path), when="h", backupCount=3, layout=PatternLayout("%m")
    ).doAppend(record("previous"))

    app = TimedRotatingFileAppender(
        str(path),
        when="h",
        backupCount=3,
        onStartup=True,
        layout=PatternLayout("%m"),
    )
    app.doAppend(record("current"))
    app.stop()

    assert path.read_text() == "current\n"
    assert glob.glob(str(path) + ".2*")


def test_size_and_time_on_startup_rolls_existing(tmp_path):
    path = tmp_path / "app.log"
    SizeAndTimeBasedAppender(
        str(path), maxBytes="1KB", when="d", backupCount=3, layout=PatternLayout("%m")
    ).doAppend(record("previous"))

    app = SizeAndTimeBasedAppender(
        str(path),
        maxBytes="1KB",
        when="d",
        backupCount=3,
        onStartup=True,
        layout=PatternLayout("%m"),
    )
    app.doAppend(record("current"))
    app.stop()

    assert path.read_text() == "current\n"
    assert glob.glob(str(path) + ".2*")


def test_size_and_time_accepts_size_string(tmp_path):
    app = SizeAndTimeBasedAppender(str(tmp_path / "a.log"), maxBytes="2MB")
    assert app.maxBytes == 2 * 1024**2
