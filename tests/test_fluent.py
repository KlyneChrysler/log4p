from log4p2 import (
    ConsoleAppender,
    Level,
    LogBuilder,
    PatternLayout,
    getLogger,
)
from log4p2.logger import getLoggerManager


def _configure(pattern="%p %m"):
    getLoggerManager().clear()
    root = getLogger()
    root.setLevel(Level.DEBUG)
    root.removeAllAppenders()
    root.addAppender(ConsoleAppender(PatternLayout(pattern)))
    return root


def test_at_level_returns_builder():
    root = _configure()
    builder = root.atInfo()
    assert isinstance(builder, LogBuilder)
    assert builder.isEnabled()
    getLoggerManager().clear()


def test_fluent_log_emits(capsys):
    root = _configure("%p %m")
    root.atInfo().log("hello %s", "world")
    assert capsys.readouterr().out == "INFO hello world\n"
    getLoggerManager().clear()


def test_fluent_disabled_is_lazy(capsys):
    root = _configure()
    root.setLevel(Level.WARN)
    root.atDebug().log("should not appear")
    assert capsys.readouterr().out == ""
    getLoggerManager().clear()


def test_fluent_with_marker(capsys):
    from log4p2 import getMarker

    root = _configure("%marker %m")
    root.atInfo().withMarker(getMarker("AUDIT")).log("login")
    assert capsys.readouterr().out == "AUDIT login\n"
    getLoggerManager().clear()


def test_fluent_with_throwable(capsys):
    root = _configure("%p %m%n")
    try:
        raise ValueError("boom")
    except ValueError as exc:
        root.atError().withThrowable(exc).log("failed")
    out = capsys.readouterr().out
    assert "ERROR failed" in out
    assert "ValueError: boom" in out
    getLoggerManager().clear()


def test_fluent_with_context(capsys):
    root = _configure("%X{req} %m")
    root.atInfo().withContext("req", "R-9").log("hi")
    assert capsys.readouterr().out == "R-9 hi\n"
    getLoggerManager().clear()


def test_fluent_with_stack_info(capsys):
    root = _configure("%p %m%n%stack")
    root.atInfo().withStackInfo().log("with stack")
    out = capsys.readouterr().out
    assert "with stack" in out
    assert "Stack (most recent call last)" in out
    getLoggerManager().clear()


def test_fluent_attributes_caller(capsys):
    root = _configure("%M %m")
    root.atInfo().log("where")
    assert capsys.readouterr().out == "test_fluent_attributes_caller where\n"
    getLoggerManager().clear()


def test_at_level_accepts_string_and_int():
    root = _configure()
    assert root.atLevel("info").level is Level.INFO
    assert root.atLevel(20).level is Level.INFO
    getLoggerManager().clear()
