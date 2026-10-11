"""Cron-scheduled rolling files."""

import os
import tempfile
import time
from datetime import datetime

from log4p import (
    CronExpression,
    CronRollingFileAppender,
    Level,
    PatternLayout,
    getLogger,
)

expression = CronExpression("0 0 * * *")
next_midnight = datetime.fromtimestamp(expression.next_after(time.time()))
print("cron '0 0 * * *' next fires at:", next_midnight.isoformat())

tmp = tempfile.mkdtemp()
log_file = os.path.join(tmp, "app.log")

logger = getLogger("demo.cron")
logger.setLevel(Level.INFO)
logger.setAdditivity(False)
logger.addAppender(
    CronRollingFileAppender(
        log_file,
        cron="0 0 * * *",
        suffix="%Y%m%d",
        backupCount=7,
        layout=PatternLayout("%d{ISO8601} %-5p %m%n"),
    )
)

logger.info("before roll")
appender = logger.getAppenders()[0]
# Pretend the scheduled time already passed so the next write rotates.
appender.rollover_at = time.time() - 1
logger.info("after roll")
appender.stop()

print("files:")
for name in sorted(os.listdir(tmp)):
    print(" ", name)
