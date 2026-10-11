"""log4p2 - a log4j-inspired logging framework for Python.

Public entry points mirror log4j's API shape:

    from log4p2 import getLogger, Level, ConsoleAppender, PatternLayout

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
    CallableAppender,
    ConsoleAppender,
    CronRollingFileAppender,
    FailoverAppender,
    FileAppender,
    MemoryAppender,
    NullAppender,
    RotatingFileAppender,
    RoutingAppender,
    SizeAndTimeBasedAppender,
    TimedRotatingFileAppender,
)
from .bridge import (
    StdlibLoggingAppender,
    StdlibToLog4pHandler,
    capture_stdlib,
)
from .context import MDC, NDC
from .cron import CronExpression
from .error import ErrorHandler, FallbackErrorHandler
from .filter import (
    AcceptAllFilter,
    AndFilter,
    BurstFilter,
    CallableFilter,
    ContextMapFilter,
    DenyAllFilter,
    DynamicThresholdFilter,
    Filter,
    FilterReply,
    LevelMatchFilter,
    LevelRangeFilter,
    MapFilter,
    MarkerFilter,
    NoMarkerFilter,
    NotFilter,
    OrFilter,
    RegexFilter,
    StructuredDataFilter,
    ThresholdFilter,
    TimeFilter,
)
from .layout import (
    HTMLLayout,
    JSONLayout,
    Layout,
    LogfmtLayout,
    MarkerPatternSelector,
    PatternLayout,
    SimpleLayout,
    XMLLayout,
)
from .levels import ALL, OFF, Level, addLevel, getLevel, getLevelNames
from .logger import LogBuilder, Logger, getLogger, getRootLogger, shutdown
from .mail import SMTPAppender
from .marker import Marker, MarkerManager, getMarker, getMarkerNames
from .message import MapMessage, Message, StringMapMessage, StructuredDataMessage
from .net import HttpAppender, SocketAppender, SyslogAppender
from .record import LogRecord
from .rewrite import (
    CallableRewritePolicy,
    MapRewritePolicy,
    PropertiesRewritePolicy,
    RewriteAppender,
    RewritePolicy,
)
from .syslog import RFC5424Layout, SyslogLayout

__version__ = "0.2.0"

__all__ = [
    "Level",
    "OFF",
    "ALL",
    "addLevel",
    "getLevel",
    "getLevelNames",
    "LogRecord",
    "Marker",
    "MarkerManager",
    "getMarker",
    "getMarkerNames",
    "Message",
    "MapMessage",
    "StringMapMessage",
    "StructuredDataMessage",
    "Layout",
    "SimpleLayout",
    "PatternLayout",
    "JSONLayout",
    "LogfmtLayout",
    "XMLLayout",
    "HTMLLayout",
    "SyslogLayout",
    "RFC5424Layout",
    "MarkerPatternSelector",
    "Filter",
    "FilterReply",
    "ThresholdFilter",
    "LevelMatchFilter",
    "LevelRangeFilter",
    "RegexFilter",
    "StructuredDataFilter",
    "TimeFilter",
    "MarkerFilter",
    "MapFilter",
    "AndFilter",
    "OrFilter",
    "NotFilter",
    "AcceptAllFilter",
    "DenyAllFilter",
    "ContextMapFilter",
    "DynamicThresholdFilter",
    "NoMarkerFilter",
    "BurstFilter",
    "CallableFilter",
    "Appender",
    "AsyncAppender",
    "ConsoleAppender",
    "FailoverAppender",
    "FileAppender",
    "CronRollingFileAppender",
    "MemoryAppender",
    "NullAppender",
    "CallableAppender",
    "RotatingFileAppender",
    "RoutingAppender",
    "TimedRotatingFileAppender",
    "SizeAndTimeBasedAppender",
    "RewritePolicy",
    "CallableRewritePolicy",
    "MapRewritePolicy",
    "PropertiesRewritePolicy",
    "RewriteAppender",
    "SocketAppender",
    "SyslogAppender",
    "HttpAppender",
    "SMTPAppender",
    "ErrorHandler",
    "FallbackErrorHandler",
    "Logger",
    "LogBuilder",
    "getLogger",
    "getRootLogger",
    "shutdown",
    "MDC",
    "NDC",
    "CronExpression",
    "StdlibLoggingAppender",
    "StdlibToLog4pHandler",
    "capture_stdlib",
    "config",
]
