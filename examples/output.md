# Example output

Captured from [`demo.py`](demo.py):

```bash
PYTHONPATH=. python3 examples/demo.py
```

```text
--- pattern layout ---
2026-10-11 05:14:40 DEBUG [MainThread] order.svc - resolving cart
2026-10-11 05:14:40 INFO  [MainThread] order.svc - user klyne charged $42.00
--- json layout ---
{"time": 1791666880.30071, "level": "WARN", "logger": "order.svc", "message": "inventory low for sku-9", "thread": "MainThread", "process": "MainProcess", "module": "demo", "func": "main", "line": 40, "context": {"request_id": "r-123"}}
--- simple + threshold + regex filters ---
ERROR - db timeout after 3s
ERROR - failed to persist
--- level range WARN..ERROR ---
WARN warning kept
ERROR error kept
--- caller info + exception ---
ERROR at charge_card (demo.py:74) - charge failed
Traceback (most recent call last):
  File "/Users/CK/Desktop/P_NO_16/log4p/examples/demo.py", line 72, in charge_card
    1 / 0
    ~~^~~
ZeroDivisionError: division by zero
```

## What each section shows

| Section | Layout | Point |
|---------|--------|-------|
| pattern layout | `%d{ISO8601} %-5p [%t] %c - %m%n` | left-justified level (`%-5p`), thread, logger name, and `%s`-style argument interpolation |
| json layout | `JSONLayout` | one JSON object per line; `context` carries the MDC field `request_id` |
| simple + filters | `SimpleLayout` | `ThresholdFilter("INFO")` drops DEBUG, `RegexFilter` keeps only `timeout`/`failed` messages |
| level range | `PatternLayout("%p %m")` | `LevelRangeFilter("WARN", "ERROR")` drops INFO and FATAL |
| caller info + exception | `%M (%F:%L)` | reports the real call site (`charge_card`) and renders the traceback |

> The timestamp, the `time` epoch value, and the line numbers vary between runs.
