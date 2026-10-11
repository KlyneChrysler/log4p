import io

import pytest

from log4p2 import (
    ConsoleAppender,
    Level,
    LogRecord,
    PatternLayout,
    RFC5424Layout,
    StructuredDataMessage,
    SyslogLayout,
    getLogger,
)
from log4p2.logger import getLoggerManager


@pytest.fixture(autouse=True)
def _isolate():
    getLoggerManager().clear()
    getLoggerManager().warn_on_no_appenders = False
    yield
    getLoggerManager().clear()


def record(message="disk full", level=Level.ERROR, name="app.db"):
    return LogRecord(name=name, level=level, message=message)


def test_syslog_layout_rfc3164():
    line = SyslogLayout(facility="LOCAL0").format(record())
    # LOCAL0(16)*8 + ERROR(3) = 131
    assert line.startswith("<131>")
    assert line.endswith("app.db: disk full")
    assert " " in line


def test_syslog_layout_custom_tag_and_pattern():
    layout = SyslogLayout(facility="USER", tag="svc", pattern="%-5p %m")
    line = layout.format(record("boom", level=Level.WARN))
    assert line.endswith("svc: WARN  boom")


def test_syslog_layout_appends_exception():
    try:
        raise ValueError("nope")
    except ValueError:
        import sys

        exc = sys.exc_info()
    rec = LogRecord(name="app", level=Level.ERROR, message="failed", exc_info=exc)
    line = SyslogLayout().format(rec)
    assert "ValueError: nope" in line


def test_syslog_layout_severity_by_level():
    for level, pri in [
        (Level.FATAL, 2),
        (Level.ERROR, 3),
        (Level.WARN, 4),
        (Level.INFO, 6),
        (Level.DEBUG, 7),
    ]:
        line = SyslogLayout(facility="USER").format(record(level=level))
        assert line.startswith(f"<{1 * 8 + pri}>")


def test_rfc5424_layout_basic():
    layout = RFC5424Layout(facility="LOCAL0", appName="websvc", msgId="ID47")
    line = layout.format(record())
    assert line.startswith("<131>1 ")
    assert " websvc " in line
    assert "ID47 - disk full" in line
    assert "T" in line and "." in line


def test_rfc5424_structured_data():
    message = StructuredDataMessage({"user": "alice"}, type="audit")
    rec = LogRecord(name="app", level=Level.INFO, message=message)
    line = RFC5424Layout().format(rec)
    assert "audit" in line
    assert 'user="alice"' in line


def test_rfc5424_no_structured_data_uses_nil():
    line = RFC5424Layout().format(record("hi"))
    assert " - hi" in line
    assert line.count("-") >= 2


def test_rfc5424_defaults_use_process_and_logger():
    rec = record("hi", level=Level.INFO)
    line = RFC5424Layout().format(rec)
    assert rec.name in line
    assert str(rec.process) in line


def test_syslog_layout_end_to_end_through_appender():
    buf = io.StringIO()
    appender = ConsoleAppender(SyslogLayout(facility="LOCAL0"), stream=buf)
    logger = getLogger("syslog.e2e")
    logger.setLevel("INFO")
    logger.addAppender(appender)
    logger.error("disk full")
    out = buf.getvalue()
    assert out.startswith("<131>")
    assert out.rstrip("\n").endswith("syslog.e2e: disk full")


def test_rfc5424_layout_end_to_end_roundtrip_exception():
    buf = io.StringIO()
    appender = ConsoleAppender(RFC5424Layout(appName="svc"), stream=buf)
    logger = getLogger("syslog.exc")
    logger.setLevel("INFO")
    logger.addAppender(appender)
    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        logger.exception("failed")
    assert "RuntimeError: kaboom" in buf.getvalue()


def test_config_builds_syslog_layouts():
    from log4p2 import config as log4p_config

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "RFC5424Layout", "appName": "svc"},
                }
            },
        }
    )
    logger = getLogger("cfg")
    logger.info("hello")
    assert buf.getvalue().startswith("<")


def test_invalid_facility_raises():
    with pytest.raises(ValueError):
        SyslogLayout(facility="NOPE")
    with pytest.raises(ValueError):
        RFC5424Layout(facility="NOPE")


def test_pattern_layout_still_independent():
    assert PatternLayout("%m").format(record("x")) == "x"
