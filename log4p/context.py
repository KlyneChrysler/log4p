"""Diagnostic context: MDC (mapped) and NDC (nested), log4j style.

Both are isolated per execution context (thread or asyncio task) using
``contextvars`` so values never leak between concurrent callers.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Dict, List, Optional

_mdc: ContextVar[Optional[Dict[str, object]]] = ContextVar("log4p_mdc", default=None)
_ndc: ContextVar[Optional[List[str]]] = ContextVar("log4p_ndc", default=None)


class MDC:
    """Mapped Diagnostic Context: a per-context key/value bag.

    Use it to attach request IDs, tenant IDs, or any cross-cutting field that
    every log line inside a scope should carry.
    """

    @staticmethod
    def put(key: str, value: object) -> None:
        current = _mdc.get()
        new = dict(current) if current else {}
        new[key] = value
        _mdc.set(new)

    @staticmethod
    def get(key: str, default: object = None) -> object:
        current = _mdc.get()
        return current.get(key, default) if current else default

    @staticmethod
    def remove(key: str) -> None:
        current = _mdc.get()
        if not current or key not in current:
            return
        new = dict(current)
        del new[key]
        _mdc.set(new or None)

    @staticmethod
    def putAll(mapping) -> None:
        current = _mdc.get()
        new = dict(current) if current else {}
        new.update(mapping)
        _mdc.set(new or None)

    @staticmethod
    def setContext(mapping) -> None:
        new = dict(mapping) if mapping else None
        _mdc.set(new or None)

    @staticmethod
    def containsKey(key: str) -> bool:
        current = _mdc.get()
        return bool(current) and key in current

    @staticmethod
    def isEmpty() -> bool:
        return not _mdc.get()

    @staticmethod
    def clear() -> None:
        _mdc.set(None)

    @staticmethod
    def getCopy() -> Dict[str, object]:
        current = _mdc.get()
        return dict(current) if current else {}

    @staticmethod
    def getContext() -> Dict[str, object]:
        """Immutable snapshot of the context (log4j ``getImmutableContext``)."""
        return MDC.getCopy()

    @staticmethod
    def getImmutableContext() -> Dict[str, object]:
        return MDC.getCopy()


class NDC:
    """Nested Diagnostic Context: a per-context LIFO stack of strings."""

    @staticmethod
    def push(message: str) -> None:
        current = _ndc.get()
        stack = list(current) if current else []
        stack.append(message)
        _ndc.set(stack)

    @staticmethod
    def pop() -> Optional[str]:
        current = _ndc.get()
        if not current:
            return None
        stack = list(current)
        value = stack.pop()
        _ndc.set(stack or None)
        return value

    @staticmethod
    def remove() -> Optional[str]:
        """Alias for :meth:`pop` (log4j ``NDC.remove``)."""
        return NDC.pop()

    @staticmethod
    def peek() -> Optional[str]:
        current = _ndc.get()
        return current[-1] if current else None

    @staticmethod
    def getDepth() -> int:
        current = _ndc.get()
        return len(current) if current else 0

    @staticmethod
    def isEmpty() -> bool:
        return not _ndc.get()

    @staticmethod
    def getStack() -> List[str]:
        current = _ndc.get()
        return list(current) if current else []

    @staticmethod
    def clear() -> None:
        _ndc.set(None)

    @staticmethod
    def get() -> str:
        current = _ndc.get()
        return " ".join(current) if current else ""


# log4j 2 naming alias.
ThreadContext = MDC
