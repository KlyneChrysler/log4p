# log4p2

A log4j-inspired logging framework for Python: named loggers, appenders, layouts, filters, markers, and file/dict config.

```python
from log4p2 import getLogger, PatternLayout, ConsoleAppender

logger = getLogger("myapp.db")
logger.setLevel("DEBUG")
logger.addAppender(ConsoleAppender(PatternLayout("%d{ISO8601} %-5p [%t] %c - %m%n")))

logger.info("connected to %s", "orders-db")
# 2026-10-12 01:04:57 INFO  [MainThread] myapp.db - connected to orders-db
```

## Install

```bash
pip install -e .   # Python 3.9+, only dependency: PyYAML
```

## What you get

- **Hierarchy:** dotted logger names inherit level and appenders; additivity control.
- **Levels:** TRACE, DEBUG, INFO, WARN, ERROR, FATAL, plus custom levels.
- **Layouts:** `PatternLayout` (full log4j vocabulary), JSON, logfmt, XML, HTML, Simple.
- **Appenders:** console, file, size/time/cron rotation, async, rewrite, routing, failover, socket, syslog, HTTP, SMTP, memory.
- **Filters:** threshold, level, regex, marker, context, burst, time-of-day; combine with And/Or/Not.
- **Context:** MDC/NDC per thread and asyncio task; markers with inheritance.
- **Config:** dict, YAML or JSON with `${env:...}` substitution and auto-reload.
- **Interop:** route stdlib `logging` into log4p2 and back.

## How it compares

| Feature | log4p2 | stdlib `logging` | structlog | loguru |
|---|---|---|---|---|
| Built-in JSON output | Yes | No (custom formatter) | Yes (flat, cleanest) | Yes (verbose) |
| Caller info in output (file:line) | Yes | Yes | Needs extra processor | Yes |
| log4j-style pattern language | Yes | No | No | No |
| Context fields (MDC) | Yes | Via `extra` | Yes | Yes |
| Hierarchical markers | Yes | No | No | No |
| Size / time rotation | Yes | Yes | Delegates to stdlib | Yes |
| Cron-based rotation | Yes | No | No | No |
| Routing / failover / rewrite appenders | Yes | No | No | No |
| Composable filters (And / Or / Not) | Yes | Partial | Via processors | Via function |
| Two-way stdlib bridge | Yes | n/a | Yes | Partial |
| Extra dependencies | PyYAML | None | structlog | loguru |
| Maturity | New, not yet production-tested | Standard | Proven | Proven |

Output formats for text, JSON, context and exceptions were checked by running the same events through all four. Other rows come from each library's documented features.

## Example output

```text
2026-10-12 01:04:57 INFO  [MainThread] shop.checkout [r-1042] - user klyne started checkout
2026-10-12 01:04:57 ERROR [MainThread] shop.checkout [r-1042] - payment gateway timeout after 3s
```

```json
{"time": 1791735383.8, "level": "WARN", "logger": "order.svc", "message": "inventory low", "thread": "MainThread", "func": "main", "line": 11, "context": {"request_id": "r-123"}}
```

## Test

```bash
python3 -m pytest -q
```

## Limitations

- **AsyncAppender queue loss on hard kill**: When using `AsyncAppender`, events in the queue that haven't been processed by the background worker will be lost if the process is terminated abruptly (e.g., `SIGKILL`, `os._exit`, power loss). This is inherent to asynchronous logging designs. For critical audit trails, use synchronous appenders or call `appender.flush()` before graceful shutdown.

MIT licensed.
