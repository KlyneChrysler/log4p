import json

from log4p2 import (
    JSONLayout,
    Level,
    LogfmtLayout,
    LogRecord,
    MapMessage,
    PatternLayout,
    StringMapMessage,
    StructuredDataMessage,
)


def record(message):
    return LogRecord(name="app", level=Level.INFO, message=message)


def test_map_message_builder():
    msg = MapMessage().put("user", "bob").put("id", 7)
    assert msg.get("user") == "bob"
    assert msg.getData() == {"user": "bob", "id": 7}
    assert msg.keySet() == ["user", "id"]
    assert not msg.isEmpty()
    msg.remove("id")
    assert msg.getData() == {"user": "bob"}
    msg.clear()
    assert msg.isEmpty()


def test_map_message_init_from_mapping_and_kwargs():
    msg = MapMessage({"a": 1}, b=2)
    assert msg.getData() == {"a": 1, "b": 2}


def test_map_message_formatted_message():
    msg = MapMessage({"user": "bob", "id": 7})
    assert msg.getFormattedMessage() == 'user="bob" id="7"'
    assert str(msg) == 'user="bob" id="7"'


def test_record_get_message_uses_formatted_message():
    rec = record(MapMessage({"k": "v"}))
    assert rec.getMessage() == 'k="v"'


def test_pattern_layout_renders_map_message():
    rec = record(MapMessage({"user": "bob"}))
    assert PatternLayout("%m").format(rec) == 'user="bob"'


def test_json_layout_flattens_map_message():
    rec = record(MapMessage({"user": "bob", "id": 7}))
    data = json.loads(JSONLayout().format(rec))
    assert data["user"] == "bob"
    assert data["id"] == 7
    assert data["message"] == 'user="bob" id="7"'


def test_json_layout_does_not_clobber_reserved_fields():
    rec = record(MapMessage({"level": "spoofed", "logger": "x", "user": "bob"}))
    data = json.loads(JSONLayout().format(rec))
    assert data["level"] == "INFO"
    assert data["logger"] == "app"
    assert data["user"] == "bob"


def test_logfmt_layout_includes_map_data():
    rec = record(MapMessage({"user": "bob", "id": 7}))
    line = LogfmtLayout().format(rec)
    assert "user=bob" in line
    assert "id=7" in line


def test_plain_string_record_unaffected():
    rec = record("hello %s")
    rec.args = ("world",)
    data = json.loads(JSONLayout().format(rec))
    assert data["message"] == "hello world"


def test_string_map_message():
    msg = StringMapMessage({"a": "1"})
    assert msg.getFormattedMessage() == 'a="1"'


def test_structured_data_message():
    msg = StructuredDataMessage({"user": "bob"}, id="audit@example", type="login")
    assert msg.getFormattedMessage() == '[audit@example name="login" user="bob"]'
    rec = record(msg)
    data = json.loads(JSONLayout().format(rec))
    assert data["user"] == "bob"


def test_structured_data_message_without_type():
    msg = StructuredDataMessage({"a": 1}, id="x@1")
    assert msg.getFormattedMessage() == '[x@1 a="1"]'
