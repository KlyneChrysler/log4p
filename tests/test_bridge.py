import io
import logging

import pytest

from log4p import (
    ConsoleAppender,
    Level,
    PatternLayout,
    StdlibLoggingAppender,
    StdlibToLog4pHandler,
    capture_stdlib,
    getLogger,
)
from log4p.logger import LoggerManager
from log4p.context import MDC


@pytest.fixture
def manager():
    return LoggerManager()


def test_stdlib_handler_forwards_to_log4p(manager):
    captured = []

    class Capture(ConsoleAppender):
        def append(self, record):
            captured.append(record)

    target = manager.getLogger("inbound")
    target.setAdditivity(False)
    target.setLevel("DEBUG")
    target.addAppender(Capture(PatternLayout("%m")))

    std = logging.getLogger("legacy.module")
    std.handlers = []
    std.setLevel(logging.DEBUG)
    std.propagate = False
    std.addHandler(StdlibToLog4pHandler(target))

    std.info("hello from stdlib")
    std.warning("watch out")

    assert [r.getMessage() for r in captured] == ["hello from stdlib", "watch out"]
    assert captured[0].level is Level.INFO
    assert captured[1].level is Level.WARN


def test_stdlib_handler_preserves_caller(manager):
    captured = []

    class Capture(ConsoleAppender):
        def append(self, record):
            captured.append(record)

    target = manager.getLogger("inbound")
    target.setAdditivity(False)
    target.setLevel("DEBUG")
    target.addAppender(Capture(PatternLayout("%m")))

    std = logging.getLogger("legacy.caller")
    std.handlers = []
    std.setLevel(logging.DEBUG)
    std.propagate = False
    std.addHandler(StdlibToLog4pHandler(target))

    std.error("boom")  # this line number is captured

    assert captured[0].filename == "test_bridge.py"
    assert captured[0].funcName == "test_stdlib_handler_preserves_caller"


def test_stdlib_handler_respects_level(manager):
    captured = []

    class Capture(ConsoleAppender):
        def append(self, record):
            captured.append(record)

    target = manager.getLogger("inbound")
    target.setAdditivity(False)
    target.setLevel("ERROR")
    target.addAppender(Capture(PatternLayout("%m")))

    std = logging.getLogger("legacy.level")
    std.handlers = []
    std.setLevel(logging.DEBUG)
    std.propagate = False
    std.addHandler(StdlibToLog4pHandler(target))

    std.info("dropped")
    std.error("kept")

    assert [r.getMessage() for r in captured] == ["kept"]


def test_stdlib_handler_extra_data(manager):
    captured = []

    class Capture(ConsoleAppender):
        def append(self, record):
            captured.append(record)

    target = manager.getLogger("inbound")
    target.setAdditivity(False)
    target.setLevel("DEBUG")
    target.addAppender(Capture(PatternLayout("%m")))

    std = logging.getLogger("legacy.extra")
    std.handlers = []
    std.setLevel(logging.DEBUG)
    std.propagate = False
    std.addHandler(StdlibToLog4pHandler(target))

    std.info("with data", extra={"tenant": "acme"})
    assert captured[0].context.get("tenant") == "acme"


def test_log4p_appender_forwards_to_stdlib(manager):
    buf = io.StringIO()
    std = logging.getLogger("outbound")
    std.handlers = []
    std.propagate = False
    std.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
    std.addHandler(handler)

    logger = manager.getLogger("app")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(StdlibLoggingAppender(std))

    logger.info("to stdlib")
    logger.error("also to stdlib")
    out = buf.getvalue()
    assert "INFO:to stdlib" in out
    assert "ERROR:also to stdlib" in out


def test_capture_stdlib_installs_on_root():
    # Use the default manager (capture_stdlib wires into it).
    from log4p.logger import getLoggerManager

    getLoggerManager().clear()
    getLoggerManager().warn_on_no_appenders = False
    try:
        buf = io.StringIO()
        target = getLogger("captured")
        target.setAdditivity(False)
        target.setLevel("DEBUG")
        target.addAppender(ConsoleAppender(PatternLayout("%m"), stream=buf))

        handler = capture_stdlib("WARNING", target)
        root = logging.getLogger()
        assert handler in root.handlers
        try:
            logging.getLogger("library.x").warning("routed")
            logging.getLogger("library.x").info("too low")
        finally:
            root.removeHandler(handler)

        assert "routed" in buf.getvalue()
        assert "too low" not in buf.getvalue()
    finally:
        getLoggerManager().clear()


def test_mdc_flows_through_stdlib_handler(manager):
    captured = []

    class Capture(ConsoleAppender):
        def append(self, record):
            captured.append(record)

    target = manager.getLogger("inbound")
    target.setAdditivity(False)
    target.setLevel("DEBUG")
    target.addAppender(Capture(PatternLayout("%X{req}")))

    std = logging.getLogger("legacy.mdc")
    std.handlers = []
    std.setLevel(logging.DEBUG)
    std.propagate = False
    std.addHandler(StdlibToLog4pHandler(target))

    MDC.put("req", "r-9")
    std.info("with mdc")
    MDC.clear()
    assert captured[0].context.get("req") == "r-9"
