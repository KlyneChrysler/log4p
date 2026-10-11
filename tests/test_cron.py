from datetime import datetime

import pytest

from log4p2 import CronExpression


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def test_every_minute_five_field():
    cron = CronExpression("* * * * *")
    assert cron.has_seconds is False
    assert cron.matches(at("2026-01-01 09:30:00"))
    assert cron.matches(at("2026-12-31 23:59:00"))


def test_five_field_only_matches_second_zero():
    cron = CronExpression("* * * * *")
    assert cron.matches(at("2026-01-01 09:30:00"))
    assert not cron.matches(at("2026-01-01 09:30:30"))


def test_specific_minute_and_hour():
    cron = CronExpression("30 9 * * *")
    assert cron.matches(at("2026-01-01 09:30:00"))
    assert not cron.matches(at("2026-01-01 09:31:00"))
    assert not cron.matches(at("2026-01-01 10:30:00"))


def test_six_field_with_seconds():
    cron = CronExpression("0 30 9 * * *")
    assert cron.has_seconds is True
    assert cron.matches(at("2026-01-01 09:30:00"))
    assert not cron.matches(at("2026-01-01 09:30:01"))


def test_ranges_lists_and_steps():
    cron = CronExpression("0 1-5 * * *")
    for hour in range(1, 6):
        assert cron.matches(at(f"2026-01-01 0{hour}:00:00"))
    assert not cron.matches(at("2026-01-01 06:00:00"))

    every_15 = CronExpression("*/15 * * * *")
    for minute in (0, 15, 30, 45):
        assert every_15.matches(at(f"2026-01-01 09:{minute:02d}:00"))
    assert not every_15.matches(at("2026-01-01 09:07:00"))


def test_names_for_month_and_dow():
    cron = CronExpression("0 0 * JAN MON")
    assert cron.matches(at("2026-01-05 00:00:00"))
    assert not cron.matches(at("2026-02-02 00:00:00"))


def test_dow_sunday_as_zero_or_seven():
    zero = CronExpression("0 0 * * 0")
    seven = CronExpression("0 0 * * 7")
    sunday = at("2026-01-04 00:00:00")
    assert sunday.strftime("%A") == "Sunday"
    assert zero.matches(sunday)
    assert seven.matches(sunday)


def test_dom_and_dow_restricted_use_or():
    cron = CronExpression("0 0 1 * MON")
    assert cron.matches(at("2026-01-01 00:00:00"))
    assert cron.matches(at("2026-01-05 00:00:00"))
    assert not cron.matches(at("2026-01-06 00:00:00"))


def test_next_after_returns_next_matching_time():
    cron = CronExpression("0 0 * * *")
    start = at("2026-01-01 09:30:00").timestamp()
    assert cron.next_after(start) == at("2026-01-02 00:00:00").timestamp()


def test_next_after_within_same_day():
    cron = CronExpression("*/15 * * * *")
    start = at("2026-01-01 09:07:00").timestamp()
    assert cron.next_after(start) == at("2026-01-01 09:15:00").timestamp()


def test_next_after_day_of_month():
    cron = CronExpression("0 0 1 * *")
    start = at("2026-01-15 00:00:00").timestamp()
    assert cron.next_after(start) == at("2026-02-01 00:00:00").timestamp()


def test_invalid_expressions():
    with pytest.raises(ValueError):
        CronExpression("* * *")
    with pytest.raises(ValueError):
        CronExpression("60 * * * *")
    with pytest.raises(ValueError):
        CronExpression("* * * * FOO")
    with pytest.raises(ValueError):
        CronExpression("*/0 * * * *")
    with pytest.raises(ValueError):
        CronExpression("10-5 * * * *")
