"""Network appenders: SocketAppender (TCP) and SyslogAppender (UDP).

Starts a local loopback listener so the example is self-contained.
"""

import socket
import threading

from log4p2 import Level, PatternLayout, SocketAppender, SyslogAppender, getLogger

# --- TCP listener --------------------------------------------------------------
tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcp.bind(("127.0.0.1", 0))
tcp.listen(1)
tcp_port = tcp.getsockname()[1]

received = []


def accept():
    conn, _ = tcp.accept()
    received.append(conn.recv(4096).decode())
    conn.close()


threading.Thread(target=accept, daemon=True).start()

tcp_logger = getLogger("demo.net")
tcp_logger.setLevel(Level.DEBUG)
tcp_logger.setAdditivity(False)
tcp_logger.addAppender(
    SocketAppender("127.0.0.1", tcp_port, layout=PatternLayout("%p %m"))
)
tcp_logger.info("shipped over tcp")

# --- UDP syslog listener -------------------------------------------------------
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.bind(("127.0.0.1", 0))
udp_port = udp.getsockname()[1]
udp.settimeout(2)

syslog_logger = getLogger("demo.syslog")
syslog_logger.setLevel(Level.DEBUG)
syslog_logger.setAdditivity(False)
syslog_logger.addAppender(
    SyslogAppender("127.0.0.1", udp_port, facility="LOCAL0", layout=PatternLayout("%m"))
)
syslog_logger.error("disk almost full")

data, _ = udp.recvfrom(4096)
print("tcp  ->", received[0].strip())
print("syslog->", data.decode())
