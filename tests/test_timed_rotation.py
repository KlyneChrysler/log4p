import glob
import gzip
import time

import pytest

from log4p import Level, LogRecord, PatternLayout, TimedRotatingFileAppender


def record(message="line", level=Level.INFO):
    return LogRecord(name="app", level=level, message=message)


def test_invalid_when_value(tmp_path):
    with pytest.raises(ValueError):
        TimedRotatingFileAppender(str(tmp_path / "x.log"), when="nope")


def test_invalid_weekly_value(tmp_path):
    with pytest.raises(ValueError):
        TimedRotatingFileAppender(str(tmp_path / "x.log"), when="W9")


def test_rotation_creates_timestamped_file(tmp_path):
    path = tmp_path / "app.log"
    app = TimedRotatingFileAppender(
        str(path), when="S", interval=1, layout=PatternLayout("%m")
    )
    app.doAppend(record("before"))
    # Force the schedule into the past to guarantee a rollover on next write.
    app.rollover_at = time.time() - 1
    expected_suffix = app._suffix_for(app.rollover_at - 1)
    app.doAppend(record("after"))
    app.stop()

    assert path.exists()
    assert path.read_text() == "after\n"
    rotated = tmp_path / f"app.log.{expected_suffix}"
    assert rotated.exists()
    assert rotated.read_text() == "before\n"


def test_rotation_compresses(tmp_path):
    path = tmp_path / "app.log"
    app = TimedRotatingFileAppender(
        str(path), when="S", compress=True, layout=PatternLayout("%m")
    )
    app.doAppend(record("compressed-line"))
    app.rollover_at = time.time() - 1
    suffix = app._suffix_for(app.rollover_at - 1)
    app.doAppend(record("new-line"))
    app.stop()

    gz_path = tmp_path / f"app.log.{suffix}.gz"
    assert gz_path.exists()
    with gzip.open(gz_path, "rt") as handle:
        assert handle.read() == "compressed-line\n"


def test_backups_expire(tmp_path):
    path = tmp_path / "app.log"
    app = TimedRotatingFileAppender(
        str(path), when="S", backupCount=2, layout=PatternLayout("%m")
    )
    base = int(time.time()) - 100
    app.doAppend(record("line-0"))
    for i in range(1, 5):
        app.rollover_at = base + i * 2  # distinct past seconds -> distinct suffixes
        app.doAppend(record(f"line-{i}"))
    app.stop()

    backups = sorted(glob.glob(str(tmp_path / "app.log.*")))
    assert len(backups) == 2


def test_rollover_then_writes_new_file(tmp_path):
    path = tmp_path / "app.log"
    app = TimedRotatingFileAppender(str(path), when="S", layout=PatternLayout("%m"))
    app.doAppend(record("one"))
    app.rollover_at = time.time() - 1
    app.doAppend(record("two"))
    app.doAppend(record("three"))
    app.stop()
    assert path.read_text() == "two\nthree\n"
