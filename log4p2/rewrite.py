"""Rewrite policies mutate a record before it reaches a delegate appender.

Mirrors log4j's ``RewriteAppender``: a :class:`RewritePolicy` inspects (and may
alter) each :class:`~log4p2.record.LogRecord`, then the wrapped appender writes
the result.

Policies receive a shallow copy of the record, so mutations don't affect sibling
appenders or async queues. The copy includes a pre-formatted ``exception_text``
field with the rendered traceback (or ``None``).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Union

from .appender import Appender
from .layout import Layout
from .levels import Level
from .record import LogRecord


class RewritePolicy:
    """Base class: return the (possibly modified) record to keep, or ``None``.

    The *record* argument is a copy; mutations are safe. The record has an extra
    ``exception_text`` attribute containing the formatted traceback (or ``None``).
    """

    def rewrite(self, record: LogRecord) -> Optional[LogRecord]:
        return record


class MapRewritePolicy(RewritePolicy):
    """Add or update context (MDC) entries on every record.

    *mode* is ``"update"`` (default) to set keys unconditionally, or ``"add"``
    to set a key only when it is absent.
    """

    def __init__(self, properties: Mapping[str, Any], mode: str = "update") -> None:
        if mode not in ("add", "update"):
            raise ValueError("mode must be 'add' or 'update'")
        self.properties = dict(properties)
        self.mode = mode

    def rewrite(self, record: LogRecord) -> Optional[LogRecord]:
        for key, value in self.properties.items():
            if self.mode == "update" or key not in record.context:
                record.context[key] = value
        return record


class PropertiesRewritePolicy(RewritePolicy):
    """Substitute ``${key}`` tokens in the message from *properties*.

    Useful for pulling deployment-specific values (host, region, ...) into log
    text without touching call sites. Substitution happens on the fully
    formatted message so it also sees ``%``-style arguments.
    """

    def __init__(self, properties: Mapping[str, Any]) -> None:
        self.properties = dict(properties)

    def rewrite(self, record: LogRecord) -> Optional[LogRecord]:
        message = record.getMessage()
        for key, value in self.properties.items():
            token = "${" + key + "}"
            if token in message:
                message = message.replace(token, str(value))
        record.message = message
        record.args = None
        record._formatted = None
        return record


class CallableRewritePolicy(RewritePolicy):
    """Apply a Python callable to each record (the log4j2 ``ScriptRewritePolicy``
    analogue).

    *function* receives the record and returns either the (possibly modified)
    record or ``None`` to drop the event. The record is a copy with an
    ``exception_text`` attribute.
    """

    def __init__(self, function) -> None:
        self.function = function

    def rewrite(self, record: LogRecord) -> Optional[LogRecord]:
        return self.function(record)


class RewriteAppender(Appender):
    """Apply *policy* to each record, then delegate to *appender*.

    A shallow copy of the record is passed to the policy so that mutations are
    isolated from other appenders and async queues. The copy has an extra
    ``exception_text`` attribute with the formatted traceback (or ``None``).
    """

    def __init__(
        self,
        appender: Appender,
        policy: Optional[RewritePolicy] = None,
        layout: Optional[Layout] = None,
        threshold: Optional[Union[str, int, Level]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, layout=layout, threshold=threshold)
        self.appender = appender
        self.policy = policy

    def getLayout(self) -> Layout:
        return self.appender.getLayout()

    def start(self) -> None:
        with self._lock:
            self.appender.start()
            self._started = True

    def stop(self) -> None:
        with self._lock:
            self.appender.stop()
            self._started = False

    def flush(self) -> None:
        self.appender.flush()

    def append(self, record: LogRecord) -> None:
        if self.policy is not None:
            # Create a copy with exception text for safe mutation
            record = record.copy()
            record.exception_text = record.getExceptionText()
            record = self.policy.rewrite(record)
            if record is None:
                return
        self.appender.doAppend(record)
