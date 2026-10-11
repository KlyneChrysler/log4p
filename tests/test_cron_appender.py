import time

from log4p import CronRollingFileAppender, Level, LogRecord, PatternLayout


def record(message="line", level=Level.INFO):
    return LogRecord(name="app", level=level, message=message)


def test_cron_rollover_creates_timestamped_file(tmp_path):
    path = tmp_path / "app.log"
    app = CronRollingFileAppender(
        str(path), cron="*/1 * * * *", layout=PatternLayout("%m")
    )
    app.doAppend(record("before"))
    app.rollover_at = time.time() - 1
    expected_suffix = app._suffix_for(app.rollover_at - 1)
    app.doAppend(record("after"))
    app.stop()

    assert path.read_text() == "after\n"
    rotated = tmp_path / f"app.log.{expected_suffix}"
    assert rotated.exists()
    assert rotated.read_text() == "before\n"


def test_cron_rollover_custom_suffix(tmp_path):
    path = tmp_path / "app.log"
    app = CronRollingFileAppender(
        str(path),
        cron="0 0 * * *",
        suffix="%Y%m%d",
        layout=PatternLayout("%m"),
    )
    assert app.suffix_format == "%Y%m%d"
    app.doAppend(record("x"))
    app.stop()
    assert path.read_text() == "x\n"


def test_cron_appender_invalid_expression(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        CronRollingFileAppender(str(tmp_path / "app.log"), cron="bogus")
