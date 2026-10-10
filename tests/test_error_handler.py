import io

from log4p import (
    ConsoleAppender,
    ErrorHandler,
    FallbackErrorHandler,
    Level,
    LogRecord,
    PatternLayout,
    getLogger,
)
from log4p.logger import getLoggerManager


class FailingAppender(ConsoleAppender):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = 0

    def append(self, record):
        self.calls += 1
        raise IOError("disk gone")


def record(message="hi"):
    return LogRecord(name="app", level=Level.ERROR, message=message)


def setup_function(_):
    getLoggerManager().clear()
    getLoggerManager().warn_on_no_appenders = False


def teardown_function(_):
    getLoggerManager().clear()


def test_default_error_handler_writes_to_stderr(capsys):
    appender = FailingAppender(stream=io.StringIO())
    appender.doAppend(record())  # must not raise
    err = capsys.readouterr().err
    assert "error appending record" in err
    assert "disk gone" in err


def test_error_handler_can_be_disabled(capsys):
    appender = FailingAppender(stream=io.StringIO())
    appender.setErrorHandler(ErrorHandler(enabled=False))
    appender.doAppend(record())
    assert capsys.readouterr().err == ""


def test_fallback_error_handler_swaps_in_backup(capsys):
    primary = FailingAppender(stream=io.StringIO(), name="primary")
    backup_buf = io.StringIO()
    backup = ConsoleAppender(PatternLayout("%m"), stream=backup_buf, name="backup")

    fallback = FallbackErrorHandler()
    fallback.setAppender(primary)
    fallback.setBackupAppender(backup)
    primary.setErrorHandler(fallback)

    logger = getLogger("svc")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(primary)

    logger.error("first")   # triggers failure -> fallback activates
    assert primary not in logger.getAppenders()
    assert backup in logger.getAppenders()
    assert fallback.isActivated()

    logger.error("second")  # now routed to the backup
    assert backup_buf.getvalue() == "second\n"
    assert "FallbackErrorHandler activated" in capsys.readouterr().err


def test_fallback_without_backups_does_not_activate(capsys):
    primary = FailingAppender(stream=io.StringIO())
    fallback = FallbackErrorHandler()
    fallback.setAppender(primary)
    primary.setErrorHandler(fallback)

    logger = getLogger("svc")
    logger.setAdditivity(False)
    logger.setLevel("DEBUG")
    logger.addAppender(primary)

    logger.error("x")
    assert not fallback.isActivated()
    assert primary in logger.getAppenders()
