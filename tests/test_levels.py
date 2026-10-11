import pytest

from log4p2 import Level, addLevel, getLevel, getLevelNames
from log4p2.levels import ALL, OFF


def test_standard_levels_and_ordering():
    assert int(Level.TRACE) < int(Level.DEBUG) < int(Level.INFO)
    assert int(Level.INFO) < int(Level.WARN) < int(Level.ERROR) < int(Level.FATAL)
    assert Level.INFO > Level.DEBUG
    assert Level.ERROR >= Level.ERROR
    assert int(ALL) == 0
    assert int(OFF) > int(Level.FATAL)


def test_level_compare_with_int():
    assert Level.INFO == 20
    assert Level.INFO > 10
    assert 40 >= Level.ERROR


def test_level_str_and_name():
    assert str(Level.WARN) == "WARN"
    assert Level.WARN.name == "WARN"
    assert Level.WARN.value == 30
    assert repr(Level.WARN) == "Level('WARN', 30)"


def test_aliases():
    assert getLevel("warning") is Level.WARN
    assert getLevel("critical") is Level.FATAL
    assert Level.WARNING is Level.WARN
    assert Level.CRITICAL is Level.FATAL


@pytest.mark.parametrize(
    "value,expected",
    [("info", Level.INFO), ("INFO", Level.INFO), (20, Level.INFO), (Level.INFO, Level.INFO)],
)
def test_getlevel_coercion(value, expected):
    assert getLevel(value) is expected


def test_getlevel_unknown_name_raises():
    with pytest.raises(ValueError):
        getLevel("NOPE")


def test_getlevel_unregistered_int_is_anonymous():
    level = getLevel(12345)
    assert int(level) == 12345
    assert level.name == "LEVEL(12345)"


def test_custom_level_registration():
    custom = addLevel("VERBOSE", 15)
    assert getLevel("verbose") is custom
    assert int(custom) == 15
    assert "VERBOSE" in getLevelNames()


def test_addlevel_idempotent():
    a = addLevel("NOTICE", 25)
    b = addLevel("NOTICE", 25)
    assert a is b
