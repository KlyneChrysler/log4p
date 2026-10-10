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
from log4p import ConsoleAppender, FileAppender, RotatingFileAppender

ConsoleAppender(layout, target="stdout")     # or "stderr", or stream=...
FileAppender("app.log", layout, append=True)
RotatingFileAppender("app.log", maxBytes=10_000_000, backupCount=5, layout=...)
```

Each appender takes an optional `threshold` and any number of filters:

```python
from log4p import ThresholdFilter, LevelRangeFilter, RegexFilter

appender.addFilter(ThresholdFilter("INFO"))
appender.addFilter(RegexFilter(r"timeout|failed", field="message"))
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

See `examples/` for runnable snippets. Captured output for all of them lives
in [`examples/output.md`](examples/output.md) (`python3 examples/demo.py`).

## Why "log4p"?

Log**4J** is for **J**ava. This is for **P**ython.
