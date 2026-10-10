"""Markers: named tags attached to records, log4j style.

A marker is a lightweight, possibly hierarchical label (``SQL``, ``AUDIT``).
Attach one to a call with ``marker=`` and filter on it with
:class:`~log4p.filter.MarkerFilter`.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional

_LOCK = threading.RLock()
_REGISTRY: Dict[str, "Marker"] = {}


class Marker:
    """A named, optionally hierarchical tag on a log record."""

    def __init__(self, name: str, parents: Optional[list] = None) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("marker name must be a non-empty string")
        self.name = name
        self.parents = list(parents) if parents else []

    def getName(self) -> str:
        return self.name

    def getParents(self) -> list:
        return list(self.parents)

    def add(self, parent: "Marker") -> "Marker":
        if parent not in self.parents:
            self.parents.append(parent)
        return self

    def remove(self, parent: "Marker") -> None:
        if parent in self.parents:
            self.parents.remove(parent)

    def isInstanceOf(self, other: "Marker") -> bool:
        """True if *other* is this marker or one of its ancestors."""
        if other is self or other.name == self.name:
            return True
        for parent in self.parents:
            if parent.isInstanceOf(other):
                return True
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Marker) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Marker({self.name!r})"


def getMarker(name: str, parents: Optional[list] = None) -> Marker:
    """Return the shared marker called *name*, creating it if needed."""
    with _LOCK:
        existing = _REGISTRY.get(name)
        if existing is not None:
            if parents:
                for parent in parents:
                    existing.add(parent)
            return existing
        marker = Marker(name, parents)
        _REGISTRY[name] = marker
        return marker


def getMarkerNames() -> list:
    return sorted(_REGISTRY.keys())
