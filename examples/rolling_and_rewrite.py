"""Rewrite policies and size+time rolling files."""

import os
import tempfile

from log4p2 import (
    ConsoleAppender,
    Level,
    MapRewritePolicy,
    PatternLayout,
    RewriteAppender,
    SizeAndTimeBasedAppender,
    getLogger,
)

tmp = tempfile.mkdtemp()
log_file = os.path.join(tmp, "app.log")

logger = getLogger("demo.rolling")
logger.setLevel(Level.DEBUG)
logger.setAdditivity(False)

# Rolls when the file passes 200 bytes or a day elapses, whichever comes first.
rolling = SizeAndTimeBasedAppender(
    log_file,
    maxBytes=200,
    when="d",
    backupCount=3,
    compress=True,
    layout=PatternLayout("%d{ISO8601} %-5p %m%n"),
)
logger.addAppender(rolling)

for i in range(25):
    logger.info("request %03d processed", i)

rolling.stop()
print("rotated files:")
for name in sorted(os.listdir(tmp)):
    print(" ", name)

# RewriteAppender injects request-scoped context before writing.
audit = getLogger("demo.audit")
audit.setLevel(Level.INFO)
audit.setAdditivity(False)
audit.addAppender(
    RewriteAppender(
        ConsoleAppender(PatternLayout("%X{request_id} %m")),
        policy=MapRewritePolicy({"request_id": "req-42", "service": "checkout"}),
    )
)
audit.info("order placed")
