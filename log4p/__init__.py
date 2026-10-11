"""log4p - a log4j-inspired logging framework for Python.

Public entry points mirror log4j's API shape:

    from log4p import getLogger, Level, ConsoleAppender, PatternLayout

    logger = getLogger("myapp.db")
    logger.setLevel(Level.DEBUG)
    appender = ConsoleAppender(PatternLayout("%d{ISO8601} %-5p %c - %m%n"))
    logger.addAppender(appender)
    logger.info("connected to %s", "orders-db")
"""

from . import config
from .appender import (
    Appender,
    AsyncAppender,
    ConsoleAppender,
    FileAppender,
    NullAppender,
    RotatingFileAppender,
    SizeAndTimeBasedAppender,
    TimedRotatingFileAppender,
)
from .bridge import (
    StdlibLoggingAppender,
    StdlibToLog4pHandler,
    capture_stdlib,
)
from .context import MDC, NDC
from .error import ErrorHandler, FallbackErrorHandler
from .filter import (
    AcceptAllFilter,
    AndFilter,
    DenyAllFilter,
    Filter,
    FilterReply,
    LevelMatchFilter,
    LevelRangeFilter,
    MarkerFilter,
    NotFilter,
    OrFilter,
    RegexFilter,
    ThresholdFilter,
)
from .layout import (
    HTMLLayout,
    JSONLayout,
    Layout,
    LogfmtLayout,
    PatternLayout,
    SimpleLayout,
    XMLLayout,
)
from .levels import ALL, OFF, Level, addLevel, getLevel, getLevelNames
from .logger import Logger, getLogger, getRootLogger, shutdown
from .mail import SMTPAppender
from .marker import Marker, getMarker, getMarkerNames
from .net import SocketAppender, SyslogAppender
from .record import LogRecord
from .rewrite import MapRewritePolicy, RewriteAppender, RewritePolicy

__version__ = "0.1.0"

__all__ = [
    "Level",
    "OFF",
    "ALL",
    "addLevel",
    "getLevel",
    "getLevelNames",
    "LogRecord",
    "Marker",
    "getMarker",
    "getMarkerNames",
    "Layout",
    "SimpleLayout",
    "PatternLayout",
    "JSONLayout",
    "LogfmtLayout",
    "XMLLayout",
    "HTMLLayout",
    "Filter",
    "FilterReply",
    "ThresholdFilter",
    "LevelMatchFilter",
    "LevelRangeFilter",
    "RegexFilter",
    "MarkerFilter",
    "AndFilter",
    "OrFilter",
    "NotFilter",
    "AcceptAllFilter",
    "DenyAllFilter",
    "Appender",
    "AsyncAppender",
    "ConsoleAppender",
    "FileAppender",
    "NullAppender",
    "RotatingFileAppender",
    "TimedRotatingFileAppender",
    "SizeAndTimeBasedAppender",
    "RewritePolicy",
    "MapRewritePolicy",
    "RewriteAppender",
    "SocketAppender",
    "SyslogAppender",
    "SMTPAppender",
    "ErrorHandler",
    "FallbackErrorHandler",
    "Logger",
    "getLogger",
    "getRootLogger",
    "shutdown",
    "MDC",
    "NDC",
    "StdlibLoggingAppender",
    "StdlibToLog4pHandler",
    "capture_stdlib",
    "config",
]
