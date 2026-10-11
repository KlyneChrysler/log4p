import json
import re

from log4p import JSONLayout, Level, LogRecord, PatternLayout, SimpleLayout


def make_record(msg="hello %s", args=("world",), name="app.db"):
    return LogRecord(
        name=name,
        level=Level.INFO,
        message=msg,
        args=args,
        pathname="/tmp/x/module.py",
        lineno=42,
        funcName="do_work",
        context={"req": "r-1"},
        ndc="outer inner",
    )


def test_simple_layout():
    assert SimpleLayout().format(make_record()) == "INFO - hello world"


def test_pattern_basic():
    layout = PatternLayout("%p %c - %m%n")
    assert layout.format(make_record()) == "INFO app.db - hello world\n"


def test_pattern_logger_precision():
    layout = PatternLayout("%c{1} | %c{2}")
    assert layout.format(make_record()) == "db | app.db"


def test_pattern_width_and_truncate():
    assert PatternLayout("[%-5p]").format(make_record()) == "[INFO ]"
    assert PatternLayout("[%5p]").format(make_record()) == "[ INFO]"
    # log4j max-width keeps the *end* of the field.
    assert PatternLayout("%.30m").format(make_record()) == "hello world"
    assert PatternLayout("%.5m").format(make_record()) == "world"
    assert PatternLayout("%.6c").format(make_record()) == "app.db"


def test_pattern_field_converters():
    record = make_record()
    assert PatternLayout("%F").format(record) == "module.py"
    assert PatternLayout("%L").format(record) == "42"
    assert PatternLayout("%M").format(record) == "do_work"
    assert PatternLayout("%C").format(record) == "module"
    assert PatternLayout("%t").format(record)
    assert PatternLayout("%r").format(record).isdigit()


def test_pattern_mdc_and_ndc():
    record = make_record()
    assert PatternLayout("%X{req}").format(record) == "r-1"
    assert PatternLayout("%X{missing}").format(record) == ""
    assert PatternLayout("%x").format(record) == "outer inner"
    assert json.loads(PatternLayout("%X").format(record)) == {"req": "r-1"}


def test_pattern_literal_percent_and_newline():
    assert PatternLayout("100%% done%n").format(make_record()) == "100% done\n"


def test_pattern_raw_long_names():
    assert PatternLayout("%level %logger %message").format(make_record()) == (
        "INFO app.db hello world"
    )


def test_pattern_strftime_style_date():
    out = PatternLayout("%d{%Y-%m-%d}").format(make_record())
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", out)


def test_pattern_java_style_date():
    out = PatternLayout("%d{HH:mm:ss}").format(make_record())
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", out)


def test_pattern_millis():
    out = PatternLayout("%d{yyyy-MM-dd HH:mm:ss,SSS}").format(make_record())
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}", out)


def test_pattern_iso8601_preset():
    out = PatternLayout("%d{ISO8601}").format(make_record())
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", out)


def test_json_layout():
    data = json.loads(JSONLayout().format(make_record()))
    assert data["level"] == "INFO"
    assert data["logger"] == "app.db"
    assert data["message"] == "hello world"
    assert data["line"] == 42
    assert data["context"] == {"req": "r-1"}
    assert data["ndc"] == "outer inner"


def test_json_layout_includes_exception():
    try:
        raise ValueError("bad")
    except ValueError:
        import sys

        record = LogRecord(
            name="x", level=Level.ERROR, message="oops", exc_info=sys.exc_info()
        )
    data = json.loads(JSONLayout().format(record))
    assert "ValueError: bad" in data["exception"]
    assert JSONLayout().ignoresExceptions is True


def test_json_layout_compact():
    out = JSONLayout(compact=True).format(make_record())
    assert ", " not in out
    assert '": "' not in out


def test_json_layout_include_stacktrace_toggle():
    try:
        raise ValueError("bad")
    except ValueError:
        import sys

        record = LogRecord(
            name="x", level=Level.ERROR, message="oops", exc_info=sys.exc_info()
        )
    assert "exception" not in json.loads(
        JSONLayout(includeStacktrace=False).format(record)
    )


def test_json_layout_properties_and_location():
    data = json.loads(
        JSONLayout(
            properties={"app": "svc", "level": "KEEP"},
            includeLocation=True,
        ).format(make_record())
    )
    assert data["app"] == "svc"
    assert data["level"] == "INFO"
    assert data["source"]["file"] == "module.py"
    assert data["source"]["method"] == "do_work"


def test_json_layout_event_eol():
    out = JSONLayout(eventEol=True).format(make_record())
    assert out.endswith("\n")
    assert not JSONLayout().format(make_record()).endswith("\n")


def test_message_formatting_dict_args():
    record = LogRecord(
        name="x", level=Level.INFO, message="%(a)s-%(b)s", args={"a": 1, "b": 2}
    )
    assert record.getMessage() == "1-2"


def test_message_formatting_bad_args_does_not_raise():
    record = LogRecord(name="x", level=Level.INFO, message="%d", args=("no",))
    assert "no" in record.getMessage()


def test_pattern_new_converters_pid_thread_throwable():
    record = make_record()
    import os
    import threading

    assert PatternLayout("%pid").format(record) == str(os.getpid())
    assert PatternLayout("%T").format(record) == str(record.thread)
    assert PatternLayout("%tid").format(record) == str(record.thread)
    assert PatternLayout("%t").format(record) == threading.current_thread().name


def test_pattern_exception_converters():
    record = LogRecord(name="x", level=Level.ERROR, message="oops")
    record.exc_text = "Traceback (most recent call last):\nValueError: bad"
    assert "ValueError: bad" in PatternLayout("%throwable").format(record)
    assert "ValueError: bad" in PatternLayout("%ex").format(record)
    assert "ValueError: bad" in PatternLayout("%exception").format(record)


def test_pattern_stack_converter():
    record = LogRecord(name="x", level=Level.INFO, message="m", stack_info="STACK HERE")
    assert PatternLayout("%stack").format(record) == "STACK HERE"
    assert PatternLayout("%stack").format(make_record()) == ""


def test_logfmt_layout():
    from log4p import LogfmtLayout

    out = LogfmtLayout().format(make_record())
    assert "level=info" in out
    assert "logger=app.db" in out
    assert 'msg="hello world"' in out
    assert "req=r-1" in out


def test_logfmt_layout_quotes_special_values():
    from log4p import LogfmtLayout

    record = LogRecord(name="x", level=Level.INFO, message="a b=c", args=None)
    out = LogfmtLayout(timestamp=False).format(record)
    assert 'msg="a b=c"' in out


def test_xml_layout():
    from log4p import XMLLayout

    out = XMLLayout().format(make_record())
    assert out.startswith("<event ")
    assert 'level="INFO"' in out
    assert "<message>hello world</message>" in out
    assert '<data name="req">r-1</data>' in out
    assert out.endswith("</event>")


def test_xml_layout_escapes_body():
    from log4p import XMLLayout

    record = LogRecord(name="x", level=Level.INFO, message="a<b>&c", args=None)
    out = XMLLayout().format(record)
    assert "a&lt;b&gt;&amp;c" in out


def test_html_layout_header_body_footer():
    from log4p import HTMLLayout

    layout = HTMLLayout(title="t")
    assert layout.header().startswith("<!DOCTYPE html>")
    row = layout.format(make_record())
    assert row.startswith("<tr>") and row.endswith("</tr>\n")
    assert "hello world" in row
    assert layout.footer().startswith("</tbody>")


def test_pattern_msg_alias():
    assert PatternLayout("%msg").format(make_record()) == "hello world"


def test_pattern_replace_selector():
    assert PatternLayout(r"%replace{%msg}{\s}{_}").format(make_record()) == "hello_world"
    assert (
        PatternLayout(r"%replace{%logger %msg}{\.}{/}").format(make_record())
        == "app/db hello world"
    )


def test_pattern_equals_selector():
    tagged = make_record()
    from log4p import getMarker

    tagged.marker = getMarker("SQL")
    assert PatternLayout("%equals{[%marker]}{[SQL]}{!}").format(tagged) == "!"
    assert PatternLayout("%equals{[%marker]}{[NO]}{!}").format(tagged) == "[SQL]"


def test_pattern_equals_ignore_case_selector():
    tagged = make_record()
    from log4p import getMarker

    tagged.marker = getMarker("Sql")
    assert PatternLayout("%equalsIgnoreCase{%marker}{sql}{OK}").format(tagged) == "OK"


def test_pattern_not_empty_selector():
    from log4p import getMarker

    record = make_record()
    assert PatternLayout("%notEmpty{[%marker]}END").format(record) == "END"
    record.marker = getMarker("SQL")
    assert PatternLayout("%notEmpty{[%marker]}END").format(record) == "[SQL]END"


def test_pattern_style_selector():
    out = PatternLayout("%style{%msg}{bold,cyan}").format(make_record())
    assert out == "\x1b[1;36mhello world\x1b[0m"


def test_pattern_color_shorthand():
    assert PatternLayout("%red{%msg}").format(make_record()) == "\x1b[31mhello world\x1b[0m"


def test_pattern_highlight_by_level():
    record = make_record()
    assert PatternLayout("%highlight{%p}").format(record) == "\x1b[32mINFO\x1b[0m"
    override = PatternLayout("%highlight{%-5p}{ERROR=red,INFO=blue}").format(record)
    assert override == "\x1b[34mINFO \x1b[0m"


def test_pattern_replace_missing_args_is_literal():
    assert PatternLayout("%replace{%msg}").format(make_record()) == "%replace{%msg}"


def test_pattern_logger_abbreviation():
    record = make_record(name="org.apache.commons.Foo")
    assert PatternLayout("%c{1.}").format(record) == "o.a.c.Foo"
    assert PatternLayout("%c{2.}").format(record) == "o.a.commons.Foo"
    assert PatternLayout("%c{.}").format(record) == "o.a.c.Foo"
    assert PatternLayout("%c{2}").format(record) == "commons.Foo"


def test_pattern_max_len():
    long = make_record(msg="x" * 40, args=())
    assert PatternLayout("%maxLen{%m}{10}").format(long) == "x" * 10
    assert PatternLayout("%maxLen{%m}{30}").format(long) == "x" * 27 + "..."
    short = make_record()
    assert PatternLayout("%maxLen{%m}{30}").format(short) == "hello world"


def test_pattern_encode():
    record = make_record(msg='a"b<c>&', args=())
    assert PatternLayout("%encode{%m}{HTML}").format(record) == "a&quot;b&lt;c&gt;&amp;"
    assert PatternLayout("%encode{%m}{XML}").format(record) == "a&quot;b&lt;c&gt;&amp;"
    assert PatternLayout("%encode{%m}{JSON}").format(record) == 'a\\"b<c>&'
    crlf = make_record(msg="a\nb", args=())
    assert PatternLayout("%encode{%m}{CRLF}").format(crlf) == "a\\nb"


def test_pattern_map_converter():
    record = make_record()
    assert PatternLayout("%K{req}").format(record) == "r-1"
    assert json.loads(PatternLayout("%K").format(record)) == {"req": "r-1"}


def test_pattern_message_map_converter():
    from log4p import MapMessage

    rec = LogRecord(name="a", level=Level.INFO, message=MapMessage({"svc": "checkout"}))
    assert PatternLayout("%map{svc}").format(rec) == "checkout"
    assert PatternLayout("%map{missing:-none}").format(rec) == "none"
    assert json.loads(PatternLayout("%map").format(rec)) == {"svc": "checkout"}
    plain = make_record()
    assert PatternLayout("%map{svc}").format(plain) == ""


def test_pattern_enc_alias():
    rec = LogRecord(name="a", level=Level.INFO, message="<x>&")
    assert PatternLayout("%enc{%m}{HTML}").format(rec) == "&lt;x&gt;&amp;"
    assert PatternLayout("%encode{%m}{HTML}").format(rec) == "&lt;x&gt;&amp;"



def test_pattern_location_converter():
    record = make_record()
    assert PatternLayout("%l").format(record) == "module.do_work(module.py:42)"


def test_pattern_nanos_converter():
    record = make_record()
    assert PatternLayout("%N").format(record).isdigit()


def test_pattern_env_converter(monkeypatch):
    monkeypatch.setenv("LOG4P_TEST_VAR", "abc")
    record = make_record()
    assert PatternLayout("%env{LOG4P_TEST_VAR}").format(record) == "abc"
    assert PatternLayout("%env{LOG4P_MISSING}").format(record) == ""
    assert PatternLayout("%env{LOG4P_MISSING:-fallback}").format(record) == "fallback"


def test_pattern_marker_simple_name():
    from log4p import getMarker

    record = make_record()
    record.marker = getMarker("SQL")
    assert PatternLayout("%markerSimpleName").format(record) == "SQL"
    assert PatternLayout("%marker").format(record) == "SQL"


def test_pattern_converter_aliases():
    record = make_record()
    assert PatternLayout("%threadName").format(record) == record.threadName
    assert PatternLayout("%threadId").format(record) == str(record.thread)
    assert PatternLayout("%processId").format(record) == str(record.process)
    assert PatternLayout("%hostName").format(record) == PatternLayout("%h").format(record)


def test_pattern_sequence_number():
    first = make_record()
    second = make_record()
    assert int(PatternLayout("%seq").format(second)) == int(PatternLayout("%seq").format(first)) + 1
    assert PatternLayout("%sequenceNumber").format(first) == str(first.sequence)
    assert PatternLayout("%sn").format(first) == str(first.sequence)


def test_pattern_structured_data():
    record = make_record()
    assert PatternLayout("%sd").format(record) == '[log4p@32473 req="r-1"]'
    assert PatternLayout("%sd{myapp@1}").format(record) == '[myapp@1 req="r-1"]'
    assert PatternLayout("%structuredData").format(record) == '[log4p@32473 req="r-1"]'


def test_pattern_structured_data_escapes():
    record = make_record()
    record.context = {"k": 'a"b]c\\d'}
    assert PatternLayout("%sd").format(record) == '[log4p@32473 k="a\\"b\\]c\\\\d"]'


def _exception_record():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = make_record(args=())
        record.exc_info = sys.exc_info()
        record.exc_text = None
        return record


def test_pattern_throwable_short():
    record = _exception_record()
    assert PatternLayout("%throwable{short}").format(record) == "ValueError: boom"
    assert PatternLayout("%rEx{short}").format(record) == "ValueError: boom"
    assert PatternLayout("%xEx{short}").format(record) == "ValueError: boom"


def test_pattern_throwable_full_default():
    record = _exception_record()
    assert "ValueError: boom" in PatternLayout("%throwable").format(record)


def test_pattern_throwable_nolines():
    record = _exception_record()
    out = PatternLayout("%throwable{nolines}").format(record)
    assert "ValueError: boom" in out
    assert 'File "' not in out


def test_pattern_throwable_depth():
    record = _exception_record()
    out = PatternLayout("%throwable{depth(2)}").format(record)
    assert len(out.splitlines()) == 2


def test_pattern_throwable_empty_without_exception():
    record = make_record()
    assert PatternLayout("%throwable").format(record) == ""


def test_pattern_date_timezone_utc():
    import time

    record = make_record()
    record.created = 1_700_000_000.0
    expected = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(record.created))
    assert PatternLayout("%d{yyyy-MM-dd HH:mm:ss}{UTC}").format(record) == expected


def test_pattern_date_fixed_offset():
    import time

    record = make_record()
    record.created = 1_700_000_000.0
    expected = time.strftime("%H:%M:%S", time.gmtime(record.created + 7200))
    assert PatternLayout("%d{HH:mm:ss}{GMT+2}").format(record) == expected


def test_pattern_date_iana_timezone():
    import datetime

    record = make_record()
    record.created = 1_700_000_000.0
    dt = datetime.datetime.fromtimestamp(
        record.created, datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    )
    expected = dt.strftime("%H:%M")
    assert PatternLayout("%d{HH:mm}{+05:30}").format(record) == expected


def test_pattern_date_invalid_timezone_falls_back_to_local():
    record = make_record()
    out = PatternLayout("%d{HH:mm}").format(record)
    assert PatternLayout("%d{HH:mm}{Not/AZone}").format(record) == out


def test_marker_pattern_selector(monkeypatch):
    from log4p import MarkerPatternSelector, getMarker

    selector = MarkerPatternSelector(
        {"SQL": "SQL> %m", "AUDIT": "AUD> %m"}, default="%m"
    )
    layout = PatternLayout("%m", selector=selector)

    plain = LogRecord(name="a", level=Level.INFO, message="q")
    assert layout.format(plain) == "q"

    tagged = LogRecord(name="a", level=Level.INFO, message="q", marker=getMarker("SQL"))
    assert layout.format(tagged) == "SQL> q"


def test_marker_pattern_selector_hierarchy_and_default():
    from log4p import MarkerPatternSelector, getMarker

    parent = getMarker("ACCESS")
    child = getMarker("ACCESS.DB", [parent])
    selector = MarkerPatternSelector({"ACCESS": "A> %m"})
    layout = PatternLayout("%m", selector=selector)

    rec = LogRecord(name="a", level=Level.INFO, message="hi", marker=child)
    assert layout.format(rec) == "A> hi"

    untagged = LogRecord(name="a", level=Level.INFO, message="hi")
    assert layout.format(untagged) == "hi"


def test_pattern_layout_header_footer():
    layout = PatternLayout("%m%n", header="--- start ---\n", footer="--- end ---\n")
    assert layout.header() == "--- start ---\n"
    assert layout.footer() == "--- end ---\n"
    assert PatternLayout("%m%n").header() is None


def test_pattern_layout_always_write_exceptions_false():
    import io

    from log4p import ConsoleAppender, getLogger
    from log4p.logger import getLoggerManager

    getLoggerManager().clear()
    buf = io.StringIO()
    appender = ConsoleAppender(
        PatternLayout("%m%n", alwaysWriteExceptions=False), stream=buf
    )
    logger = getLogger("layout.exc")
    logger.setLevel("INFO")
    logger.addAppender(appender)
    try:
        raise ValueError("nope")
    except ValueError:
        logger.exception("failed")
    getLoggerManager().clear()
    out = buf.getvalue()
    assert "failed" in out
    assert "ValueError" not in out


def test_pattern_layout_always_write_exceptions_true_default():
    import io

    from log4p import ConsoleAppender, getLogger
    from log4p.logger import getLoggerManager

    getLoggerManager().clear()
    buf = io.StringIO()
    appender = ConsoleAppender(PatternLayout("%m%n"), stream=buf)
    logger = getLogger("layout.exc2")
    logger.setLevel("INFO")
    logger.addAppender(appender)
    try:
        raise ValueError("kaboom")
    except ValueError:
        logger.exception("failed")
    getLoggerManager().clear()
    assert "ValueError: kaboom" in buf.getvalue()





