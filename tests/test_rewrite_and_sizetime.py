import glob
import os
import time

import pytest

from log4p import (
    ConsoleAppender,
    Level,
    LogRecord,
    MapRewritePolicy,
    PatternLayout,
    PropertiesRewritePolicy,
    RewriteAppender,
    SizeAndTimeBasedAppender,
)


def record(message="line", level=Level.INFO):
    return LogRecord(name="app", level=level, message=message)


def test_map_rewrite_policy_update():
    policy = MapRewritePolicy({"req": "R1"})
    rec = record()
    rec.context["req"] = "old"
    policy.rewrite(rec)
    assert rec.context["req"] == "R1"


def test_map_rewrite_policy_add_keeps_existing():
    policy = MapRewritePolicy({"req": "new", "user": "bob"}, mode="add")
    rec = record()
    rec.context["req"] = "old"
    policy.rewrite(rec)
    assert rec.context["req"] == "old"
    assert rec.context["user"] == "bob"


def test_map_rewrite_policy_rejects_bad_mode():
    with pytest.raises(ValueError):
        MapRewritePolicy({}, mode="nope")


def test_rewrite_appender_applies_policy(capsys):
    inner = ConsoleAppender(PatternLayout("%X{req} %m"))
    rw = RewriteAppender(inner, policy=MapRewritePolicy({"req": "R1"}))
    rw.doAppend(record("hello"))
    inner.stop()
    assert capsys.readouterr().out == "R1 hello\n"


def test_rewrite_appender_without_policy(capsys):
    inner = ConsoleAppender(PatternLayout("%m"))
    rw = RewriteAppender(inner)
    rw.doAppend(record("plain"))
    inner.stop()
    assert capsys.readouterr().out == "plain\n"


def test_rewrite_appender_delegates_lifecycle():
    inner = ConsoleAppender()
    rw = RewriteAppender(inner)
    rw.start()
    assert inner.isStarted()
    rw.stop()
    assert not inner.isStarted()


def test_properties_rewrite_policy_substitutes_tokens():
    policy = PropertiesRewritePolicy({"region": "us-east-1", "env": "prod"})
    rec = record("deploy to ${region} (${env})")
    policy.rewrite(rec)
    assert rec.getMessage() == "deploy to us-east-1 (prod)"


def test_properties_rewrite_policy_leaves_unknown_tokens():
    policy = PropertiesRewritePolicy({"a": "x"})
    rec = record("keep ${missing} as is")
    policy.rewrite(rec)
    assert rec.getMessage() == "keep ${missing} as is"


def test_properties_rewrite_policy_sees_formatted_args():
    policy = PropertiesRewritePolicy({"region": "eu"})
    rec = LogRecord(name="app", level=Level.INFO, message="%s -> ${region}", args=("node1",))
    policy.rewrite(rec)
    assert rec.getMessage() == "node1 -> eu"


def test_callable_rewrite_policy_transforms_record():
    from log4p import CallableRewritePolicy

    policy = CallableRewritePolicy(lambda r: r)
    rec = record("hello")
    assert policy.rewrite(rec) is rec


def test_callable_rewrite_policy_can_drop_event(capsys):
    from log4p import CallableRewritePolicy

    inner = ConsoleAppender(PatternLayout("%m"))
    rw = RewriteAppender(inner, policy=CallableRewritePolicy(lambda r: None))
    rw.doAppend(record("dropped"))
    inner.stop()
    assert capsys.readouterr().out == ""


def test_callable_appender_receives_records():
    from log4p import CallableAppender

    seen = []
    appender = CallableAppender(seen.append)
    appender.doAppend(record("one"))
    appender.doAppend(record("two"))
    assert [r.getMessage() for r in seen] == ["one", "two"]


def test_size_and_time_rolls_on_size(tmp_path):
    path = tmp_path / "app.log"
    app = SizeAndTimeBasedAppender(
        str(path), maxBytes=30, when="h", backupCount=10, layout=PatternLayout("%m")
    )
    for i in range(10):
        app.doAppend(record(f"line-{i:02d}"))
    app.stop()
    backups = [p for p in glob.glob(str(path) + ".2*")]
    assert backups
    assert path.exists()


def test_size_and_time_unique_names(tmp_path):
    path = tmp_path / "app.log"
    app = SizeAndTimeBasedAppender(
        str(path), maxBytes=20, when="h", backupCount=10, layout=PatternLayout("%m")
    )
    for i in range(6):
        app.doAppend(record(f"line-{i:02d}"))
    app.stop()
    names = sorted(os.path.basename(p) for p in glob.glob(str(path) + ".2*"))
    assert len(names) == len(set(names))


def test_size_and_time_rolls_on_time(tmp_path):
    path = tmp_path / "app.log"
    app = SizeAndTimeBasedAppender(
        str(path), maxBytes=10_000, when="S", backupCount=10, layout=PatternLayout("%m")
    )
    app.doAppend(record("before"))
    app.rollover_at = time.time() - 1
    app.doAppend(record("after"))
    app.stop()
    assert path.read_text() == "after\n"
    assert glob.glob(str(path) + ".2*")


def test_size_and_time_invalid_max_bytes(tmp_path):
    with pytest.raises(ValueError):
        SizeAndTimeBasedAppender(str(tmp_path / "x.log"), maxBytes=0)


def test_size_and_time_compresses(tmp_path):
    path = tmp_path / "app.log"
    app = SizeAndTimeBasedAppender(
        str(path),
        maxBytes=20,
        when="h",
        backupCount=10,
        compress=True,
        layout=PatternLayout("%m"),
    )
    for i in range(6):
        app.doAppend(record(f"line-{i:02d}"))
    app.stop()
    assert glob.glob(str(path) + ".2*.gz")
