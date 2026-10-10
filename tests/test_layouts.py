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


