from log4p import (
    AndFilter,
    BurstFilter,
    FilterReply,
    Level,
    LevelRangeFilter,
    LogRecord,
    NoMarkerFilter,
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


def test_accept_and_deny_all_filters():
    from log4p import AcceptAllFilter, DenyAllFilter

    assert AcceptAllFilter().decide(record()) == FilterReply.ACCEPT
    assert DenyAllFilter().decide(record()) == FilterReply.DENY


def test_level_match_filter():
    from log4p import LevelMatchFilter

    filt = LevelMatchFilter("WARN")
    assert filt.decide(record(Level.WARN)) == FilterReply.NEUTRAL
    assert filt.decide(record(Level.ERROR)) == FilterReply.DENY
    assert filt.decide(record(Level.INFO)) == FilterReply.DENY


def test_on_match_and_on_mismatch_replies():
    filt = ThresholdFilter("WARN", onMatch="accept", onMismatch="neutral")
    assert filt.decide(record(Level.ERROR)) == FilterReply.ACCEPT
    assert filt.decide(record(Level.INFO)) == FilterReply.NEUTRAL


def test_regex_filter_explicit_replies():
    filt = RegexFilter(r"boom", onMatch="accept", onMismatch="neutral")
    assert filt.decide(record(message="boom")) == FilterReply.ACCEPT
    assert filt.decide(record(message="ok")) == FilterReply.NEUTRAL


def test_regex_filter_deny_variant_unchanged():
    filt = RegexFilter(r"health", on_match="deny")
    assert filt.decide(record(message="health ok")) == FilterReply.DENY
    assert filt.decide(record(message="real")) == FilterReply.NEUTRAL


def test_invalid_reply_rejected():
    import pytest

    with pytest.raises(ValueError):
        ThresholdFilter("WARN", onMatch="maybe")


def test_on_match_makes_composites_useful():
    # An ACCEPT-returning filter lets OrFilter short-circuit.
    filt = OrFilter(
        ThresholdFilter("ERROR", onMatch="accept"),
        RegexFilter(r"audit", onMatch="accept"),
    )
    assert filt.decide(record(Level.ERROR, "anything")) == FilterReply.ACCEPT
    assert filt.decide(record(Level.INFO, "audit trail")) == FilterReply.ACCEPT
    assert filt.decide(record(Level.INFO, "noise")) == FilterReply.DENY


def test_context_map_filter_and():
    from log4p import ContextMapFilter

    filt = ContextMapFilter({"user": "alice", "tenant": "acme"})
    rec = record()
    rec.context.update({"user": "alice", "tenant": "acme"})
    assert filt.decide(rec) == FilterReply.NEUTRAL
    rec.context["tenant"] = "other"
    assert filt.decide(rec) == FilterReply.DENY


def test_context_map_filter_or():
    from log4p import ContextMapFilter

    filt = ContextMapFilter({"user": "alice", "tenant": "acme"}, operator="or")
    rec = record()
    rec.context["user"] = "alice"
    assert filt.decide(rec) == FilterReply.NEUTRAL
    rec.context["user"] = "bob"
    assert filt.decide(rec) == FilterReply.DENY


def test_context_map_filter_empty_denies():
    from log4p import ContextMapFilter

    assert ContextMapFilter({}).decide(record()) == FilterReply.DENY


def test_context_map_filter_rejects_bad_operator():
    import pytest

    from log4p import ContextMapFilter

    with pytest.raises(ValueError):
        ContextMapFilter({"a": "b"}, operator="xor")


def test_dynamic_threshold_filter():
    from log4p import DynamicThresholdFilter

    filt = DynamicThresholdFilter("user", {"alice": "DEBUG"}, default_threshold="ERROR")
    rec = record(Level.DEBUG)
    rec.context["user"] = "alice"
    assert filt.decide(rec) == FilterReply.NEUTRAL
    rec.context["user"] = "bob"
    assert filt.decide(rec) == FilterReply.DENY
    assert filt.decide(record(Level.ERROR)) == FilterReply.NEUTRAL


def test_dynamic_threshold_filter_accept_variant():
    from log4p import DynamicThresholdFilter

    filt = DynamicThresholdFilter(
        "user", {"alice": "DEBUG"}, default_threshold="ERROR", onMatch="accept"
    )
    rec = record(Level.ERROR)
    assert filt.decide(rec) == FilterReply.ACCEPT


def test_no_marker_filter():
    rec = record()
    assert NoMarkerFilter().decide(rec) == FilterReply.NEUTRAL
    from log4p import Marker

    rec.marker = Marker("SQL")
    assert NoMarkerFilter().decide(rec) == FilterReply.DENY


def test_no_marker_filter_custom_replies():
    from log4p import Marker

    filt = NoMarkerFilter(onMatch="accept", onMismatch="neutral")
    assert filt.decide(record()) == FilterReply.ACCEPT
    rec = record()
    rec.marker = Marker("X")
    assert filt.decide(rec) == FilterReply.NEUTRAL


def test_burst_filter_allows_capacity_then_denies():
    filt = BurstFilter(rate=0.0, maxBurst=3)
    replies = [filt.decide(record()) for _ in range(5)]
    assert replies[:3] == [FilterReply.NEUTRAL] * 3
    assert replies[3:] == [FilterReply.DENY] * 2


def test_burst_filter_refills_over_time():
    from log4p.filter import BurstFilter as BF

    filt = BF(rate=1000.0, maxBurst=1)
    assert filt.decide(record()) == FilterReply.NEUTRAL
    assert filt.decide(record()) == FilterReply.DENY
    time = __import__("time")

    time.sleep(0.01)
    assert filt.decide(record()) == FilterReply.NEUTRAL


def test_burst_filter_level_bypasses_limit():
    filt = BurstFilter(rate=0.0, maxBurst=1, level="ERROR")
    assert filt.decide(record(Level.ERROR)) == FilterReply.NEUTRAL
    assert filt.decide(record(Level.INFO)) == FilterReply.NEUTRAL
    assert filt.decide(record(Level.INFO)) == FilterReply.DENY
