import io

from log4p import (
    ConsoleAppender,
    FileAppender,
    HTMLLayout,
    Level,
    LogRecord,
    MemoryAppender,
    PatternLayout,
    RotatingFileAppender,
    ThresholdFilter,
)


def record(message="hello", level=Level.INFO):
    return LogRecord(name="app", level=level, message=message)


def test_memory_appender_captures_events():
    appender = MemoryAppender(PatternLayout("%p %m"))
    appender.doAppend(record())
    appender.doAppend(record("bye", level=Level.WARN))
    assert appender.getEvents() == ["INFO hello", "WARN bye"]
    assert [r.getMessage() for r in appender.getRecords()] == ["hello", "bye"]


def test_memory_appender_max_size_keeps_recent():
    appender = MemoryAppender(PatternLayout("%m"), maxSize=2)
    for i in range(4):
        appender.doAppend(record(str(i)))
    assert appender.getEvents() == ["2", "3"]


def test_memory_appender_clear():
    appender = MemoryAppender()
    appender.doAppend(record())
    appender.clear()
    assert appender.getEvents() == []
    assert appender.getRecords() == []


def test_console_appender_immediate_flush_disabled():
    class _Spy(io.StringIO):
        flushes = 0

        def flush(self):
            type(self).flushes += 1
            return super().flush()

    buf = _Spy()
    appender = ConsoleAppender(PatternLayout("%m"), stream=buf, immediateFlush=False)
    appender.doAppend(record())
    assert _Spy.flushes == 0
    appender.flush()
    assert _Spy.flushes == 1


def test_console_appender_default_flushes():
    class _Spy(io.StringIO):
        flushes = 0

        def flush(self):
            type(self).flushes += 1
            return super().flush()

    buf = _Spy()
    ConsoleAppender(PatternLayout("%m"), stream=buf).doAppend(record())
    assert _Spy.flushes == 1


def test_console_appender_writes_to_stream():
    buf = io.StringIO()
    appender = ConsoleAppender(PatternLayout("%p %m"), stream=buf)
    appender.doAppend(record())
    assert buf.getvalue() == "INFO hello\n"


def test_console_appender_adds_trailing_newline_once():
    buf = io.StringIO()
    appender = ConsoleAppender(PatternLayout("%m%n"), stream=buf)
    appender.doAppend(record())
    assert buf.getvalue() == "hello\n"


def test_appender_threshold_blocks():
    buf = io.StringIO()
    appender = ConsoleAppender(PatternLayout("%m"), stream=buf, threshold="WARN")
    appender.doAppend(record(level=Level.INFO))
    appender.doAppend(record(message="boom", level=Level.ERROR))
    assert buf.getvalue() == "boom\n"


def test_appender_filter_blocks():
    buf = io.StringIO()
    appender = ConsoleAppender(PatternLayout("%m"), stream=buf)
    appender.addFilter(ThresholdFilter("ERROR"))
    appender.doAppend(record(level=Level.INFO))
    appender.doAppend(record(message="boom", level=Level.ERROR))
    assert buf.getvalue() == "boom\n"


def test_appender_swallows_errors_without_raising():
    class Broken(ConsoleAppender):
        def append(self, rec):
            raise RuntimeError("nope")

    appender = Broken(stream=io.StringIO())
    appender.handleError = lambda rec: None
    appender.doAppend(record())  # must not raise


def test_file_appender(tmp_path):
    path = tmp_path / "sub" / "app.log"
    appender = FileAppender(str(path), PatternLayout("%p %m"))
    appender.doAppend(record("first"))
    appender.doAppend(record("second"))
    appender.stop()
    text = path.read_text()
    assert "INFO first" in text
    assert "INFO second" in text


def test_file_appender_truncate(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("old\n")
    appender = FileAppender(str(path), PatternLayout("%m"), append=False)
    appender.doAppend(record("new"))
    appender.stop()
    assert path.read_text() == "new\n"


def test_rotating_appender_rotates(tmp_path):
    path = tmp_path / "rot.log"
    appender = RotatingFileAppender(
        str(path), maxBytes=40, backupCount=3, layout=PatternLayout("%m"), append=False
    )
    for i in range(20):
        appender.doAppend(record(f"line-{i:02d}"))
    appender.stop()
    assert path.exists()
    assert (tmp_path / "rot.log.1").exists()
    assert (tmp_path / "rot.log.2").exists()
    assert not (tmp_path / "rot.log.4").exists()


def test_rotating_appender_respects_backup_count(tmp_path):
    path = tmp_path / "rot.log"
    appender = RotatingFileAppender(
        str(path), maxBytes=20, backupCount=2, layout=PatternLayout("%m"), append=False
    )
    for i in range(30):
        appender.doAppend(record(f"line-{i:02d}"))
    appender.stop()
    assert (tmp_path / "rot.log.1").exists()
    assert (tmp_path / "rot.log.2").exists()
    assert not (tmp_path / "rot.log.3").exists()


def test_appender_lifecycle_flags(tmp_path):
    appender = FileAppender(str(tmp_path / "x.log"))
    assert not appender.isStarted()
    appender.start()
    assert appender.isStarted()
    appender.stop()
    assert not appender.isStarted()


def test_file_appender_writes_html_header_and_footer(tmp_path):
    path = tmp_path / "page.html"
    appender = FileAppender(str(path), layout=HTMLLayout(), append=False)
    appender.doAppend(record("first"))
    appender.stop()
    text = path.read_text()
    assert text.startswith("<!DOCTYPE html>")
    assert "<tr>" in text
    assert text.rstrip().endswith("</html>")


def test_console_appender_html_header_on_start_footer_on_stop():
    buf = io.StringIO()
    appender = ConsoleAppender(HTMLLayout(), stream=buf)
    appender.start()
    appender.doAppend(record("x"))
    appender.stop()
    text = buf.getvalue()
    assert text.startswith("<!DOCTYPE html>")
    assert text.rstrip().endswith("</html>")


def test_file_appender_html_header_not_duplicated_on_append(tmp_path):
    path = tmp_path / "page2.html"
    first = FileAppender(str(path), layout=HTMLLayout(), append=True)
    first.doAppend(record("one"))
    first.stop()
    second = FileAppender(str(path), layout=HTMLLayout(), append=True)
    second.doAppend(record("two"))
    second.stop()
    assert path.read_text().count("<!DOCTYPE html>") == 1

