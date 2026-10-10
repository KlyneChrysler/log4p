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
| `%X{key}` / `%mdc{key}` | MDC value (or whole map with no key) | `r-1` |
| `%x` / `%ndc` | NDC stack | `outer inner` |
| `%h` / `%host` | Hostname | |
| `%n` | Newline | |
| `%%` | Literal `%` | |

Format modifiers work: `%-5p` (left-justify, width 5), `%5p` (right-justify),
`%.30m` (truncate to 30), `%-7.15c` (both).

Other layouts: `SimpleLayout` (`LEVEL - message`) and `JSONLayout`
(one JSON object per line, includes exception text).

## Appenders

```python
from log4p import (
    ConsoleAppender,
    FileAppender,
    RotatingFileAppender,
    TimedRotatingFileAppender,
    AsyncAppender,
)

ConsoleAppender(layout, target="stdout")     # or "stderr", or stream=...
FileAppender("app.log", layout, append=True)
RotatingFileAppender("app.log", maxBytes=10_000_000, backupCount=5, layout=...)
TimedRotatingFileAppender("app.log", when="midnight", backupCount=7,
                          compress=True, layout=...)
AsyncAppender(FileAppender("app.log"), queue_size=4096, overflow="block")
```

- `RotatingFileAppender` rolls on size (`maxBytes`); `TimedRotatingFileAppender`
  rolls on a schedule (`when` = `S`/`M`/`H`/`D`/`midnight`/`W0`..`W6`,
  optional `compress=True` to gzip old files, `backupCount` to expire them).
- `AsyncAppender` wraps another appender and writes from a background thread so
  slow targets never block the caller. `overflow="block"` waits for space (no
  loss); `overflow="discard"` drops and counts via `appender.dropped`.

Each appender takes an optional `threshold` and any number of filters:

```python
from log4p import ThresholdFilter, LevelRangeFilter, RegexFilter

appender.addFilter(ThresholdFilter("INFO"))
appender.addFilter(RegexFilter(r"timeout|failed", field="message"))
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

Quick setup, similar to `logging.basicConfig`:

```python
config.basicConfig(level="INFO", filename="app.log")
```

See `examples/` for runnable snippets (`basic.py`, `from_config.py`,
`demo.py`, `async_and_bridge.py`). Captured output for the demo lives in
[`examples/output.md`](examples/output.md).

## Why "log4p"?

Log**4J** is for **J**ava. This is for **P**ython.
