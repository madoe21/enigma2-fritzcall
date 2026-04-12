# -*- coding: utf-8 -*-
"""
Enigma2-specific runtime services.

This is the ONLY module with Enigma2 imports.  For a Kodi port, replace
this file with a Kodi-specific implementation that exposes the same
public interfaces (UiEventService, LcdEventService, CallMonitorService,
PhonebookRefreshService).
"""
from __future__ import absolute_import

from enigma import eTimer

try:
    from enigma import evfd
except Exception:
    evfd = None

try:
    from enigma import eDBoxLCD
except Exception:
    eDBoxLCD = None

from Screens.MessageBox import MessageBox
from Tools import Notifications

from .call_monitor import CallMonitorClient
from .core import MONITOR_CALL, MONITOR_RING, format_call_notification


def _timer_connect(timer, callback):
    """Connect a timer timeout signal – handles both API styles."""
    try:
        timer.timeout.connect(callback)
    except Exception:
        timer.callback.append(callback)


# ---------------------------------------------------------------------------
# UI notification service
# ---------------------------------------------------------------------------

class UiEventService(object):
    def __init__(self, session):
        self.session = session

    def show(self, text, timeout_sec):
        Notifications.AddPopup(
            text,
            MessageBox.TYPE_INFO,
            timeout=int(timeout_sec),
            id="FritzCallNotification",
        )


# ---------------------------------------------------------------------------
# LCD service
# ---------------------------------------------------------------------------

class LcdEventService(object):
    def __init__(self):
        self._restore_timer = eTimer()
        _timer_connect(self._restore_timer, self._restore)

    def _write(self, text):
        if evfd is not None:
            try:
                evfd.getInstance().vfd_write_string(text)
                return
            except Exception:
                pass
        if eDBoxLCD is not None:
            try:
                eDBoxLCD.getInstance().setText(text)
            except Exception:
                pass

    def show(self, text, timeout_sec):
        short = text.replace("\n", " | ")[:60]
        self._write(short)
        self._restore_timer.start(int(timeout_sec) * 1000, True)

    def _restore(self):
        self._write("")


# ---------------------------------------------------------------------------
# Event dispatcher  (routes to UI / LCD / both)
# ---------------------------------------------------------------------------

class EventDispatcher(object):
    def __init__(self, ui_service, lcd_service, app):
        self.ui_service = ui_service
        self.lcd_service = lcd_service
        self._app = app

    def dispatch(self, text):
        settings = self._app.get_settings()
        target = settings.get("output_target", "both")
        timeout = int(settings.get("message_timeout_sec", 8))
        if target in ("ui", "both"):
            self.ui_service.show(text, timeout)
        if target in ("lcd", "both"):
            self.lcd_service.show(text, timeout)


# ---------------------------------------------------------------------------
# Call-monitor service  (non-blocking socket + eTimer)
# ---------------------------------------------------------------------------

class CallMonitorService(object):
    """Drives the platform-neutral CallMonitorClient from an Enigma2 eTimer.

    Poll interval : 500 ms  (fast enough for real-time feel)
    Reconnect delay: 30 s   (after connection drop / error)
    """

    _POLL_MS = 500
    _RECONNECT_MS = 30000

    def __init__(self, app, dispatcher):
        self._app = app
        self._dispatcher = dispatcher
        self._client = None

        self._poll_timer = eTimer()
        self._reconnect_timer = eTimer()
        _timer_connect(self._poll_timer, self._poll)
        _timer_connect(self._reconnect_timer, self._connect)

        # active call tracking: call_id → event (for RING events)
        self._active_calls = {}
        self._api = None

    def start(self):
        self._connect()

    def stop(self):
        self._poll_timer.stop()
        self._reconnect_timer.stop()
        if self._client is not None:
            self._client.disconnect()
            self._client = None

    def is_connected(self):
        return self._client is not None and self._client.connected

    def _connect(self):
        self._poll_timer.stop()
        if self._client is not None:
            self._client.disconnect()

        settings = self._app.get_settings()
        host = settings.get("host", "fritz.box")
        self._client = CallMonitorClient(host)
        ok = self._client.connect()
        if ok:
            self._poll_timer.start(self._POLL_MS, False)  # repeating
        else:
            self._schedule_reconnect()

    def _poll(self):
        if self._client is None:
            self._poll_timer.stop()
            return

        if not self._client.connected:
            self._poll_timer.stop()
            self._schedule_reconnect()
            return

        events = self._client.poll()
        for event in events:
            self._handle_event(event)

        if not self._client.connected:
            self._poll_timer.stop()
            self._schedule_reconnect()

    def _handle_event(self, event):
        ev_type = event.get("type", "")
        call_id = event.get("call_id", "")

        if ev_type == MONITOR_RING:
            # Incoming call – resolve name and notify
            number = event.get("caller", "")
            name = self._resolve(number)
            text = format_call_notification(event, name)
            self._active_calls[call_id] = event
            if text:
                self._dispatcher.dispatch(text)

        elif ev_type == MONITOR_CALL:
            # Outgoing call – just track it (no mandatory notification)
            self._active_calls[call_id] = event

        elif ev_type == "DISCONNECT":
            self._active_calls.pop(call_id, None)

    def _resolve(self, number):
        """Resolve a number via the API's cached phonebook if available."""
        try:
            # app context attaches .api – only available after full init
            if hasattr(self, "_api") and self._api is not None:
                return self._api.resolve_number(number)
        except Exception:
            pass
        return number

    def attach_api(self, api):
        """Called by AppContext after the FritzBoxClient is ready."""
        self._api = api

    def _schedule_reconnect(self):
        self._reconnect_timer.start(self._RECONNECT_MS, True)


# ---------------------------------------------------------------------------
# Phonebook refresh service  (periodic background fetch)
# ---------------------------------------------------------------------------

class PhonebookRefreshService(object):
    """Periodically refreshes the phonebook cache in the FritzBoxClient.

    Runs a first refresh shortly after startup, then repeats on the
    interval configured in settings (phonebook_refresh_min).
    """

    _INITIAL_DELAY_MS = 5000  # 5 s after start

    def __init__(self, api, app):
        self._api = api
        self._app = app
        self._timer = eTimer()
        _timer_connect(self._timer, self._refresh)

    def start(self):
        self._timer.start(self._INITIAL_DELAY_MS, True)

    def stop(self):
        self._timer.stop()

    def _refresh(self):
        try:
            self._api.refresh_phonebook()
        except Exception:
            pass
        settings = self._app.get_settings()
        interval_min = int(settings.get("phonebook_refresh_min", 60))
        self._timer.start(interval_min * 60 * 1000, True)
