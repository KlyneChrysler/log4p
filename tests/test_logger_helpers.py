from log4p import Level, LogRecord, NullAppender, PatternLayout, getLogger
from log4p.logger import getLoggerManager


def record(message="hello"):
    rec = LogRecord(name="x", level=Level.INFO, message=message)
    rec.context["user"] = "bob"
    return rec


def test_mdc_default_value_used_when_absent():
    rec = record()
    assert PatternLayout("%X{missing:-n/a}").format(rec) == "n/a"
    assert PatternLayout("%X{user:-n/a}").format(rec) == "bob"


def test_map_converter_default_value():
    rec = record()
    assert PatternLayout("%K{missing:-none}").format(rec) == "none"
    assert PatternLayout("%K{user:-none}").format(rec) == "bob"


def test_null_appender_discards():
    app = NullAppender()
    app.doAppend(record())
    assert app.isStarted()
    app.stop()


def test_logger_level_helpers():
    getLoggerManager().clear()
    logger = getLogger("svc")
    logger.setLevel(Level.WARN)
    assert logger.isWarnEnabled()
    assert logger.isErrorEnabled()
    assert logger.isFatalEnabled()
    assert not logger.isInfoEnabled()
    assert not logger.isDebugEnabled()
    assert not logger.isTraceEnabled()
    getLoggerManager().clear()


def test_logger_level_helpers_follow_inheritance():
    getLoggerManager().clear()
    root = getLogger()
    root.setLevel(Level.DEBUG)
    child = getLogger("a.b")
    assert child.isDebugEnabled()
    assert child.isTraceEnabled() is False
    getLoggerManager().clear()


def test_logger_is_enabled_alias():
    getLoggerManager().clear()
    logger = getLogger("svc")
    logger.setLevel(Level.INFO)
    assert logger.isEnabled("INFO")
    assert logger.isEnabled(Level.ERROR)
    assert not logger.isEnabled("DEBUG")
    getLoggerManager().clear()


def test_logger_manager_exists():
    manager = getLoggerManager()
    manager.clear()
    assert not manager.exists("pkg.sub")
    getLogger("pkg.sub")
    assert manager.exists("pkg.sub")
    assert manager.exists("pkg.sub.")
    assert not manager.exists("pkg.other")
    manager.clear()
