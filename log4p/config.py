"""Configuration: build appenders/layouts/filters from Python dicts or files.

Two entry points:

* :func:`dictConfig` - apply an in-memory mapping.
* :func:`fileConfig` - load YAML or JSON (YAML is a superset of JSON) and apply.

The mapping shape::

    version: 1
    root:
      level: INFO
      appenders: [console]
    loggers:
      myapp.db:
        level: DEBUG
        appenders: [console, db_file]
        additive: false
    appenders:
      console:
        class: ConsoleAppender
        target: stdout
        layout:
          class: PatternLayout
          pattern: "%d{ISO8601} %-5p %c - %m%n"
      db_file:
        class: RotatingFileAppender
        filename: logs/db.log
        maxBytes: 1048576
        backupCount: 3
        layout:
          class: JSONLayout
        filters:
          - class: LevelRangeFilter
            min_level: INFO
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
from typing import Any, Dict, Mapping, Optional

from .appender import (
    Appender,
    AsyncAppender,
    ConsoleAppender,
    FileAppender,
    NullAppender,
    RotatingFileAppender,
    SizeAndTimeBasedAppender,
    TimedRotatingFileAppender,
)
from .error import ErrorHandler, FallbackErrorHandler
from .filter import (
    AcceptAllFilter,
    AndFilter,
    DenyAllFilter,
    Filter,
    LevelMatchFilter,
    LevelRangeFilter,
    MarkerFilter,
    NotFilter,
    OrFilter,
    RegexFilter,
    ThresholdFilter,
)
from .layout import (
    HTMLLayout,
    JSONLayout,
    Layout,
    LogfmtLayout,
    PatternLayout,
    SimpleLayout,
    XMLLayout,
)
from .logger import getLogger, getLoggerManager, getRootLogger
from .mail import SMTPAppender
from .net import SocketAppender, SyslogAppender
from .rewrite import (
    MapRewritePolicy,
    PropertiesRewritePolicy,
    RewriteAppender,
    RewritePolicy,
)

_REGISTRY = {
    cls.__name__: cls
    for cls in (
        Appender,
        ConsoleAppender,
        FileAppender,
        NullAppender,
        RotatingFileAppender,
        TimedRotatingFileAppender,
        SizeAndTimeBasedAppender,
        AsyncAppender,
        RewriteAppender,
        RewritePolicy,
        MapRewritePolicy,
        PropertiesRewritePolicy,
        SocketAppender,
        SyslogAppender,
        SMTPAppender,
        Layout,
        SimpleLayout,
        PatternLayout,
        JSONLayout,
        LogfmtLayout,
        XMLLayout,
        HTMLLayout,
        Filter,
        ThresholdFilter,
        LevelMatchFilter,
        LevelRangeFilter,
        RegexFilter,
        MarkerFilter,
        AndFilter,
        OrFilter,
        NotFilter,
        AcceptAllFilter,
        DenyAllFilter,
        ErrorHandler,
        FallbackErrorHandler,
    )
}


_SUBST_RE = re.compile(r"\$\{([^}:]+):([^}]*)\}")


def _lookup_substitution(kind: str, expr: str) -> str:
    """Resolve ``${kind:name:-default}`` to a string value."""
    default = ""
    name = expr
    if ":-" in expr:
        name, _, default = expr.partition(":-")
    if kind == "env":
        value = os.environ.get(name)
    elif kind == "sys":
        value = getattr(sys, name, None)
    else:
        raise ValueError(f"unknown substitution kind {kind!r} (use 'env' or 'sys')")
    if value is None:
        return default
    return str(value)


def substitute_variables(value: Any) -> Any:
    """Recursively replace ``${env:...}`` / ``${sys:...}`` in config values."""
    if isinstance(value, str):
        return _SUBST_RE.sub(lambda m: _lookup_substitution(m.group(1), m.group(2)), value)
    if isinstance(value, Mapping):
        return {key: substitute_variables(val) for key, val in value.items()}
    if isinstance(value, list):
        return [substitute_variables(item) for item in value]
    return value


def _resolve(name: str) -> type:
    """Resolve a component class from a short name or a dotted path."""
    if not isinstance(name, str):
        raise TypeError(f"component class must be a string, got {type(name).__name__}")
    if name in _REGISTRY:
        return _REGISTRY[name]
    module_path, _, attr = name.rpartition(".")
    if not module_path:
        raise ValueError(f"unknown log4p component: {name!r}")
    module = importlib.import_module(module_path)
    try:
        return getattr(module, attr)
    except AttributeError:
        raise ValueError(f"module {module_path!r} has no attribute {attr!r}") from None


def _build_layout(spec: Any) -> Optional[Layout]:
    if spec is None:
        return None
    if isinstance(spec, Layout):
        return spec
    if isinstance(spec, str):
        spec = {"class": spec}
    spec = dict(spec)
    cls = _resolve(spec.pop("class"))
    return cls(**spec)


def _build_filter(spec: Any) -> Filter:
    if isinstance(spec, Filter):
        return spec
    if isinstance(spec, str):
        spec = {"class": spec}
    spec = dict(spec)
    cls = _resolve(spec.pop("class"))
    args = []
    children = spec.pop("filters", None)
    if children is not None:
        args = [_build_filter(child) for child in children]
    single = spec.pop("filter", None)
    if single is not None:
        args.append(_build_filter(single))
    return cls(*args, **spec)


def _build_policy(spec: Any) -> Optional[RewritePolicy]:
    if spec is None:
        return None
    if isinstance(spec, RewritePolicy):
        return spec
    if isinstance(spec, str):
        spec = {"class": spec}
    spec = dict(spec)
    cls = _resolve(spec.pop("class"))
    return cls(**spec)


def _build_error_handler(spec: Any):
    if spec is None:
        return None
    if isinstance(spec, ErrorHandler):
        return spec
    if isinstance(spec, str):
        spec = {"class": spec}
    spec = dict(spec)
    cls = _resolve(spec.pop("class"))
    backups = spec.pop("backup", None) or []
    handler = cls(**spec)
    setattr(handler, "_log4p_backups", backups)
    return handler


def _build_appender(spec: Any, built: Dict[str, Appender]) -> Appender:
    if isinstance(spec, Appender):
        return spec
    spec = dict(spec)
    cls = _resolve(spec.pop("class"))

    delegate = spec.pop("appender", None)
    if isinstance(delegate, str):
        if delegate not in built:
            raise ValueError(
                f"async appender references {delegate!r}, which must be defined first"
            )
        spec["appender"] = built[delegate]

    layout = _build_layout(spec.pop("layout", None))
    filters = spec.pop("filters", None) or []
    threshold = spec.pop("threshold", None)
    error_handler = _build_error_handler(spec.pop("errorHandler", None))
    policy = _build_policy(spec.pop("policy", None))
    if layout is not None:
        spec["layout"] = layout
    if threshold is not None:
        spec["threshold"] = threshold
    if policy is not None:
        spec["policy"] = policy

    appender = cls(**spec)

    if error_handler is not None:
        if hasattr(error_handler, "setAppender"):
            error_handler.setAppender(appender)
        backup_names = getattr(error_handler, "_log4p_backups", [])
        for backup_name in backup_names:
            if backup_name not in built:
                raise ValueError(
                    f"error handler references backup appender {backup_name!r}, "
                    "which must be defined first"
                )
            error_handler.setBackupAppender(built[backup_name])
        appender.setErrorHandler(error_handler)

    for filt in filters:
        appender.addFilter(_build_filter(filt))
    return appender


def dictConfig(config: Mapping[str, Any]) -> None:
    """Apply a logging configuration mapping (see module docstring)."""
    if not isinstance(config, Mapping):
        raise TypeError("dictConfig expects a mapping")
    config = dict(config)
    if config.pop("substitute", True):
        config = substitute_variables(config)

    appender_cfgs: Dict[str, Any] = config.get("appenders", {})
    logger_cfgs: Dict[str, Any] = config.get("loggers", {})
    root_cfg = config.get("root")
    do_clear = config.get("clear", True)

    manager = getLoggerManager()
    if do_clear:
        manager.clear()

    appenders: Dict[str, Appender] = {}
    for name, spec in appender_cfgs.items():
        appenders[name] = _build_appender(spec, appenders)

    root = getRootLogger()
    if root_cfg:
        if root_cfg.get("level") is not None:
            root.setLevel(root_cfg["level"])
        for name in root_cfg.get("appenders", []):
            root.addAppender(_lookup_appender(appenders, name))

    for name, lcfg in logger_cfgs.items():
        logger = getLogger(name)
        if lcfg.get("level") is not None:
            logger.setLevel(lcfg["level"])
        additive = lcfg.get("additive", lcfg.get("additivity"))
        if additive is not None:
            logger.setAdditivity(bool(additive))
        for appender_name in lcfg.get("appenders", []):
            logger.addAppender(_lookup_appender(appenders, appender_name))

    return None


def _lookup_appender(appenders: Dict[str, Appender], name: str) -> Appender:
    try:
        return appenders[name]
    except KeyError:
        raise ValueError(f"configuration references unknown appender {name!r}") from None


def fileConfig(path: str, format: Optional[str] = None) -> None:
    """Load a YAML/JSON config file and apply it via :func:`dictConfig`."""
    ext = (format or os.path.splitext(path)[1]).lstrip(".").lower()
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if ext == "json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "PyYAML is required to read non-JSON config files"
            ) from exc
        data = yaml.safe_load(text)
    dictConfig(data)


def basicConfig(
    level: str = "INFO",
    format: str = "%d{ISO8601} %-5p %c - %m%n",
    filename: Optional[str] = None,
    stream: Any = None,
    target: str = "stdout",
) -> Appender:
    """Quick one-call setup on the root logger.

    Writes to a file when *filename* is given, otherwise to the console.
    """
    layout = PatternLayout(format)
    if filename:
        appender: Appender = FileAppender(filename, layout=layout)
    else:
        appender = ConsoleAppender(layout=layout, target=target, stream=stream)
    root = getRootLogger()
    root.addAppender(appender)
    root.setLevel(level)
    return appender
