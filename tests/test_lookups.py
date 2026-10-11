import pytest

from log4p import Level, LogRecord, Marker, PatternLayout
from log4p import config as log4p_config


def record(context=None, marker=None):
    return LogRecord(
        name="app", level=Level.INFO, message="hi", context=context or {}, marker=marker
    )


def render(pattern, rec):
    return PatternLayout(pattern).format(rec)


def test_ctx_lookup():
    assert render("${ctx:req}", record({"req": "abc"})) == "abc"


def test_ctx_lookup_default():
    assert render("${ctx:req:-none}", record()) == "none"
    assert render("${ctx:req:-none}", record({"req": "abc"})) == "abc"


def test_env_lookup(monkeypatch):
    monkeypatch.setenv("LOG4P_TEST", "yes")
    assert render("${env:LOG4P_TEST}", record()) == "yes"
    assert render("${env:MISSING:-fallback}", record()) == "fallback"


def test_sys_lookup():
    assert render("${sys:version_info[0]}", record()) == ""
    assert render("${sys:argv}", record()) != ""


def test_marker_lookup():
    assert render("${marker}", record(marker=Marker("SQL"))) == "SQL"
    assert render("${marker}", record()) == ""


def test_unknown_lookup_is_literal():
    assert render("${bundle:key}", record()) == "${bundle:key}"


def test_dollar_escape_renders_literal_lookup():
    assert render("$${ctx:key}", record({"ctx": "x"})) == "${ctx:key}"
    assert render("$${env:HOME}", record()) == "${env:HOME}"


def test_single_dollar_collapses():
    assert render("$$", record()) == "$"
    assert render("cost $$5", record()) == "cost $5"


def test_config_escape_keeps_literal(monkeypatch):
    monkeypatch.setenv("APP", "svc")
    out = log4p_config.substitute_variables("$${env:APP} ${env:APP}")
    assert out == "$${env:APP} svc"


def test_lookup_mixed_with_pattern():
    rec = record({"user": "klyne"})
    assert render("[${ctx:user}] %p %m", rec) == "[klyne] INFO hi"


def test_unbalanced_dollar_is_literal():
    assert render("cost $5", record()) == "cost $5"
    assert render("$ {x}", record()) == "$ {x}"


def test_lookup_inside_selector():
    rec = record({"tenant": "acme"})
    assert render("%notEmpty{${ctx:tenant}}", rec) == "acme"
    assert render("%notEmpty{${ctx:missing}}", rec) == ""


def test_ctx_lookup_survives_config_substitution():
    spec = {"pattern": "${env:APP} ${ctx:req}", "class": "PatternLayout"}
    result = log4p_config.substitute_variables(spec)
    assert result["pattern"].endswith("${ctx:req}")


def test_ctx_lookup_in_config_layout(monkeypatch):
    import io

    from log4p.logger import getLoggerManager

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "${ctx:tid} %m"},
                }
            },
        }
    )
    from log4p import MDC

    MDC.put("tid", "T1")
    getLoggerManager().root.info("hello")
    assert buf.getvalue() == "T1 hello\n"


@pytest.mark.parametrize("pattern", ["${ctx:missing}", "${env:__NOPE__}"])
def test_empty_lookups_render_empty(pattern):
    assert render(pattern, record()) == ""
