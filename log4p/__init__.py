"""log4p - a log4j-inspired logging framework for Python.

Public entry points mirror log4j's API shape:

    from log4p import getLogger, Level, ConsoleAppender, PatternLayout

    logger = getLogger("myapp.db")
    logger.setLevel(Level.DEBUG)
    appender = ConsoleAppender(PatternLayout("%d{ISO8601} %-5p %c - %m%n"))
    logger.addAppender(appender)
    logger.info("connected to %s", "orders-db")
"""

from .levels import Level, OFF, ALL, addLevel, getLevel, getLevelNames
from .record import LogRecord
from .layout import (
    Layout,
    SimpleLayout,
    PatternLayout,
    JSONLayout,
)
from .filter import (
    Filter,
    FilterReply,
    ThresholdFilter,
    LevelRangeFilter,
    RegexFilter,
)
from .appender import (
    Appender,
    ConsoleAppender,
    FileAppender,
    RotatingFileAppender,
)
from .logger import Logger, getLogger, getRootLogger, shutdown
from .context import MDC, NDC
from . import config

__version__ = "0.1.0"

__all__ = [
    "Level",
    "OFF",
    "ALL",
    "addLevel",
    "getLevel",
    "getLevelNames",
    "LogRecord",
    "Layout",
    "SimpleLayout",
    "PatternLayout",
    "JSONLayout",
    "Filter",
    "FilterReply",
    "ThresholdFilter",
    "LevelRangeFilter",
    "RegexFilter",
    "Appender",
    "ConsoleAppender",
    "FileAppender",
    "RotatingFileAppender",
    "Logger",
    "getLogger",
    "getRootLogger",
    "shutdown",
    "MDC",
    "NDC",
    "config",
]
