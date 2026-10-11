"""Throughput benchmark for log4p.

Run directly::

    python3 benchmarks/benchmark.py            # default 200k events, 1 thread
    python3 benchmarks/benchmark.py 500000 4   # 500k events across 4 threads

It measures events/second for common appenders and the cost of a disabled
level, so regressions in the hot path are easy to spot.
"""

import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log4p2 import (  # noqa: E402
    ConsoleAppender,
    FileAppender,
    MemoryAppender,
    PatternLayout,
    getLogger,
)
from log4p2.context import MDC  # noqa: E402
from log4p2.logger import getLoggerManager  # noqa: E402

PATTERN = "%d{ISO8601} %-5p [%c] %X{request} - %m%n"


def _time(name, count, fn):
    start = time.perf_counter()
    fn()
    elapsed = time.perf_counter() - start
    rate = count / elapsed if elapsed else float("inf")
    print(f"{name:<34} {rate:>12,.0f} events/s   ({elapsed:6.3f}s)")
    return rate


def _drive(logger, count, threads, message="user %s logged in"):
    per_thread = count // threads
    remainder = count - per_thread * threads
    barrier = threading.Barrier(threads)

    def worker(n):
        barrier.wait()
        for i in range(n):
            logger.info(message, i)

    workers = [
        threading.Thread(target=worker, args=(per_thread + (1 if t < remainder else 0),))
        for t in range(threads)
    ]
    for w in workers:
        w.start()
    for w in workers:
        w.join()


def _reset():
    getLoggerManager().clear()
    getLoggerManager().warn_on_no_appenders = False


def bench_memory(count, threads):
    _reset()
    appender = MemoryAppender(PatternLayout(PATTERN))
    logger = getLogger("bench.memory")
    logger.setLevel("INFO")
    logger.addAppender(appender)
    _time(f"MemoryAppender ({threads}t)", count, lambda: _drive(logger, count, threads))


def bench_file(count, threads):
    _reset()
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    appender = FileAppender(path, PatternLayout(PATTERN), immediateFlush=False)
    logger = getLogger("bench.file")
    logger.setLevel("INFO")
    logger.addAppender(appender)
    try:
        _time(f"FileAppender buffered ({threads}t)", count, lambda: _drive(logger, count, threads))
        appender.flush()
    finally:
        os.remove(path)


def bench_console_devnull(count, threads):
    _reset()
    with open(os.devnull, "w") as sink:
        appender = ConsoleAppender(PatternLayout(PATTERN), stream=sink)
        logger = getLogger("bench.console")
        logger.setLevel("INFO")
        logger.addAppender(appender)
        _time(f"ConsoleAppender->devnull ({threads}t)", count, lambda: _drive(logger, count, threads))


def bench_mdc(count, threads):
    _reset()
    appender = MemoryAppender(PatternLayout(PATTERN))
    logger = getLogger("bench.mdc")
    logger.setLevel("INFO")
    logger.addAppender(appender)

    def run():
        MDC.put("request", "r-1")
        _drive(logger, count, threads)
        MDC.clear()

    _time(f"MemoryAppender + MDC ({threads}t)", count, run)


def bench_disabled(count, threads):
    _reset()
    logger = getLogger("bench.off")
    logger.setLevel("WARN")

    def run():
        for _ in range(count):
            if logger.isEnabledFor(20):  # INFO
                logger.info("never")

    _time(f"disabled level check ({threads}t)", count, run)


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
    threads = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(f"log4p benchmark: {count:,} events, {threads} thread(s)\n")
    bench_memory(count, threads)
    bench_file(count, threads)
    bench_console_devnull(count, threads)
    bench_mdc(count, threads)
    bench_disabled(count, threads)
    _reset()


if __name__ == "__main__":
    main()
