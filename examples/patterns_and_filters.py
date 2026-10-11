"""PatternLayout selectors, ANSI colour, and composite filters."""

from log4p2 import (
    AndFilter,
    ConsoleAppender,
    Level,
    LogRecord,
    MarkerFilter,
    PatternLayout,
    RegexFilter,
    ThresholdFilter,
    getLogger,
    getMarker,
)

sql = getMarker("SQL")

logger = getLogger("demo.pattern")
logger.setLevel(Level.DEBUG)
logger.setAdditivity(False)
logger.addAppender(
    ConsoleAppender(
        PatternLayout("%highlight{%-5p} %style{%logger}{bold} %style{%msg}{cyan}%n")
    )
)

logger.info("server listening")
logger.warn("disk %d%% full", 92)
logger.error("unhandled: %s", "boom")

# Only records at WARN+ that are also tagged SQL reach this logger.
tagged = getLogger("demo.tagged")
tagged.setLevel(Level.DEBUG)
tagged.setAdditivity(False)
tagged_appender = ConsoleAppender(PatternLayout("%notEmpty{[%marker] }%msg%n"))
tagged_appender.addFilter(AndFilter(ThresholdFilter("INFO"), MarkerFilter(sql)))
tagged.addAppender(tagged_appender)

tagged.info("untagged query, dropped")              # no marker -> dropped
tagged.warn("tagged slow query", marker=sql)        # kept

# Drop noisy records: RegexFilter with on_match="deny" removes matches.
quiet = getLogger("demo.quiet")
quiet.setLevel(Level.DEBUG)
quiet.setAdditivity(False)
quiet_appender = ConsoleAppender(PatternLayout("%m%n"))
quiet_appender.addFilter(RegexFilter(r"healthcheck", field="message", on_match="deny"))
quiet.addAppender(quiet_appender)

quiet.info("real request")
quiet.info("healthcheck ok")                        # denied


def _record(message):
    return LogRecord(name="x", level=Level.INFO, message=message)


print("\n--- selector demo ---")
print(PatternLayout(r"%replace{%msg}{\s}{_}").format(_record("a b c")))
print(PatternLayout("%equals{[%marker]}{[]}{}").format(_record("no marker")))
