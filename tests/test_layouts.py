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
