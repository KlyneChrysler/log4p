import io
import json
import os

import pytest

from log4p2 import config as log4p_config
from log4p2 import getLogger, getMarker, getRootLogger
from log4p2.logger import getLoggerManager


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


def _write_level_config(path, level, marker, mtime):
    path.write_text(
        f"""
root:
  level: {level}
  appenders: [console]
appenders:
  console:
    class: ConsoleAppender
    layout:
      class: PatternLayout
      pattern: "{marker} %m"
"""
    )
    os.utime(path, (mtime, mtime))


def test_fileconfig_monitor_interval_reloads(tmp_path):
    import time

    path = tmp_path / "log4p.yaml"
    now = time.time()
    _write_level_config(path, "INFO", "one", now)
    log4p_config.fileConfig(str(path), monitorInterval=0.05)
    assert getRootLogger().getLevel().name == "INFO"

    _write_level_config(path, "DEBUG", "two", now + 5)
    deadline = time.time() + 3
    while time.time() < deadline and getRootLogger().getLevel().name != "DEBUG":
        time.sleep(0.02)
    assert getRootLogger().getLevel().name == "DEBUG"

    log4p_config._configure_watcher(str(path), None, None)
    assert str(path) not in log4p_config._WATCHERS


def test_fileconfig_stops_watcher(tmp_path):
    import time

    path = tmp_path / "log4p.yaml"
    _write_level_config(path, "INFO", "x", time.time())
    log4p_config.fileConfig(str(path), monitorInterval=0.05)
    assert str(path) in log4p_config._WATCHERS
    log4p_config.fileConfig(str(path), monitorInterval=0)
    assert str(path) not in log4p_config._WATCHERS


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
    from log4p2 import ConsoleAppender, PatternLayout

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
    from log4p2 import AsyncAppender

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


def test_dictconfig_async_buffer_size_and_blocking():
    from log4p2 import AsyncAppender

    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["async"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                },
                "async": {
                    "class": "AsyncAppender",
                    "appender": "console",
                    "bufferSize": 16,
                    "blocking": False,
                    "discardingThreshold": 3,
                },
            },
        }
    )
    app = getRootLogger().getAppenders()[0]
    assert isinstance(app, AsyncAppender)
    assert app.queue_size == 16
    assert app.overflow == "discard"
    assert app.discardingThreshold == 3
    app.stop()


def test_dictconfig_http_appender():
    from log4p2 import HttpAppender, JSONLayout

    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["http"]},
            "appenders": {
                "http": {
                    "class": "HttpAppender",
                    "url": "http://example.test/log",
                    "method": "GET",
                    "headers": {"X-Token": "abc"},
                    "readTimeout": 1.5,
                }
            },
        }
    )
    app = getRootLogger().getAppenders()[0]
    assert isinstance(app, HttpAppender)
    assert app.url == "http://example.test/log"
    assert app.method == "GET"
    assert app.headers == {"X-Token": "abc"}
    assert app.readTimeout == 1.5
    assert isinstance(app.getLayout(), JSONLayout)


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


def test_dictconfig_builds_level_match_and_on_match_replies():
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
                        {"class": "LevelMatchFilter", "level": "ERROR"},
                    ],
                }
            },
        }
    )
    root = getRootLogger()
    root.error("keep me")
    root.warn("drop me")
    out = buf.getvalue()
    assert "ERROR keep me" in out
    assert "drop me" not in out

    filt = getRootLogger().getAppenders()[0].getFilters()[0]
    from log4p2 import FilterReply, LevelMatchFilter

    assert isinstance(filt, LevelMatchFilter)
    assert filt.onMatch == FilterReply.NEUTRAL
    assert filt.onMismatch == FilterReply.DENY


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
    from log4p2 import NotFilter, RegexFilter

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
    from log4p2 import RewriteAppender

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


def test_dictconfig_properties_rewrite_policy():
    from log4p2 import RewriteAppender

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["rewrite"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                },
                "rewrite": {
                    "class": "RewriteAppender",
                    "appender": "console",
                    "policy": {
                        "class": "PropertiesRewritePolicy",
                        "properties": {"region": "us-east-1"},
                    },
                },
            },
        }
    )
    root = getRootLogger()
    assert isinstance(root.getAppenders()[0], RewriteAppender)
    root.info("deploy to ${region}")
    assert buf.getvalue() == "deploy to us-east-1\n"


def test_dictconfig_size_and_time_appender(tmp_path):
    from log4p2 import SizeAndTimeBasedAppender

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
    from log4p2 import SocketAppender, SyslogAppender

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
                    "rfc5424": True,
                    "appName": "svc",
                },
            },
        }
    )
    apps = getRootLogger().getAppenders()
    assert isinstance(apps[0], SocketAppender)
    assert isinstance(apps[1], SyslogAppender)
    assert apps[1].facility == "LOCAL1"
    assert apps[1].rfc5424 is True
    assert apps[1].appName == "svc"
    apps[0].stop()
    apps[1].stop()


def test_dictconfig_smtp_appender():
    from log4p2 import SMTPAppender

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


def test_dictconfig_null_appender():
    from log4p2 import NullAppender

    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["null"]},
            "appenders": {"null": {"class": "NullAppender"}},
        }
    )
    app = getRootLogger().getAppenders()[0]
    assert isinstance(app, NullAppender)


def test_dictconfig_memory_appender():
    from log4p2 import MemoryAppender

    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["mem"]},
            "appenders": {
                "mem": {
                    "class": "MemoryAppender",
                    "maxSize": 5,
                    "layout": {"class": "PatternLayout", "pattern": "%p %m"},
                }
            },
        }
    )
    app = getRootLogger().getAppenders()[0]
    assert isinstance(app, MemoryAppender)
    assert app.maxSize == 5
    getRootLogger().info("hi")
    assert app.getEvents() == ["INFO hi"]


def test_dictconfig_console_immediate_flush():
    from log4p2 import ConsoleAppender

    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["c"]},
            "appenders": {
                "c": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "immediateFlush": False,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    app = getRootLogger().getAppenders()[0]
    assert isinstance(app, ConsoleAppender)
    assert app.immediateFlush is False


def test_dictconfig_custom_level():
    from log4p2 import getLevel

    log4p_config.dictConfig(
        {
            "levels": {"VERBOSE": 15},
            "root": {"level": "VERBOSE", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    assert getLevel("VERBOSE").value == 15
    assert getRootLogger().getEffectiveLevel().name == "VERBOSE"


def test_dictconfig_context_map_filter():
    from log4p2 import ContextMapFilter

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
                            "class": "ContextMapFilter",
                            "properties": {"tenant": "acme"},
                            "operator": "and",
                        }
                    ],
                }
            },
        }
    )
    built = getRootLogger().getAppenders()[0].getFilters()[0]
    assert isinstance(built, ContextMapFilter)
    assert built.operator == "and"


def test_dictconfig_dynamic_threshold_filter():
    from log4p2 import DynamicThresholdFilter

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
                            "class": "DynamicThresholdFilter",
                            "key": "user",
                            "levels": {"alice": "DEBUG"},
                            "default_threshold": "ERROR",
                        }
                    ],
                }
            },
        }
    )
    built = getRootLogger().getAppenders()[0].getFilters()[0]
    assert isinstance(built, DynamicThresholdFilter)
    assert built.key == "user"
    assert built.default_threshold.name == "ERROR"


def test_dictconfig_logger_level_filters():
    from log4p2 import LevelMatchFilter

    log4p_config.dictConfig(
        {
            "root": {"level": "DEBUG", "appenders": ["console"]},
            "loggers": {
                "svc": {
                    "level": "DEBUG",
                    "appenders": ["console"],
                    "filters": [{"class": "LevelMatchFilter", "level": "ERROR"}],
                }
            },
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    logger = getLogger("svc")
    built = logger.getFilters()[0]
    assert isinstance(built, LevelMatchFilter)
    assert built.level.name == "ERROR"


def test_dictconfig_root_filters():
    from log4p2 import AcceptAllFilter

    log4p_config.dictConfig(
        {
            "root": {
                "level": "DEBUG",
                "appenders": ["console"],
                "filters": [{"class": "AcceptAllFilter"}],
            },
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    built = getRootLogger().getFilters()[0]
    assert isinstance(built, AcceptAllFilter)


def test_dictconfig_json_layout_options():
    from log4p2 import JSONLayout

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {
                        "class": "JSONLayout",
                        "compact": True,
                        "includeStacktrace": False,
                        "includeLocation": True,
                        "properties": {"app": "svc"},
                    },
                }
            },
        }
    )
    logger = getRootLogger()
    layout = logger.getAppenders()[0].getLayout()
    assert isinstance(layout, JSONLayout)
    assert layout.compact is True
    assert layout.includeStacktrace is False
    assert layout.includeLocation is True
    assert layout.properties == {"app": "svc"}
    logger.info("hi")
    data = json.loads(buf.getvalue())
    assert data["app"] == "svc"
    assert "source" in data


def test_dictconfig_burst_filter():
    from log4p2 import BurstFilter

    log4p_config.dictConfig(
        {
            "root": {"level": "DEBUG", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                    "filters": [
                        {"class": "BurstFilter", "rate": 5, "maxBurst": 10}
                    ],
                }
            },
        }
    )
    built = getRootLogger().getAppenders()[0].getFilters()[0]
    assert isinstance(built, BurstFilter)
    assert built.rate == 5.0
    assert built.maxBurst == 10


def test_dictconfig_cron_rolling(tmp_path):
    from log4p2 import CronRollingFileAppender

    path = tmp_path / "app.log"
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["cron"]},
            "appenders": {
                "cron": {
                    "class": "CronRollingFileAppender",
                    "filename": str(path),
                    "cron": "0 0 * * *",
                    "suffix": "%Y%m%d",
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                }
            },
        }
    )
    app = getRootLogger().getAppenders()[0]
    assert isinstance(app, CronRollingFileAppender)
    assert app.suffix_format == "%Y%m%d"
    getRootLogger().info("cron-tick")
    getLoggerManager().shutdown()
    assert path.read_text() == "cron-tick\n"


def test_dictconfig_time_filter():
    from log4p2 import TimeFilter

    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": io.StringIO(),
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                    "filters": [{"class": "TimeFilter", "start": "08:00", "end": "17:00"}],
                }
            },
        }
    )
    built = getRootLogger().getAppenders()[0].getFilters()[0]
    assert isinstance(built, TimeFilter)
    assert built.start == "08:00"
    assert built.end == "17:00"


def test_dictconfig_marker_pattern_selector():
    from log4p2 import MarkerPatternSelector, PatternLayout

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {
                        "class": "PatternLayout",
                        "pattern": "%m",
                        "selector": {
                            "class": "MarkerPatternSelector",
                            "patterns": {"SQL": "SQL> %m"},
                            "default": "def> %m",
                        },
                    },
                }
            },
        }
    )
    layout = getRootLogger().getAppenders()[0].getLayout()
    assert isinstance(layout, PatternLayout)
    assert isinstance(layout.selector, MarkerPatternSelector)

    getRootLogger().info("plain")
    getRootLogger().info("query", marker=getMarker("SQL"))
    assert buf.getvalue() == "def> plain\nSQL> query\n"


def test_dictconfig_map_filter():
    from log4p2 import MapFilter, MapMessage

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                    "filters": [
                        {"class": "MapFilter", "properties": {"svc": "checkout"}}
                    ],
                }
            },
        }
    )
    built = getRootLogger().getAppenders()[0].getFilters()[0]
    assert isinstance(built, MapFilter)
    getRootLogger().info(MapMessage({"svc": "checkout"}))
    getRootLogger().info(MapMessage({"svc": "billing"}))
    out = buf.getvalue()
    assert "checkout" in out
    assert "billing" not in out


def test_dictconfig_structured_data_filter():
    from log4p2 import StructuredDataFilter, StructuredDataMessage

    buf = io.StringIO()
    log4p_config.dictConfig(
        {
            "root": {"level": "INFO", "appenders": ["console"]},
            "appenders": {
                "console": {
                    "class": "ConsoleAppender",
                    "stream": buf,
                    "layout": {"class": "PatternLayout", "pattern": "%m"},
                    "filters": [
                        {
                            "class": "StructuredDataFilter",
                            "properties": {"user": "alice"},
                            "type": "audit",
                        }
                    ],
                }
            },
        }
    )
    built = getRootLogger().getAppenders()[0].getFilters()[0]
    assert isinstance(built, StructuredDataFilter)
    assert built.type == "audit"
    getRootLogger().info(StructuredDataMessage({"user": "alice"}, type="audit"))
    getRootLogger().info(StructuredDataMessage({"user": "bob"}, type="audit"))
    getRootLogger().info("plain")
    assert "alice" in buf.getvalue()
    assert "bob" not in buf.getvalue()
    assert "plain" not in buf.getvalue()




