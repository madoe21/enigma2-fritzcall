# -*- coding: utf-8 -*-
"""
Platform-neutral FritzBox call-monitor TCP client (port 1012).

The FritzBox broadcasts call events on TCP port 1012.  You must first
enable the call monitor on the Fritz!Box by dialling  #96*5*  from any
connected phone (dial #96*4* to disable again).

Line format
-----------
  RING:        DD.MM.YY HH:MM:SS;RING;ConnID;CallerNr;CalledNr;SIP;
  CALL:        DD.MM.YY HH:MM:SS;CALL;ConnID;Extension;CalledNr;SIP;
  CONNECT:     DD.MM.YY HH:MM:SS;CONNECT;ConnID;Extension;Number;
  DISCONNECT:  DD.MM.YY HH:MM:SS;DISCONNECT;ConnID;Duration;

This class has NO Enigma2 / Kodi imports.  The Enigma2 wrapper in services.py
drives it via an eTimer.
"""
from __future__ import absolute_import

import errno
import socket

from .core import parse_call_monitor_event

CALL_MONITOR_PORT = 1012
_RECV_SIZE = 4096


class CallMonitorClient(object):
    """Non-blocking TCP socket wrapper for the FritzBox call monitor.

    Usage (pseudo-code for any platform):
        client = CallMonitorClient("fritz.box")
        client.connect()
        # in a periodic callback:
        for event in client.poll():
            handle(event)
        # on shutdown:
        client.disconnect()
    """

    def __init__(self, host="fritz.box", port=CALL_MONITOR_PORT):
        self.host = host
        self.port = port
        self._sock = None
        self._buf = ""
        self.connected = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self):
        """Open a non-blocking TCP connection to the call monitor port.

        Returns True on success, False on failure.
        The socket may not be fully connected yet when using *connect_ex*
        in non-blocking mode; subsequent poll() calls will handle that.
        """
        self.disconnect()
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self._sock.setblocking(False)
            err = self._sock.connect_ex((self.host, self.port))
            # EINPROGRESS / EWOULDBLOCK is expected for non-blocking connect
            if err not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK,
                           errno.EAGAIN, 10035):  # 10035 = WSAEWOULDBLOCK
                self._sock.close()
                self._sock = None
                return False
            self.connected = True
            self._buf = ""
            return True
        except Exception:
            self._sock = None
            self.connected = False
            return False

    def disconnect(self):
        """Close the socket and reset state."""
        self.connected = False
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._buf = ""

    # ------------------------------------------------------------------
    # Non-blocking read
    # ------------------------------------------------------------------

    def poll(self):
        """Read any available data and return a list of parsed event dicts.

        Call this periodically (e.g. every 500 ms) from a timer.
        Returns an empty list if no full event lines arrived.
        Sets self.connected = False if the remote end closed the connection.
        """
        if self._sock is None:
            return []

        events = []
        try:
            data = self._sock.recv(_RECV_SIZE)
            if not data:
                # Connection closed by remote end
                self.connected = False
                return events
            try:
                self._buf += data.decode("latin-1")
            except Exception:
                self._buf += data.decode("utf-8", errors="replace")

        except socket.error as exc:
            if exc.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK, 10035):
                # No data right now – that is perfectly normal
                return events
            # Real error: mark as disconnected
            self.connected = False
            return events

        # Extract complete lines
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if line:
                event = parse_call_monitor_event(line)
                if event:
                    events.append(event)

        return events
