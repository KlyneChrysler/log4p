"""Async appender, timed rotation, and stdlib logging interop.

Run:  PYTHONPATH=. python3 examples/async_and_bridge.py
"""

import logging
import os
import time

from log4p import (
    AsyncAppender,
    ConsoleAppender,
    PatternLayout,
    StdlibToLog4pHandler,
    TimedRotatingFileAppender,
    capture_stdlib,
    getLogger,
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "logs")


def main():
    logger = getLogger("app")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")

    # 1) Async + timed rotating file: logging calls never block on disk.
    timed = TimedRotatingFileAppender(
        os.path.join(OUT_DIR, "app.log"),
        when="S",
        interval=1,
        backupCount=3,
        compress=True,
        layout=PatternLayout("%d{ISO8601} %-5p %c - %m%n"),
    )
    logger.addAppender(AsyncAppender(timed, queue_size=1024, overflow="block"))
    logger.addAppender(ConsoleAppender(PatternLayout("%-5p %c - %m%n")))

    for i in range(5):
        logger.info("async record %d", i)

    # 2) Route the standard library's logging into log4p.
    handler = StdlibToLog4pHandler(logger)
    legacy = logging.getLogger("legacy.lib")
    legacy.handlers = []
    legacy.setLevel(logging.DEBUG)
    legacy.propagate = False
    legacy.addHandler(handler)
    legacy.warning("stdlib warning routed into log4p")
    legacy.error("stdlib error routed into log4p")

    # Or, in one line, capture the whole stdlib root logger:
    capture_stdlib("WARNING", logger)
    logging.getLogger("another.lib").warning("captured via capture_stdlib")

    logger.getAppenders()[0].flush()
    time.sleep(0.1)
    logger.info("done")


if __name__ == "__main__":
    main()
