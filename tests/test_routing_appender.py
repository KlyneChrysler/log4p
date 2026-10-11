import io

from log4p2 import (
    ConsoleAppender,
    Level,
    LogRecord,
    PatternLayout,
    RoutingAppender,
)
from log4p2.logger import getLoggerManager


def record(context=None):
    return LogRecord(name="app", level=Level.INFO, message="hi", context=context or {})


def _appender(stream):
    return ConsoleAppender(PatternLayout("%m"), stream=stream)


def test_routing_appender_routes_by_context():
    a, b = io.StringIO(), io.StringIO()
    routing = RoutingAppender({"a": _appender(a), "b": _appender(b)}, key="route")
    routing.doAppend(record({"route": "a"}))
    routing.doAppend(record({"route": "b"}))
    routing.stop()
    assert a.getvalue() == "hi\n"
    assert b.getvalue() == "hi\n"


def test_routing_appender_default_route():
    a, b = io.StringIO(), io.StringIO()
    routing = RoutingAppender(
        {"a": _appender(a), "fallback": _appender(b)}, key="route", default="fallback"
    )
    routing.doAppend(record({"route": "unknown"}))
    routing.stop()
    assert a.getvalue() == ""
    assert b.getvalue() == "hi\n"


def test_routing_appender_drops_unmatched_without_default():
    a = io.StringIO()
    routing = RoutingAppender({"a": _appender(a)})
    routing.doAppend(record())
    routing.stop()
    assert a.getvalue() == ""


def test_routing_appender_lifecycle():
    inner = _appender(io.StringIO())
    routing = RoutingAppender({"a": inner})
    routing.start()
    assert inner.isStarted()
    routing.stop()
    assert not inner.isStarted()


def test_routing_appender_get_route():
    a = _appender(io.StringIO())
    routing = RoutingAppender({"a": a}, default="a")
    assert routing.getRoute(record({"route": "a"})) is a
    assert routing.getRoute(record()) is a


def test_routing_appender_config_builds_children(monkeypatch):
    from log4p2 import config as log4p_config

    a, b = io.StringIO(), io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["router"]},
            "appenders": {
                "to_a": {
                    "class": "ConsoleAppender",
                    "stream": a,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                },
                "to_b": {
                    "class": "ConsoleAppender",
                    "stream": b,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                },
                "router": {
                    "class": "RoutingAppender",
                    "key": "route",
                    "routes": {"a": "to_a", "b": "to_b"},
                },
            },
        }
    )
    root = getLoggerManager().root
    router = root.getAppenders()[0]
    assert isinstance(router, RoutingAppender)
    from log4p2 import MDC

    MDC.put("route", "a")
    root.info("first")
    MDC.put("route", "b")
    root.info("second")
    router.stop()
    assert a.getvalue() == "first\n"
    assert b.getvalue() == "second\n"
