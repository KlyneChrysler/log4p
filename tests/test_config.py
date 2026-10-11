import io
import json

import pytest

from log4p import config as log4p_config
from log4p import getLogger, getMarker, getRootLogger
from log4p.logger import getLoggerManager


@pytest.fixture(autouse=True)
def _isolate():
    getLoggerManager().clear()
    getLoggerManager().warn_on_no_appenders = False
    yield
    getLoggerManager().clear()


def test_dictconfig_builds_appender_and_levels():
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "WARN"},
            "loggers": {"app": {"level": "DEBUG", "appenders": ["console"], "additive": False}},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%p %c - %m"},
                }
            },
        }
    )
    app = getLogger("app")
    assert app.getLevel().name == "DEBUG"
    assert app.getAdditivity() is False
    app.debug("dbg")
    getRootLogger().error("root-level")
    out = buf.getvalue()
    assert "DEBUG app - dbg" in out
    assert out.count("root-level") == 0
    assert getLogger("app").getAppenders()[0].getLayout().pattern == "%p %c - %m"


def test_dictconfig_wires_filters_and_threshold():
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "DEBUG", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%p %m"},
                    "threshold": "WARN",
                    "filters": [{"class": "RegexFilter", "pattern": "keep"}],
                }
            },
        }
    )
    logger = getLogger()
    logger.info("keep me")
    logger.error("drop me")
    logger.error("keep this too")
    out = buf.getvalue()
    assert "keep me" not in out
    assert "drop me" not in out
    assert "keep this too" in out


def test_dictconfig_file_appender(tmp_path):
    path = tmp_path / "cfg.log"
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["file"]},
            "appenders": {
                "file": {
                    "class": "FileAppender",
                    "filename": str(path),
                    "layout": {"class": "SimpleLayout"},
                }
            },
        }
    )
    getRootLogger().info("written")
    getLoggerManager().shutdown()
    assert "INFO - written" in path.read_text()


def test_dictconfig_unknown_component_raises():
    with pytest.raises(ValueError):
        log4p_config.dictConfig(
            {"appenders": {"x": {"class": "NoSuchAppender"}}}
        )


def test_dictconfig_unknown_appender_reference_raises():
    with pytest.raises(ValueError):
        log4p_config.dictConfig({"root": {"appenders": ["missing"]}})


def test_fileconfig_yaml(tmp_path):
    buf = io.StringIO()
    cfg = tmp_path / "log4p.yaml"
    cfg.write_text(
        """
root:
  level: DEBUG
  appenders: [console]
appenders:
  console:
    class: ConsoleAppender
    target: stderr
    layout:
      class: PatternLayout
      pattern: "%p %m"
"""
    )
    log4p_config.fileConfig(str(cfg))
    # redirect by swapping the appender stream after config
    appender = getRootLogger().getAppenders()[0]
    appender._stream = buf
    getRootLogger().info("from-yaml")
    assert buf.getvalue() == "INFO from-yaml\n"


def test_fileconfig_json(tmp_path):
    cfg = tmp_path / "log4p.json"
    cfg.write_text(
        json.dumps(
            {
                "root": {"level": "INFO", "appenders": ["console"]},
                "appenders": {
                    "console": {
                        "class": "ConsoleAppender",
                        "layout": {"class": "JSONLayout"},
                    }
                },
            }
        )
    )
    buf = io.StringIO()
    log4p_config.fileConfig(str(cfg))
    getRootLogger().getAppenders()[0]._stream = buf
    getRootLogger().info("json-msg")
    payload = json.loads(buf.getvalue())
    assert payload["message"] == "json-msg"
    assert payload["level"] == "INFO"


def test_basic_config_console():
    buf = io.StringIO()
    appender = log4p_config.basicConfig(level="INFO", stream=buf, format="%p %m")
    assert appender in getRootLogger().getAppenders()
    getRootLogger().warning("hey")
    assert buf.getvalue() == "WARN hey\n"


def test_basic_config_file(tmp_path):
    path = tmp_path / "basic.log"
    log4p_config.basicConfig(level="DEBUG", filename=str(path), format="%m")
    getRootLogger().debug("to-file")
    getLoggerManager().shutdown()
    assert path.read_text() == "to-file\n"


def test_appender_instance_passed_directly():
    from log4p import ConsoleAppender, PatternLayout

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": ConsoleAppender(PatternLayout("%m"), stream=buf),
            },
        }
    )
    getRootLogger().info("direct")
    assert buf.getvalue() == "direct\n"


def test_dictconfig_async_appender_wraps_delegate():
    from log4p import AsyncAppender

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["async"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                },
                "async": {"class": "AsyncAppender", "appender": "console"},
            },
        }
    )
    root = getRootLogger()
    app = root.getAppenders()[0]
    assert isinstance(app, AsyncAppender)
    root.info("through async")
    app.flush()
    app.stop()
    assert buf.getvalue() == "through async\n"


def test_dictconfig_async_requires_prior_delegate():
    with pytest.raises(ValueError):
        log4p_config.dictConfig(
            {
                "appenders": {
                    "async": {"class": "AsyncAppender", "appender": "missing"},
                }
            }
        )


def test_dictconfig_fallback_error_handler():
    log4p_config.dictConfig(
        {
            "root": {"level": "ERROR", "appenders": ["primary"]},
            "appenders": {
                "backup": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "SimpleLayout"},
                },
                "primary": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "SimpleLayout"},
                    "errorHandler": {
                        "class": "FallbackErrorHandler",
                        "backup": ["backup"],
                    },
                },
            },
        }
    )
    primary = getRootLogger().getAppenders()[0]
    handler = primary.getErrorHandler()
    assert handler.isActivated() is False
    assert len(handler.getBackups()) == 1


def test_dictconfig_timed_rotating(tmp_path):
    path = tmp_path / "t.log"
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["timed"]},
            "appenders": {
                "timed": {
                    "class": "TimedRotatingFileAppender",
                    "filename": str(path),
                    "when": "h",
                    "backupCount": 3,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    getRootLogger().info("timed")
    getLoggerManager().shutdown()
    assert path.read_text() == "timed\n"


def test_dictconfig_substitutes_env_and_sys(monkeypatch):
    monkeypatch.setenv("LOG4P_TEST_LEVEL", "DEBUG")
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "${env:LOG4P_TEST_LEVEL}", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%p %m"},
                }
            },
        }
    )
    assert getRootLogger().getLevel().name == "DEBUG"


def test_dictconfig_substitution_default_value(monkeypatch):
    monkeypatch.delenv("LOG4P_MISSING", raising=False)
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "${env:LOG4P_MISSING:-WARN}", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "SimpleLayout"},
                }
            },
        }
    )
    assert getRootLogger().getLevel().name == "WARN"


def test_substitute_variables_recurses():
    result = log4p_config.substitute_variables(
        {"a": ["${env:LOG4P_NO_SUCH:-x}"], "b": {"c": "${sys:maxsize}"}}
    )
    assert result["a"] == ["x"]
    assert result["b"]["c"]


def test_dictconfig_can_disable_substitution():
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "substitute": False,
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "${keep} %m"},
                }
            },
        }
    )
    getRootLogger().info("v")
    assert "${keep} v" in buf.getvalue()


def test_dictconfig_builds_logfmt_layout():
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "LogfmtLayout", "timestamp": False},
                }
            },
        }
    )
    getRootLogger().info("hello")
    assert "level=info" in buf.getvalue()
    assert "msg=hello" in buf.getvalue()


def test_dictconfig_builds_marker_filter():
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                    "filters": [{"class": "MarkerFilter", "marker": "SQL"}],
                }
            },
        }
    )
    root = getRootLogger()
    root.info("tagged", marker=getMarker("SQL"))
    root.info("untagged")
    assert "tagged" in buf.getvalue()
    assert "untagged" not in buf.getvalue()


def test_dictconfig_builds_nested_and_filter():
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "DEBUG", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%p %m"},
                    "filters": [
                        {
                            "class": "AndFilter",
                            "filters": [
                                {"class": "ThresholdFilter", "level": "WARN"},
                                {"class": "RegexFilter", "pattern": "boom"},
                            ],
                        }
                    ],
                }
            },
        }
    )
    root = getRootLogger()
    root.warn("boom now")
    root.warn("fine")
    root.info("boom but low")
    out = buf.getvalue()
    assert "WARN boom now" in out
    assert "WARN fine" not in out
    assert "boom but low" not in out


def test_dictconfig_builds_not_filter():
    log4p_config.dictConfig(
        {
            "root": {"level": "DEBUG", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                    "filters": [
                        {
                            "class": "NotFilter",
                            "filter": {"class": "RegexFilter", "pattern": "skip"},
                        }
                    ],
                }
            },
        }
    )
    from log4p import NotFilter, RegexFilter

    built = getRootLogger().getAppenders()[0].getFilters()[0]
    assert isinstance(built, NotFilter)
    assert isinstance(built.filter, RegexFilter)


def test_dictconfig_builds_or_filter_behaviour():
    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "DEBUG", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%p %m"},
                    "filters": [
                        {
                            "class": "OrFilter",
                            "filters": [
                                {"class": "ThresholdFilter", "level": "WARN"},
                                {"class": "RegexFilter", "pattern": "boom"},
                            ],
                        }
                    ],
                }
            },
        }
    )
    root = getRootLogger()
    root.warn("high")
    root.info("boom low")
    root.info("quiet low")
    out = buf.getvalue()
    assert "WARN high" in out
    assert "INFO boom low" in out
    assert "quiet low" not in out


def test_dictconfig_rewrite_appender_with_policy():
    from log4p import RewriteAppender

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["rewrite"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%X{req} %m"},
                },
                "rewrite": {
                    "class": "RewriteAppender",
                    "appender": "console",
                    "policy": {"class": "MapRewritePolicy", "properties": {"req": "R1"}},
                },
            },
        }
    )
    root = getRootLogger()
    app = root.getAppenders()[0]
    assert isinstance(app, RewriteAppender)
    root.info("hi")
    assert buf.getvalue() == "R1 hi\n"


def test_dictconfig_size_and_time_appender(tmp_path):
    from log4p import SizeAndTimeBasedAppender

    path = tmp_path / "app.log"
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["rolling"]},
            "appenders": {
                "rolling": {
                    "class": "SizeAndTimeBasedAppender",
                    "filename": str(path),
                    "maxBytes": 20,
                    "when": "h",
                    "backupCount": 5,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    root = getRootLogger()
    app = root.getAppenders()[0]
    assert isinstance(app, SizeAndTimeBasedAppender)
    for i in range(6):
        root.info("line-%02d", i)
    app.stop()
    assert path.exists()


def test_dictconfig_socket_and_syslog_appenders():
    from log4p import SocketAppender, SyslogAppender

    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["tcp", "syslog"]},
            "appenders": {
                "tcp": {
                    "class": "SocketAppender",
                    "host": "127.0.0.1",
                    "port": 5140,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                },
                "syslog": {
                    "class": "SyslogAppender",
                    "host": "127.0.0.1",
                    "port": 5514,
                    "facility": "LOCAL1",
                    "socktype": "UDP",
                },
            },
        }
    )
    apps = getRootLogger().getAppenders()
    assert isinstance(apps[0], SocketAppender)
    assert isinstance(apps[1], SyslogAppender)
    assert apps[1].facility == "LOCAL1"
    apps[0].stop()
    apps[1].stop()


def test_dictconfig_smtp_appender():
    from log4p import SMTPAppender

    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["mail"]},
            "appenders": {
                "mail": {
                    "class": "SMTPAppender",
                    "host": "smtp.example.com",
                    "port": 587,
                    "fromaddr": "log@example.com",
                    "toaddrs": ["ops@example.com"],
                    "triggerLevel": "ERROR",
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    app = getRootLogger().getAppenders()[0]
    assert isinstance(app, SMTPAppender)
    assert app.toaddrs == ["ops@example.com"]
    assert app.triggerLevel.name == "ERROR"


def test_dictconfig_on_startup_and_size_string(tmp_path):
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["rolling"]},
            "appenders": {
                "rolling": {
                    "class": "RotatingFileAppender",
                    "filename": str(tmp_path / "app.log"),
                    "maxBytes": "2MB",
                    "backupCount": 3,
                    "onStartup": True,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    app = getRootLogger().getAppenders()[0]
    assert app.maxBytes == 2 * 1024**2
    assert app.onStartup is True



