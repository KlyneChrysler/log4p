"""End-to-end demo of log4p: layouts, filters, MDC, and caller info.

Run:  PYTHONPATH=. python3 examples/demo.py
The exact output is captured in examples/output.md.
"""

from log4p import (
    MDC,
    ConsoleAppender,
    JSONLayout,
    LevelRangeFilter,
    PatternLayout,
    RegexFilter,
    SimpleLayout,
    ThresholdFilter,
    getLogger,
)


def app(layout, **kwargs):
    return ConsoleAppender(layout, **kwargs)


def main():
    logger = getLogger("order.svc")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")

    # 1) PatternLayout - the classic log4j layout.
    logger.addAppender(app(PatternLayout("%d{ISO8601} %-5p [%t] %c - %m%n")))
    print("--- pattern layout ---")
    MDC.put("request_id", "r-123")
    logger.debug("resolving cart")
    logger.info("user %s charged %s", "klyne", "$42.00")

    # 2) JSONLayout - one structured object per line.
    logger.removeAllAppenders()
    logger.addAppender(app(JSONLayout()))
    print("--- json layout ---")
    logger.warn("inventory low for %s", "sku-9")

    # 3) SimpleLayout with Threshold + Regex filters stacked on one appender.
    logger.removeAllAppenders()
    filtered = app(SimpleLayout())
    filtered.addFilter(ThresholdFilter("INFO"))
    filtered.addFilter(RegexFilter(r"timeout|failed"))
    logger.addAppender(filtered)
    print("--- simple + threshold + regex filters ---")
    logger.debug("chatty")  # dropped: below INFO
    logger.info("all good")  # dropped: regex miss
    logger.error("db timeout after 3s")
    logger.error("failed to persist")

    # 4) LevelRangeFilter - keep only WARN..ERROR.
    logger.removeAllAppenders()
    ranged = app(PatternLayout("%p %m"))
    ranged.addFilter(LevelRangeFilter("WARN", "ERROR"))
    logger.addAppender(ranged)
    print("--- level range WARN..ERROR ---")
    logger.info("ignored")
    logger.warn("warning kept")
    logger.error("error kept")
    logger.fatal("fatal filtered out")

    # 5) Caller info (%M %F %L) and exception rendering.
    logger.removeAllAppenders()
    logger.addAppender(app(PatternLayout("%p at %M (%F:%L) - %m%n")))
    print("--- caller info + exception ---")

    def charge_card():
        try:
            1 / 0
        except ZeroDivisionError:
            logger.exception("charge failed")

    charge_card()
    MDC.clear()


if __name__ == "__main__":
    main()
