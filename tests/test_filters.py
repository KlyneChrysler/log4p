from log4p import (
    AndFilter,
    FilterReply,
    Level,
    LevelRangeFilter,
    LogRecord,
    NotFilter,
    OrFilter,
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


class _Always:
    def __init__(self, reply):
        self.reply = reply

    def decide(self, record):
        return self.reply


def test_and_filter_all_accept():
    filt = AndFilter(_Always(FilterReply.ACCEPT), _Always(FilterReply.ACCEPT))
    assert filt.decide(record()) == FilterReply.ACCEPT


def test_and_filter_any_deny_wins():
    filt = AndFilter(_Always(FilterReply.ACCEPT), _Always(FilterReply.DENY))
    assert filt.decide(record()) == FilterReply.DENY


def test_and_filter_neutral_when_mixed():
    filt = AndFilter(_Always(FilterReply.ACCEPT), _Always(FilterReply.NEUTRAL))
    assert filt.decide(record()) == FilterReply.NEUTRAL


def test_and_filter_empty_is_neutral():
    assert AndFilter().decide(record()) == FilterReply.NEUTRAL


def test_or_filter_any_accept_wins():
    filt = OrFilter(_Always(FilterReply.DENY), _Always(FilterReply.ACCEPT))
    assert filt.decide(record()) == FilterReply.ACCEPT


def test_or_filter_all_deny():
    filt = OrFilter(_Always(FilterReply.DENY), _Always(FilterReply.DENY))
    assert filt.decide(record()) == FilterReply.DENY


def test_or_filter_neutral_when_mixed():
    filt = OrFilter(_Always(FilterReply.DENY), _Always(FilterReply.NEUTRAL))
    assert filt.decide(record()) == FilterReply.NEUTRAL


def test_composite_accepts_flat_list():
    filt = AndFilter([_Always(FilterReply.ACCEPT), _Always(FilterReply.ACCEPT)])
    assert filt.decide(record()) == FilterReply.ACCEPT


def test_not_filter_inverts():
    assert NotFilter(_Always(FilterReply.ACCEPT)).decide(record()) == FilterReply.DENY
    assert NotFilter(_Always(FilterReply.DENY)).decide(record()) == FilterReply.ACCEPT
    assert NotFilter(_Always(FilterReply.NEUTRAL)).decide(record()) == FilterReply.NEUTRAL


def test_composite_with_real_filters():
    filt = AndFilter(ThresholdFilter("WARN"), RegexFilter(r"boom", field="message"))
    assert filt.decide(record(Level.ERROR, "boom")) == FilterReply.NEUTRAL
    assert filt.decide(record(Level.INFO, "boom")) == FilterReply.DENY
    assert filt.decide(record(Level.ERROR, "fine")) == FilterReply.DENY
