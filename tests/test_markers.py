import io

import pytest

from log4p import (
    ConsoleAppender,
    FilterReply,
    Level,
    LogRecord,
    MarkerFilter,
    PatternLayout,
    getLogger,
    getMarker,
    getMarkerNames,
)
from log4p.logger import getLoggerManager


@pytest.fixture(autouse=True)
def _isolate():
    getLoggerManager().clear()
    getLoggerManager().warn_on_no_appenders = False
    yield
    getLoggerManager().clear()


def test_marker_registry_returns_same_instance():
    assert getMarker("SQL") is getMarker("SQL")
    assert "SQL" in getMarkerNames()


def test_marker_requires_name():
    from log4p import Marker

    with pytest.raises(ValueError):
        Marker("")


def test_marker_hierarchy_isinstanceof():
    audit = getMarker("AUDIT")
    security = getMarker("SECURITY", parents=[audit])
    assert security.isInstanceOf(audit)
    assert security.isInstanceOf(security)
    assert not audit.isInstanceOf(security)


def test_marker_equality_and_str():
    assert getMarker("X") == getMarker("X")
    assert str(getMarker("X")) == "X"
    assert hash(getMarker("X")) == hash(getMarker("X"))


def _record(marker=None):
    return LogRecord(name="x", level=Level.INFO, message="m", marker=marker)


def test_marker_filter_accepts_matching_record():
    filt = MarkerFilter("SQL")
    assert filt.decide(_record(getMarker("SQL"))) == FilterReply.NEUTRAL
    assert filt.decide(_record()) == FilterReply.DENY


def test_marker_filter_deny_mode():
    filt = MarkerFilter("SQL", on_match="deny")
    assert filt.decide(_record(getMarker("SQL"))) == FilterReply.DENY
    assert filt.decide(_record()) == FilterReply.NEUTRAL


def test_marker_filter_matches_parent():
    parent = getMarker("AUDIT")
    child = getMarker("LOGIN", parents=[parent])
    assert MarkerFilter(parent).decide(_record(child)) == FilterReply.NEUTRAL


def test_marker_filter_accepts_name_string():
    filt = MarkerFilter("AUDIT")
    assert filt.marker is getMarker("AUDIT")


def test_marker_kwarg_flows_to_record():
    buf = io.StringIO()
    logger = getLogger("m")
    logger.setLevel(Level.DEBUG)
    logger.addAppender(ConsoleAppender(PatternLayout("%marker|%m"), stream=buf))
    logger.info("hi", marker=getMarker("SQL"))
    assert buf.getvalue().strip() == "SQL|hi"


def test_pattern_marker_empty_when_absent():
    assert PatternLayout("%marker").format(_record()).replace("\n", "") == ""


def test_marker_filter_rejects_bad_mode():
    with pytest.raises(ValueError):
        MarkerFilter("X", on_match="maybe")
