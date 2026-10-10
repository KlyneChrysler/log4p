import io
import json

import pytest

from log4p import getLogger, getRootLogger
from log4p import config as log4p_config
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
