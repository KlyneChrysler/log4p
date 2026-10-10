"""Log levels with a log4j-style registry and custom level support.

Levels are the standard log4j set (TRACE, DEBUG, INFO, WARN, ERROR, FATAL) plus
the two sentinels OFF and ALL.  Values use Python's "higher is more severe"
convention so a level behaves exactly like an ``int`` in comparisons, which
keeps ``isEnabledFor`` checks cheap and intuitive.
"""

from __future__ import annotations

import threading
from typing import Dict, Union


class Level(int):
    """A logging level. Subclasses ``int`` so comparisons "just work"."""

    def __new__(cls, name: str, value: int) -> "Level":
        obj = super().__new__(cls, value)
        return obj

    def __init__(self, name: str, value: int) -> None:  # noqa: D401
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> int:
        return int(self)

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"Level({self._name!r}, {int(self)})"

    def __reduce__(self):
        return (_rebuild_level, (self._name, int(self)))


_REGISTRY: Dict[str, Level] = {}
_LOCK = threading.RLock()


def _register(name: str, value: int) -> Level:
    level = Level(name, value)
    _REGISTRY[name.upper()] = level
    return level


def _rebuild_level(name: str, value: int) -> Level:
    existing = _REGISTRY.get(name.upper())
    if existing is not None and int(existing) == value:
        return existing
    return Level(name, value)


# Standard levels (higher value == more severe).
TRACE = _register("TRACE", 5)
DEBUG = _register("DEBUG", 10)
INFO = _register("INFO", 20)
WARN = _register("WARN", 30)
ERROR = _register("ERROR", 40)
FATAL = _register("FATAL", 50)
OFF = _register("OFF", 2 ** 63 - 1)
ALL = _register("ALL", 0)

# Aliases so code written against Python's stdlib or other loggers still works.
_REGISTRY["WARNING"] = WARN
_REGISTRY["CRITICAL"] = FATAL
_REGISTRY["NOTSET"] = ALL

# Attach the standard levels as class attributes for ``Level.INFO`` access.
Level.TRACE = TRACE
Level.DEBUG = DEBUG
Level.INFO = INFO
Level.WARN = WARN
Level.WARNING = WARN
Level.ERROR = ERROR
Level.FATAL = FATAL
Level.CRITICAL = FATAL
Level.OFF = OFF
Level.ALL = ALL


def addLevel(name: str, value: int) -> Level:
    """Register a custom level and return it.

    Re-registering an existing name overwrites its value, mirroring log4j's
    ``Level.toLevel`` extensibility.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("level name must be a non-empty string")
    if not isinstance(value, int):
        raise TypeError("level value must be an int")
    with _LOCK:
        existing = _REGISTRY.get(name.upper())
        if existing is not None and int(existing) == value:
            return existing
        return _register(name, value)


def getLevel(level: Union[str, int, Level]) -> Level:
    """Coerce *level* to a :class:`Level`.

    Accepts a ``Level`` (returned as-is), a case-insensitive name, or an int.
    Ints that match a registered value resolve to that level; otherwise an
    anonymous level named ``LEVEL`` is returned.
    """
    if isinstance(level, Level):
        return level
    if isinstance(level, str):
        key = level.upper()
        try:
            return _REGISTRY[key]
        except KeyError:
            raise ValueError(f"unknown level name: {level!r}") from None
    if isinstance(level, int):
        for candidate in set(_REGISTRY.values()):
            if int(candidate) == level:
                return candidate
        return Level(f"LEVEL({level})", level)
    raise TypeError(f"cannot interpret {level!r} as a level")


def getLevelNames() -> Dict[str, int]:
    """Return a copy of the name -> value mapping."""
    return {name: int(lvl) for name, lvl in _REGISTRY.items()}


def isEnabledFor(level: Level, threshold: Level) -> bool:
    """True if a record at *level* passes an effective *threshold*."""
    return int(level) >= int(threshold)
