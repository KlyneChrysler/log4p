import smtplib

import pytest

from log4p2 import Level, LogRecord, PatternLayout, SMTPAppender


def record(message="hello", level=Level.INFO, name="app.db"):
    return LogRecord(name=name, level=level, message=message)


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.sent = []
        self.logged_in = None
        self.tls = False
        FakeSMTP.instances.append(self)

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, message):
        self.sent.append(message)

    def quit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


def test_smtp_does_not_send_below_trigger(fake_smtp):
    app = SMTPAppender("mail", 25, fromaddr="a@x", toaddrs=["b@x"])
    app.doAppend(record("info", Level.INFO))
    app.doAppend(record("warn", Level.WARN))
    assert fake_smtp.instances == []


def test_smtp_sends_on_error(fake_smtp):
    app = SMTPAppender(
        "mail", 25, fromaddr="a@x", toaddrs=["b@x", "c@x"], subject="alert"
    )
    app.doAppend(record("info one", Level.INFO))
    app.doAppend(record("boom", Level.ERROR))
    assert len(fake_smtp.instances) == 1
    message = fake_smtp.instances[0].sent[0]
    assert message["From"] == "a@x"
    assert message["To"] == "b@x, c@x"
    assert message["Subject"] == "alert"
    body = message.get_content()
    assert "info one" in body
    assert "boom" in body


def test_smtp_buffer_is_bounded(fake_smtp):
    app = SMTPAppender("mail", 25, fromaddr="a@x", toaddrs=["b@x"], bufferSize=2)
    app.doAppend(record("one", Level.INFO))
    app.doAppend(record("two", Level.INFO))
    app.doAppend(record("three", Level.INFO))
    app.doAppend(record("boom", Level.ERROR))
    body = fake_smtp.instances[0].sent[0].get_content()
    assert "one" not in body
    assert "two" not in body
    assert "three" in body
    assert "boom" in body


def test_smtp_subject_is_a_pattern(fake_smtp):
    app = SMTPAppender(
        "mail",
        25,
        fromaddr="a@x",
        toaddrs=["b@x"],
        subject="%p on %c",
        layout=PatternLayout("%m"),
    )
    app.doAppend(record("kaboom", Level.ERROR, name="svc.auth"))
    assert fake_smtp.instances[0].sent[0]["Subject"] == "ERROR on svc.auth"


def test_smtp_starttls_and_login(fake_smtp):
    app = SMTPAppender(
        "mail",
        25,
        fromaddr="a@x",
        toaddrs=["b@x"],
        starttls=True,
        username="u",
        password="p",
    )
    app.doAppend(record("boom", Level.ERROR))
    server = fake_smtp.instances[0]
    assert server.tls is True
    assert server.logged_in == ("u", "p")


def test_smtp_ssl_uses_smtp_ssl(fake_smtp):
    app = SMTPAppender("mail", 465, fromaddr="a@x", toaddrs=["b@x"], ssl=True)
    app.doAppend(record("boom", Level.ERROR))
    assert len(fake_smtp.instances) == 1


def test_smtp_invalid_buffer_size():
    with pytest.raises(ValueError):
        SMTPAppender("mail", 25, bufferSize=0)


def test_smtp_flush_clears_buffer(fake_smtp):
    app = SMTPAppender("mail", 25, fromaddr="a@x", toaddrs=["b@x"])
    app.doAppend(record("one", Level.INFO))
    app.flush()
    app.doAppend(record("boom", Level.ERROR))
    body = fake_smtp.instances[0].sent[0].get_content()
    assert "one" not in body
    assert "boom" in body
