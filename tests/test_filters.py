from log4p import (
    FilterReply,
    Level,
    LevelRangeFilter,
    LogRecord,
    RegexFilter,
    ThresholdFilter,
)


def record(level=Level.INFO, message="hello", name="app.db"):
    return LogRecord(name=name, level=level, message=message)


def test_threshold_filter():
    filt = ThresholdFilter("WARN")
    assert filt.decide(record(Level.DEBUG)) == FilterReply.DENY
    assert filt.decide(record(Level.WARN)) == FilterReply.NEUTRAL
    assert filt.decide(record(Level.ERROR)) == FilterReply.NEUTRAL


def test_level_range_filter():
    filt = LevelRangeFilter("INFO", "WARN")
    assert filt.decide(record(Level.DEBUG)) == FilterReply.DENY
    assert filt.decide(record(Level.INFO)) == FilterReply.NEUTRAL
    assert filt.decide(record(Level.WARN)) == FilterReply.NEUTRAL
    assert filt.decide(record(Level.ERROR)) == FilterReply.DENY


def test_regex_filter_default_accepts_match():
    filt = RegexFilter(r"db-.*")
    assert filt.decide(record(Level.INFO, "db-42 up")) == FilterReply.NEUTRAL
    assert filt.decide(record(Level.INFO, "cache up")) == FilterReply.DENY


def test_regex_filter_deny_mode():
    filt = RegexFilter(r"secret", on_match="deny")
    assert filt.decide(record(Level.INFO, "secret token")) == FilterReply.DENY
    assert filt.decide(record(Level.INFO, "public")) == FilterReply.NEUTRAL


def test_regex_filter_on_other_field():
    filt = RegexFilter(r"^app\.db", field="name")
    assert filt.decide(record(name="app.db.pool")) == FilterReply.NEUTRAL
    assert filt.decide(record(name="app.cache")) == FilterReply.DENY


def test_regex_filter_invalid_mode():
    import pytest

    with pytest.raises(ValueError):
        RegexFilter(r"x", on_match="maybe")
