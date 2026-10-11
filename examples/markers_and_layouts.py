"""Markers, stack traces, and the logfmt / XML / HTML layouts."""

from log4p2 import (
    ConsoleAppender,
    HTMLLayout,
    Level,
    LogfmtLayout,
    MarkerFilter,
    PatternLayout,
    XMLLayout,
    getLogger,
    getMarker,
)

sql = getMarker("SQL")
audit = getMarker("AUDIT", parents=[sql])

console = getLogger("demo.console")
console.setLevel(Level.DEBUG)
console.setAdditivity(False)
console.addAppender(
    ConsoleAppender(PatternLayout("%-5p [%marker] %c - %m%n%stack"))
)

console.info("plain message")
console.info("query executed", marker=sql)
console.info("who called me?", stack_info=True)


filtered = getLogger("demo.filtered")
filtered.setLevel(Level.DEBUG)
filtered.setAdditivity(False)
appender = ConsoleAppender(PatternLayout("%m"))
appender.addFilter(MarkerFilter(sql))
filtered.addAppender(appender)

filtered.info("dropped (no marker)")
filtered.info("kept (sql marker)", marker=sql)
filtered.info("kept (audit inherits sql)", marker=audit)


print("\n--- logfmt ---")
logfmt = getLogger("demo.logfmt")
logfmt.setLevel(Level.INFO)
logfmt.setAdditivity(False)
logfmt.addAppender(ConsoleAppender(LogfmtLayout(timestamp=False)))
logfmt.info("streaming %d rows", 42, extra={"shard": "us-east"})

print("\n--- xml ---")
xml = getLogger("demo.xml")
xml.setLevel(Level.INFO)
xml.setAdditivity(False)
xml.addAppender(ConsoleAppender(XMLLayout()))
xml.info("exported report")

print("\n--- html (rows; header/footer written on start/stop) ---")
html = getLogger("demo.html")
html.setLevel(Level.INFO)
html.setAdditivity(False)
html_appender = ConsoleAppender(HTMLLayout(title="demo"))
html.addAppender(html_appender)
html_appender.start()
html.info("first row")
html_appender.stop()
