"""Minimal log4p usage: build a logger, appender, and layout in code."""

from log4p import ConsoleAppender, Level, MDC, PatternLayout, getLogger

logger = getLogger("myapp.db")
logger.setLevel(Level.DEBUG)
logger.setAdditivity(False)
logger.addAppender(
    ConsoleAppender(PatternLayout("%d{ISO8601} %-5p %c - %m%n"))
)

MDC.put("request_id", "r-123")

logger.debug("opening connection pool")
logger.info("connected to %s", "orders-db")
logger.warn("pool at %d%% capacity", 85)

try:
    1 / 0
except ZeroDivisionError:
    logger.exception("unhandled failure")

MDC.clear()
