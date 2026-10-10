import io

import pytest

from log4p import ConsoleAppender, Level, PatternLayout
from log4p.logger import LoggerManager, getLoggerManager


@pytest.fixture
def manager():
    return LoggerManager()


@pytest.fixture(autouse=True)
def _isolate_default_manager():
    getLoggerManager().clear()
    getLoggerManager().warn_on_no_appenders = False
    yield
    getLoggerManager().clear()


def test_getlogger_returns_same_instance(manager):
    assert manager.getLogger("app.db") is manager.getLogger("app.db")


def test_getlogger_normalises_trailing_dot(manager):
    assert manager.getLogger("app.db.") is manager.getLogger("app.db")


def test_parent_resolution(manager):
    db = manager.getLogger("app.db.pool")
    appdb = manager.getLogger("app.db")
    app = manager.getLogger("app")
    assert db.parent is appdb
    assert appdb.parent is app
    assert app.parent is manager.root


def test_reparenting_when_intermediate_created_later(manager):
    leaf = manager.getLogger("a.b.c")
    assert leaf.parent is manager.root
    middle = manager.getLogger("a.b")
    assert leaf.parent is middle
    assert middle.parent is manager.root


def test_effective_level_inheritance(manager):
    app = manager.getLogger("app")
    db = manager.getLogger("app.db")
    app.setLevel("DEBUG")
    assert db.getLevel() is None
    assert db.getEffectiveLevel() is Level.DEBUG
    db.setLevel("ERROR")
    assert db.getEffectiveLevel() is Level.ERROR


def test_root_default_level(manager):
    assert manager.root.getEffectiveLevel() is Level.WARN


def test_is_enabled_for(manager):
    logger = manager.getLogger("x")
    logger.setLevel("INFO")
    assert logger.isEnabledFor("INFO")
    assert logger.isEnabledFor(Level.ERROR)
    assert not logger.isEnabledFor("DEBUG")


def test_additivity_propagates_to_parent(manager):
    buf = io.StringIO()
    root = manager.root
    root.addAppender(ConsoleAppender(PatternLayout("%c:%m"), stream=buf))
    root.setLevel("DEBUG")
    child = manager.getLogger("app.db")
    child.setLevel("DEBUG")
    child.info("hi")
    assert buf.getvalue() == "app.db:hi\n"


def test_additivity_false_stops_propagation(manager):
    buf = io.StringIO()
    manager.root.addAppender(ConsoleAppender(PatternLayout("root:%m"), stream=buf))
    manager.root.setLevel("DEBUG")
    child = manager.getLogger("app")
    child.setAdditivity(False)
    child.setLevel("DEBUG")
    own = io.StringIO()
    child.addAppender(ConsoleAppender(PatternLayout("child:%m"), stream=own))
    child.info("hi")
    assert own.getvalue() == "child:hi\n"
    assert buf.getvalue() == ""


def test_appender_removal(manager):
    logger = manager.getLogger("x")
    appender = ConsoleAppender(stream=io.StringIO())
    logger.addAppender(appender)
    assert appender in logger.getAppenders()
    logger.removeAppender(appender)
    assert appender not in logger.getAppenders()


def test_message_formatting_at_call_site(manager):
    buf = io.StringIO()
    logger = manager.getLogger("x")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(ConsoleAppender(PatternLayout("%m"), stream=buf))
    logger.info("user %s logged in", "klyne")
    assert buf.getvalue() == "user klyne logged in\n"


def test_debug_suppressed_below_level(manager):
    buf = io.StringIO()
    logger = manager.getLogger("x")
    logger.setAdditivity(False)
    logger.setLevel("INFO")
    logger.addAppender(ConsoleAppender(PatternLayout("%m"), stream=buf))
    logger.debug("nope")
    logger.info("yes")
    assert buf.getvalue() == "yes\n"


def test_exception_includes_traceback(manager):
    buf = io.StringIO()
    logger = manager.getLogger("x")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(ConsoleAppender(PatternLayout("%m"), stream=buf))
    try:
        raise ValueError("kaboom")
    except ValueError:
        logger.exception("failed")
    out = buf.getvalue()
    assert "failed" in out
    assert "ValueError: kaboom" in out
    assert "Traceback" in out


def test_extra_context(manager):
    buf = io.StringIO()
    logger = manager.getLogger("x")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(ConsoleAppender(PatternLayout("%X{user}"), stream=buf))
    logger.info("hi", extra={"user": "klyne"})
    assert buf.getvalue() == "klyne\n"


def test_log_with_explicit_level(manager):
    buf = io.StringIO()
    logger = manager.getLogger("x")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(ConsoleAppender(PatternLayout("%p:%m"), stream=buf))
    logger.log("ERROR", "explicit")
    assert buf.getvalue() == "ERROR:explicit\n"


def test_getchild(manager):
    parent = manager.getLogger("app")
    child = parent.getChild("db")
    assert child.name == "app.db"
    assert child.parent is parent


def test_warn_no_appenders(manager, capsys):
    manager.warn_on_no_appenders = True
    logger = manager.getLogger("lonely")
    logger.setLevel("DEBUG")
    logger.info("hi")
    err = capsys.readouterr().err
    assert "no appenders could be found" in err


def test_shutdown_stops_appenders(manager):
    logger = manager.getLogger("x")
    appender = ConsoleAppender(stream=io.StringIO())
    logger.addAppender(appender)
    manager.shutdown()
    assert appender.isStarted() is False


def test_manager_clear_keeps_logger_identity(manager):
    logger = manager.getLogger("x")
    logger.setLevel("DEBUG")
    manager.clear()
    assert manager.getLogger("x") is logger
    assert logger.getLevel() is None


def test_caller_attribution_skips_log4p_frames(manager):
    captured = {}

    class Capture(ConsoleAppender):
        def append(self, record):
            captured["pathname"] = record.pathname
            captured["funcName"] = record.funcName
            captured["lineno"] = record.lineno

    logger = manager.getLogger("caller")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(Capture(PatternLayout("%m")))

    def helper():
        logger.info("from helper")  # line marker

    expected_line = helper.__code__.co_firstlineno + 1
    helper()

    assert captured["funcName"] == "helper"
    assert captured["pathname"].endswith("test_logger.py")
    assert captured["lineno"] == expected_line


def test_stack_info_populates_record(manager):
    captured = {}

    class Capture(ConsoleAppender):
        def append(self, record):
            captured["stack"] = record.stack_info

    logger = manager.getLogger("stack")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(Capture(PatternLayout("%m")))

    logger.info("with stack", stack_info=True)
    assert captured["stack"] is not None
    assert "Stack (most recent call last):" in captured["stack"]


def test_stack_info_absent_by_default(manager):
    captured = {}

    class Capture(ConsoleAppender):
        def append(self, record):
            captured["stack"] = record.stack_info

    logger = manager.getLogger("nostack")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(Capture(PatternLayout("%m")))
    logger.info("no stack")
    assert captured["stack"] is None

