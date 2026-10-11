"""Structured messages: typed payloads a logger can emit instead of a string.

A :class:`MapMessage` carries key/value data that :class:`~log4p2.layout.JSONLayout`
and :class:`~log4p2.layout.LogfmtLayout` emit as top-level fields while
``%m`` renders a readable ``key="value"`` form.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Mapping, Optional


class Message:
    """Base class for structured messages."""

    def getFormattedMessage(self) -> str:
        raise NotImplementedError

    def getParameters(self) -> list:
        return []

    def __str__(self) -> str:
        return self.getFormattedMessage()


class MapMessage(Message):
    """A message whose payload is an ordered key/value map."""

    def __init__(self, data: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> None:
        self.data: Dict[str, Any] = {}
        if data:
            self.data.update(data)
        if kwargs:
            self.data.update(kwargs)

    def put(self, key: str, value: Any) -> "MapMessage":
        self.data[key] = value
        return self

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def remove(self, key: str) -> None:
        self.data.pop(key, None)

    def clear(self) -> None:
        self.data.clear()

    def isEmpty(self) -> bool:
        return not self.data

    def getData(self) -> Dict[str, Any]:
        return self.data

    def keySet(self) -> list:
        return list(self.data.keys())

    def __iter__(self) -> Iterator[str]:
        return iter(self.data)

    def getFormattedMessage(self) -> str:
        return " ".join(f'{key}="{value}"' for key, value in self.data.items())


class StringMapMessage(MapMessage):
    """A :class:`MapMessage` that renders string values verbatim."""

    def getFormattedMessage(self) -> str:
        return " ".join(f'{key}="{value}"' for key, value in self.data.items())


class StructuredDataMessage(MapMessage):
    """A :class:`MapMessage` carrying an RFC 5424 structured-data id and type."""

    def __init__(
        self,
        data: Optional[Mapping[str, Any]] = None,
        id: str = "log4p@32473",
        type: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(data, **kwargs)
        self.id = id
        self.type = type

    def getFormattedMessage(self) -> str:
        params = []
        if self.type:
            params.append(f'name="{self.type}"')
        params.extend(f'{key}="{value}"' for key, value in self.data.items())
        body = " ".join(params)
        return f"[{self.id} {body}]" if body else f"[{self.id}]"
