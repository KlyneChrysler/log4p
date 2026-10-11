import json

import pytest

from log4p2 import HttpAppender, JSONLayout, Level, LogRecord, PatternLayout


def record(message="hello", level=Level.INFO):
    return LogRecord(name="app.db", level=level, message=message)


class _FakeResponse:
    def __init__(self, payload=b""):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_appender_posts_json(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None, context=None):
        captured["request"] = request
        captured["timeout"] = timeout
        captured["context"] = context
        return _FakeResponse()

    monkeypatch.setattr("log4p.net.urllib.request.urlopen", fake_urlopen)
    app = HttpAppender("http://example.test/log", readTimeout=2.5)
    app.append(record("hi"))
    request = captured["request"]
    assert request.method == "POST"
    assert request.full_url == "http://example.test/log"
    assert captured["timeout"] == 2.5
    data = json.loads(request.data.decode("utf-8"))
    assert data["message"] == "hi"
    assert data["level"] == "INFO"


def test_http_appender_get_method_encodes_message(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None, context=None):
        captured["request"] = request
        return _FakeResponse()

    monkeypatch.setattr("log4p.net.urllib.request.urlopen", fake_urlopen)
    app = HttpAppender("http://example.test/log", method="GET", layout=PatternLayout("%m"))
    app.append(record("a b"))
    request = captured["request"]
    assert request.method == "GET"
    assert "msg=a+b" in request.full_url


def test_http_appender_custom_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None, context=None):
        captured["request"] = request
        return _FakeResponse()

    monkeypatch.setattr("log4p.net.urllib.request.urlopen", fake_urlopen)
    app = HttpAppender("http://example.test/log", headers={"Authorization": "Bearer t"})
    app.append(record())
    assert captured["request"].get_header("Authorization") == "Bearer t"


def test_http_appender_unverified_context(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None, context=None):
        captured["context"] = context
        return _FakeResponse()

    monkeypatch.setattr("log4p.net.urllib.request.urlopen", fake_urlopen)
    app = HttpAppender("https://example.test/log", verifyHostname=False)
    app.append(record())
    assert captured["context"] is not None


def test_http_appender_invalid_method():
    with pytest.raises(ValueError):
        HttpAppender("http://x", method="PUT")


def test_http_appender_default_layout_is_json():
    assert isinstance(HttpAppender("http://x").getLayout(), JSONLayout)
