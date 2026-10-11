# log4p

A **log4j-inspired logging framework for Python**. Named loggers, appenders,
layouts, filters, levels, and file/dict configuration — the pieces you know
from log4j, expressed in idiomatic Python.

```python
from log4p import getLogger, PatternLayout, ConsoleAppender

logger = getLogger("myapp.db")
logger.setLevel("DEBUG")
logger.addAppender(ConsoleAppender(PatternLayout("%d{ISO8601} %-5p %c - %m%n")))

logger.info("connected to %s", "orders-db")
# 2026-10-11 05:09:01 INFO  myapp.db - connected to orders-db
```

## Install

```bash
pip install -e .
```

Requires Python 3.9+. The only runtime dependency is `PyYAML` (for YAML configs).

## Concepts

| log4j term | log4p | role |
|------------|-------|------|
| Logger | `Logger` | Named, hierarchical event source |
| Level | `Level` | TRACE, DEBUG, INFO, WARN, ERROR, FATAL (+ OFF/ALL) |
| Appender | `Appender` | Output destination (console, file, rotating file) |
| Layout | `Layout` | Formats a record (`PatternLayout`, `SimpleLayout`, `JSONLayout`) |
| Filter | `Filter` | Tri-state gate (`ACCEPT`/`DENY`/`NEUTRAL`) |
| MDC / NDC | `MDC` / `NDC` | Per-context diagnostic data |

### Logger hierarchy

Loggers are named with dots and inherit configuration from their nearest
ancestor. `getLogger("myapp.db.pool")` automatically sits under
`getLogger("myapp.db")`. Events walk up the chain until a logger with
`additivity = False` is reached, exactly like log4j.

```python
from log4p import getLogger

root = getLogger()
root.setLevel("WARN")

db = getLogger("myapp.db")
db.setLevel("DEBUG")        # only this subtree logs at DEBUG
db.setAdditivity(False)     # do not also send records to the root appenders
```

## Levels

```python
from log4p import Level, addLevel

Level.TRACE, Level.DEBUG, Level.INFO, Level.WARN, Level.ERROR, Level.FATAL
Level.OFF, Level.ALL

# Custom levels are first-class:
addLevel("VERBOSE", 15)
logger.log("VERBOSE", "chatty")
```

Levels subclass `int`, so `Level.ERROR > Level.WARN` and
`Level.INFO == 20` both hold and every `logging`-style comparison works.

## PatternLayout

The full log4j conversion vocabulary is supported:

| Conversion | Meaning | Example |
|------------|---------|---------|
| `%c` / `%logger` | Logger name (`%c{2}` = rightmost 2 segments) | `myapp.db` |
| `%d{fmt}` / `%date` | Timestamp — preset (`ISO8601`, `ABSOLUTE`, `DATE`), Java pattern (`HH:mm:ss,SSS`), or strftime | `2026-10-11 05:09:01` |
| `%m` / `%msg` | Formatted message | `connected` |
| `%p` / `%level` | Level name | `INFO` |
| `%t` / `%thread` | Thread name | `MainThread` |
| `%r` / `%relative` | Milliseconds since start | `42` |
| `%F` / `%file` | Source filename | `db.py` |
| `%L` / `%line` | Source line number | `42` |
| `%M` / `%method` | Source function | `connect` |
| `%C` / `%class` | Source module | `db` |
| `%X{key}` / `%mdc{key}` | MDC value (or whole map with no key); `%X{key:-def}` for a default | `r-1` |
| `%K{key}` | Map/context value (or whole map); `%K{key:-def}` for a default | `r-1` |
| `%x` / `%ndc` | NDC stack | `outer inner` |
| `%marker` / `%markerSimpleName` | Marker attached to the record | `SQL` |
| `%stack` | Stack trace from `stack_info=True` | |
| `%throwable` / `%ex` / `%exception` | Exception traceback | |
| `%l` / `%location` | `module.function(file:line)` | `db.connect(db.py:42)` |
| `%pid` / `%processId` | Process id | `8123` |
| `%T` / `%tid` / `%threadId` | Thread id | `140234` |
| `%N` / `%nanos` | Nanoseconds since start | `42000000` |
| `%env{NAME}` | Environment variable; `%env{NAME:-def}` for a default | |
| `%h` / `%host` / `%hostName` | Hostname | |
| `%n` | Newline | |
| `%%` | Literal `%` | |

Format modifiers work: `%-5p` (left-justify, width 5), `%5p` (right-justify),
`%.30m` (truncate to 30), `%-7.15c` (both). `%c{1.}` abbreviates ancestor
segments to their first letter (`org.apache.commons.Foo` -> `o.a.c.Foo`).

Selectors transform the result of an inner pattern (nested braces are handled):

| Selector | Meaning |
|----------|---------|
| `%replace{pattern}{regex}{substitution}` | Replace regex matches in *pattern* |
| `%equals{pattern}{test}{substitution}` | Replace literal *test* occurrences in *pattern* |
| `%equalsIgnoreCase{pattern}{test}{substitution}` | Case-insensitive variant |
| `%notEmpty{pattern}` | Output *pattern* only if its variables are all non-empty |
| `%maxLen{pattern}{N}` | Truncate to *N* chars (adds `...` when *N* > 20) |
| `%encode{pattern}{HTML\|XML\|JSON\|CRLF}` | Escape the inner result |

```python
PatternLayout(r"%replace{%msg}{\s}{_}")      # spaces -> underscores
PatternLayout("%notEmpty{[%marker]} %msg")   # hide "[marker]" when no marker
PatternLayout("%maxLen{%m}{80}")             # truncate long messages
PatternLayout("%encode{%m}{HTML}")           # HTML-escape the message
```

ANSI colour is supported for consoles that understand escapes:

| Converter | Meaning |
|-----------|---------|
| `%highlight{pattern}{LEVEL=color, ...}` | Colour by level (FATAL/ERROR=red, WARN=yellow, INFO=green, DEBUG=cyan, TRACE=black) |
| `%style{pattern}{name, ...}` | Apply a style (`bold`, `underline`, `cyan`, `bg_red`, ...) |
| `%red{pattern}`, `%green{...}`, ... | Colour shorthand |

```python
PatternLayout("%highlight{%-5p} %style{%logger}{bold,cyan} %msg%n")
```

Other layouts:

| Layout | Output |
|--------|--------|
| `SimpleLayout` | `LEVEL - message` |
| `JSONLayout` | one JSON object per line (includes marker, stack, exception) |
| `LogfmtLayout` | `level=info logger=... msg="..."` key-value pairs |
| `XMLLayout` | one `<event>` element per record |
| `HTMLLayout` | a full HTML table (header/footer written by stream appenders) |

## Appenders

```python
from log4p import (
    ConsoleAppender,
    FileAppender,
    RotatingFileAppender,
    TimedRotatingFileAppender,
    SizeAndTimeBasedAppender,
    AsyncAppender,
    RewriteAppender,
    MapRewritePolicy,
    PropertiesRewritePolicy,
    SocketAppender,
    SyslogAppender,
    SMTPAppender,
    NullAppender,
)

ConsoleAppender(layout, target="stdout")     # or "stderr", or stream=...
FileAppender("app.log", layout, append=True)
RotatingFileAppender("app.log", maxBytes=10_000_000, backupCount=5, layout=...)
TimedRotatingFileAppender("app.log", when="midnight", backupCount=7,
                          compress=True, layout=...)
SizeAndTimeBasedAppender("app.log", maxBytes=10_000_000, when="d",
                         backupCount=7, compress=True, layout=...)
AsyncAppender(FileAppender("app.log"), queue_size=4096, overflow="block")
RewriteAppender(FileAppender("app.log"),
                policy=MapRewritePolicy({"request_id": "req-42"}))
SocketAppender("logs.internal", 5140, layout=PatternLayout("%m%n"))
SyslogAppender("localhost", port=514, facility="LOCAL0", socktype="UDP")
SyslogAppender("localhost", rfc5424=True, appName="svc", msgId="ID47")
SMTPAppender("smtp.example.com", port=587, fromaddr="log@x", toaddrs=["ops@x"],
             triggerLevel="ERROR")
NullAppender()                               # discard everything
```

- `RotatingFileAppender` rolls on size (`maxBytes`); `TimedRotatingFileAppender`
  rolls on a schedule (`when` = `S`/`M`/`H`/`D`/`midnight`/`W0`..`W6`,
  optional `compress=True` to gzip old files, `backupCount` to expire them).
- `SizeAndTimeBasedAppender` rolls on whichever comes first: the size limit or
  the time period. Rotated files are `<file>.<timestamp>.<n>` so multiple rolls
  in one period stay distinct.
- Size arguments accept strings: `maxBytes="10MB"`, `"512KB"`, `"1G"`.
- Pass `onStartup=True` to any rolling appender to rotate an existing non-empty
  file the first time it is opened (log4j's `OnStartupTriggeringPolicy`).
- `AsyncAppender` wraps another appender and writes from a background thread so
  slow targets never block the caller. `overflow="block"` waits for space (no
  loss); `overflow="discard"` drops and counts via `appender.dropped`.
- `RewriteAppender` runs a `RewritePolicy` over each record before delegating.
  `MapRewritePolicy({"k": "v"}, mode="add"|"update")` adds/updates context (MDC)
  entries; `PropertiesRewritePolicy({"region": "us-east-1"})` substitutes
  `${key}` tokens in the message.
- `SocketAppender` ships rendered events over TCP; `SyslogAppender` emits syslog
  over UDP or TCP (severity derived from the level) in RFC 3164 format, or RFC
  5424 (`rfc5424=True`, with `appName`/`procId`/`msgId`). Both reconnect lazily
  and throttle retries (`reconnectDelay`).
- `SMTPAppender` keeps a ring buffer of recent events and emails them (with the
  triggering stack trace) when one reaches `triggerLevel` (default `ERROR`).
  Supports `starttls`, `ssl`, and `username`/`password`.
- `NullAppender` discards every event (a `/dev/null` sink).

Loggers expose the usual level checks: `logger.isDebugEnabled()`,
`isInfoEnabled()`, `isWarnEnabled()`, `isErrorEnabled()`, `isFatalEnabled()`,
`isTraceEnabled()`.

Each appender takes an optional `threshold` and any number of filters:

```python
from log4p import (
    ThresholdFilter, LevelMatchFilter, LevelRangeFilter, RegexFilter, MarkerFilter,
    AndFilter, OrFilter, NotFilter, AcceptAllFilter, DenyAllFilter,
)

appender.addFilter(ThresholdFilter("INFO"))            # level >= INFO
appender.addFilter(LevelMatchFilter("ERROR"))          # exactly ERROR
appender.addFilter(RegexFilter(r"timeout|failed", field="message"))
appender.addFilter(MarkerFilter("SQL"))          # only records tagged SQL

# Compose filters:
appender.addFilter(AndFilter(ThresholdFilter("WARN"),
                             RegexFilter(r"db-", field="name")))
appender.addFilter(OrFilter(RegexFilter(r"audit"), RegexFilter(r"billing")))
appender.addFilter(NotFilter(RegexFilter(r"healthcheck", field="message")))
```

`AndFilter` accepts only when every child accepts (any denial denies);
`OrFilter` accepts when any child accepts; `NotFilter` inverts one child.
All three build from config with nested `filters` / `filter` keys.
`AcceptAllFilter` / `DenyAllFilter` accept or deny unconditionally.

Level, range, regex, and marker filters take `onMatch` / `onMismatch` replies
(each `"accept"`, `"deny"`, or `"neutral"`, default `"neutral"` / `"deny"`),
so you can gate an appender on a match (`onMatch="accept"`):

```python
appender.addFilter(ThresholdFilter("ERROR", onMatch="accept"))  # ONLY errors
```

### Error handlers

An appender that raises while appending consults its error handler. The default
reports to `stderr`; `FallbackErrorHandler` swaps a dead primary appender for
backup(s) so logging survives a full disk or a closed socket:

```python
from log4p import ErrorHandler, FallbackErrorHandler

primary.setErrorHandler(ErrorHandler())          # report to stderr (default)

fallback = FallbackErrorHandler()
fallback.setAppender(primary)
fallback.setBackupAppender(ConsoleAppender(PatternLayout("%m")))
primary.setErrorHandler(fallback)                # on failure, backups take over
```

Appenders are flushed and stopped automatically on interpreter exit (`atexit`),
so buffered/async output is not lost.

## Standard library interop

Keep using `logging.getLogger(...)` anywhere (including third-party code) and
route it into log4p:

```python
from log4p import capture_stdlib, StdlibToLog4pHandler

capture_stdlib("WARNING")                        # stdlib root -> log4p root
logging.getLogger("myapp.lib").warning("routed") # lands in log4p appenders

# or target a specific log4p logger:
logging.getLogger("legacy").addHandler(StdlibToLog4pHandler("myapp.legacy"))
```

Level, caller info, `extra={...}` fields, and MDC all carry across. The reverse
direction is available too:

```python
from log4p import StdlibLoggingAppender

logger.addAppender(StdlibLoggingAppender(logging.getLogger("...") ))
```

## MDC / NDC

```python
from log4p import MDC, NDC

MDC.put("request_id", "r-123")
NDC.push("checkout")
logger.info("order placed")   # %X{request_id} -> r-123, %x -> checkout
NDC.pop()
MDC.clear()
```

Both are isolated per thread / asyncio task.

## Markers

Markers are named (optionally hierarchical) tags you attach per call and filter on
with `MarkerFilter`, mirroring log4j:

```python
from log4p import getMarker, MarkerFilter

secure = getMarker("SECURITY")
sql = getMarker("SQL")
audit = getMarker("AUDIT", parents=[secure])   # audit "is a" security marker

logger.info("SELECT 1", marker=sql)            # %marker -> SQL
appender.addFilter(MarkerFilter(secure))       # passes audit too (inheritance)
```

## Stack traces

Request a stack trace without an exception via `stack_info=True` (captured where
you call the logger); render it with `%stack`. Exceptions render with
`%throwable` / `%ex`:

```python
logger.info("where am I?", stack_info=True)
logger.exception("failed")   # %throwable contains the traceback
```

## Configuration

### Dict / YAML

```python
from log4p import config

config.dictConfig({
    "root": {"level": "WARN", "appenders": ["console"]},
    "loggers": {
        "myapp.db": {"level": "DEBUG", "appenders": ["console", "db_file"],
                     "additive": False},
    },
    "appenders": {
        "console": {
            "class": "ConsoleAppender",
            "target": "stdout",
            "layout": {"class": "PatternLayout",
                       "pattern": "%d{ISO8601} %-5p %c - %m%n"},
        },
        "db_file": {
            "class": "RotatingFileAppender",
            "filename": "logs/db.log",
            "maxBytes": 1048576,
            "backupCount": 3,
            "layout": {"class": "JSONLayout"},
            "filters": [{"class": "LevelRangeFilter", "min_level": "INFO"}],
        },
    },
})
```

The same structure loads from a file (YAML or JSON):

```python
config.fileConfig("log4p.yaml")
```

Values may reference environment variables or interpreter attributes, with an
optional default: `${env:LOG_LEVEL:-INFO}`, `${env:HOME}`, `${sys:maxsize}`.
Substitution is recursive and on by default; pass `"substitute": False` at the
top level to disable it. Any component by short name (`LogfmtLayout`, `XMLLayout`,
`HTMLLayout`, `MarkerFilter`, ...) or by dotted import path is available.

Quick setup, similar to `logging.basicConfig`:

```python
config.basicConfig(level="INFO", filename="app.log")
```

See `examples/` for runnable snippets (`basic.py`, `from_config.py`,
`demo.py`, `async_and_bridge.py`, `markers_and_layouts.py`,
`patterns_and_filters.py`, `rolling_and_rewrite.py`, `net_appenders.py`).
Captured output for the demo lives in
[`examples/output.md`](examples/output.md).

## Why "log4p"?

Log**4J** is for **J**ava. This is for **P**ython.
