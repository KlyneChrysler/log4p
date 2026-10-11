"""Deterministic fuzz tests: malformed input must never crash the library.

These use a seeded ``random.Random`` so failures are reproducible; no external
property-testing dependency is required.
"""

import random
import string

from log4p2 import CronExpression, Level, LogRecord, PatternLayout
from log4p2.config import substitute_variables

PATTERN_CHARS = list("%{}:$mpcndltXF[]()-0123456789abcdefghij " + string.ascii_letters)


def _random_pattern(rng):
    return "".join(rng.choice(PATTERN_CHARS) for _ in range(rng.randint(0, 30)))


def _record():
    return LogRecord(
        name="app.fuzz",
        level=Level.INFO,
        message="hello %s",
        args=("world",),
        pathname="/tmp/a.py",
        lineno=7,
        funcName="f",
        context={"k": "v"},
        ndc="n1 n2",
    )


def test_pattern_layout_never_raises_on_random_patterns():
    rng = random.Random(1234)
    record = _record()
    for _ in range(3000):
        pattern = _random_pattern(rng)
        try:
            layout = PatternLayout(pattern)
        except ValueError:
            continue
        result = layout.format(record)
        assert isinstance(result, str)


def test_pattern_layout_stable_across_calls():
    rng = random.Random(4321)
    record = _record()
    for _ in range(500):
        pattern = _random_pattern(rng)
        layout = PatternLayout(pattern)
        assert layout.format(record) == layout.format(record)


def test_pattern_layout_balanced_wrappers():
    rng = random.Random(99)
    record = _record()
    inner = ["%m", "%-5p", "%logger", "%X{k}", "%n", "abc"]
    for _ in range(500):
        body = "".join(rng.choice(inner) for _ in range(rng.randint(0, 3)))
        pattern = rng.choice(
            [
                "%notEmpty{" + body + "}",
                "%maxLen{" + body + "}{" + str(rng.randint(1, 20)) + "}",
                "%replace{" + body + "}{a}{b}",
            ]
        )
        try:
            layout = PatternLayout(pattern)
        except ValueError:
            continue
        result = layout.format(record)
        assert isinstance(result, str)


CRON_TOKENS = [
    "*",
    "0",
    "5",
    "7",
    "60",
    "-1",
    "1-5",
    "*/2",
    "1,2,3",
    "JAN",
    "MON",
    "0-59/5",
    "a",
    "",
]


def test_cron_expression_fuzz_errors_are_value_errors():
    rng = random.Random(2024)
    for _ in range(2000):
        field_count = rng.choice([4, 5, 6, 7])
        expr = " ".join(rng.choice(CRON_TOKENS) for _ in range(field_count))
        try:
            cron = CronExpression(expr)
        except ValueError:
            continue
        assert isinstance(cron.matches(__import__("datetime").datetime(2026, 10, 12)), bool)


def test_cron_next_after_is_strictly_increasing():
    rng = random.Random(7)
    from datetime import datetime

    base = datetime(2026, 10, 12, 3, 15, 0).timestamp()
    horizon = 366 * 8 * 24 * 3600 + 1
    for _ in range(200):
        n = rng.randint(5, 6)
        while True:
            expr = " ".join(
                rng.choice(
                    ["*", "*/5", "*/15", "0", "30", "1-5", "MON-FRI", "0-23/2", "JAN"]
                )
                for _ in range(n)
            )
            try:
                cron = CronExpression(expr)
            except ValueError:
                continue
            break
        nxt = cron.next_after(base)
        assert nxt > base
        assert nxt - base <= horizon


SUBST_CHARS = list("${}:envsysABCDEF_ 0123456789")


def test_config_substitution_never_raises():
    rng = random.Random(555)
    for _ in range(3000):
        text = "".join(rng.choice(SUBST_CHARS) for _ in range(rng.randint(0, 25)))
        result = substitute_variables(text)
        assert isinstance(result, str)


def test_config_substitution_escaped_dollar_is_literal():
    rng = random.Random(556)
    for _ in range(500):
        key = "".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randint(1, 6)))
        text = "$${%s:value}" % key
        assert substitute_variables(text) == text


def test_logrecord_get_message_never_raises():
    rng = random.Random(888)
    for _ in range(3000):
        message = "".join(
            rng.choice(list("%sd{}abc") + ["%s", "%d", "{}"]) for _ in range(rng.randint(0, 6))
        )
        args = tuple(rng.choice([1, "x", None, 2.5, [1]]) for _ in range(rng.randint(0, 4)))
        record = LogRecord(name="f", level=Level.INFO, message=message, args=args)
        assert isinstance(record.getMessage(), str)
