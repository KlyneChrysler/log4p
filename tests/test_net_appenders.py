import socket
import threading
import time

import pytest

from log4p import (
    Level,
    LogRecord,
    PatternLayout,
    SocketAppender,
    SyslogAppender,
)


def record(message="hello", level=Level.INFO, name="app.db"):
    return LogRecord(name=name, level=level, message=message)


def _tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    return server, server.getsockname()[1]


def test_socket_appender_sends_text():
    server, port = _tcp_server()
    received = []

    def accept():
        conn, _ = server.accept()
        received.append(conn.recv(4096))
        conn.close()

    thread = threading.Thread(target=accept)
    thread.start()
    app = SocketAppender("127.0.0.1", port, layout=PatternLayout("%m"))
    app.doAppend(record("over the wire"))
    app.stop()
    thread.join(timeout=2)
    server.close()
    assert received and received[0] == b"over the wire\n"


def test_socket_appender_reconnects_after_failure():
    app = SocketAppender("127.0.0.1", 1, reconnectDelay=100.0, layout=PatternLayout("%m"))
    # First append attempts a connection, which fails (no listener on port 1).
    with pytest.raises(Exception):
        app.append(record("x"))
    assert app._socket is None


def test_socket_appender_start_swallows_connection_error():
    app = SocketAppender("127.0.0.1", 1, layout=PatternLayout("%m"))
    app.start()  # must not raise
    assert app.isStarted()
    assert app._socket is None
    app.stop()


def _udp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    return server, server.getsockname()[1]


def test_syslog_appender_udp_format():
    server, port = _udp_server()
    app = SyslogAppender("127.0.0.1", port, facility="LOCAL0", layout=PatternLayout("%m"))
    app.doAppend(record("disk full", level=Level.ERROR))
    data, _ = server.recvfrom(4096)
    server.close()
    app.stop()
    text = data.decode()
    # LOCAL0(16)*8 + ERROR(3) = 131
    assert text.startswith("<131>")
    assert "app.db: disk full" in text


def test_syslog_rfc5424_udp_format():
    server, port = _udp_server()
    app = SyslogAppender(
        "127.0.0.1",
        port,
        facility="LOCAL0",
        rfc5424=True,
        appName="websvc",
        msgId="ID47",
        layout=PatternLayout("%m"),
    )
    app.doAppend(record("disk full", level=Level.ERROR))
    data, _ = server.recvfrom(4096)
    server.close()
    app.stop()
    text = data.decode()
    assert text.startswith("<131>1 ")
    assert " websvc " in text
    assert " ID47 - disk full" in text
    # RFC 5424 timestamp looks like 2026-10-11T12:00:00.123+00:00
    assert "T" in text and "." in text


def test_syslog_rfc5424_defaults_use_process_and_logger():
    app = SyslogAppender("127.0.0.1", 1, rfc5424=True)
    rec = record("hi", level=Level.INFO)
    line = app._format_line(rec)
    assert rec.name in line
    assert str(rec.process) in line
    assert " - hi" in line


def test_syslog_severity_mapping():
    app = SyslogAppender("127.0.0.1", 1)
    assert app._severity(record(level=Level.FATAL)) == 2
    assert app._severity(record(level=Level.ERROR)) == 3
    assert app._severity(record(level=Level.WARN)) == 4
    assert app._severity(record(level=Level.INFO)) == 6
    assert app._severity(record(level=Level.DEBUG)) == 7


def test_syslog_invalid_facility():
    with pytest.raises(ValueError):
        SyslogAppender("127.0.0.1", 1, facility="NOPE")


def test_syslog_invalid_socktype():
    with pytest.raises(ValueError):
        SyslogAppender("127.0.0.1", 1, socktype="RAW")


def test_syslog_tcp_sends_line():
    server, port = _tcp_server()
    received = []

    def accept():
        conn, _ = server.accept()
        received.append(conn.recv(4096))
        conn.close()

    thread = threading.Thread(target=accept)
    thread.start()
    app = SyslogAppender("127.0.0.1", port, socktype="TCP", layout=PatternLayout("%m"))
    deadline = time.time() + 2
    while time.time() < deadline:
        try:
            app.doAppend(record("tcp syslog"))
            break
        except Exception:
            time.sleep(0.02)
    app.stop()
    thread.join(timeout=2)
    server.close()
    assert received and b"tcp syslog" in received[0]
