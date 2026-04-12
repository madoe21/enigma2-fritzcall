# -*- coding: utf-8 -*-
"""
Enigma2 plugin entry point for FritzCall.

AppContext wires together the platform-neutral modules (api, store, monitor)
with the Enigma2 services.  A single global instance is created at autostart
and reused for the lifetime of the session.
"""
from __future__ import absolute_import

import os

from Components.config import (
    ConfigInteger,
    ConfigSelection,
    ConfigSubsection,
    ConfigText,
    config,
)
from Plugins.Plugin import PluginDescriptor

from . import _
from .api import FritzBoxClient
from .config_store import FritzCallStore
from .screens import CallHistoryScreen, SettingsScreen
from .services import (
    CallMonitorService,
    EventDispatcher,
    LcdEventService,
    PhonebookRefreshService,
    UiEventService,
)

SETTINGS_FILE = "/etc/enigma2/settings"

# ---------------------------------------------------------------------------
# ConfigPassword – displays asterisks instead of clear text
# ---------------------------------------------------------------------------

class ConfigPassword(ConfigText):
    def getText(self):
        return u"*" * len(self.value) if self.value else u""

    def getMulti(self, selected):
        mtext = u"*" * len(self.value) if self.value else u""
        if selected:
            return ("mtext", mtext + u"_")
        return ("mtext", mtext)


# ---------------------------------------------------------------------------
# Enigma2 config entries  (persisted in /etc/enigma2/settings)
# ---------------------------------------------------------------------------

if not hasattr(config.plugins, "fritzcall"):
    config.plugins.fritzcall = ConfigSubsection()

config.plugins.fritzcall.host = ConfigText(default="fritz.box", fixed_size=False)
config.plugins.fritzcall.username = ConfigText(default="", fixed_size=False)
config.plugins.fritzcall.password = ConfigPassword(default="", fixed_size=False)
config.plugins.fritzcall.output_target = ConfigSelection(
    default="both",
    choices=[("ui", _("UI only")), ("lcd", _("LCD only")), ("both", _("UI + LCD"))],
)
config.plugins.fritzcall.message_timeout_sec = ConfigSelection(
    default="8",
    choices=[("4", "4s"), ("6", "6s"), ("8", "8s"), ("10", "10s"), ("15", "15s"), ("20", "20s")],
)
config.plugins.fritzcall.phonebook_refresh_min = ConfigInteger(default=60, limits=(5, 1440))


_APP = None


class AppContext(object):
    """Container for all long-lived service objects."""

    def __init__(self, session):
        self.session = session
        self._load_settings_from_file()
        self.store = FritzCallStore()

        self.api = FritzBoxClient(
            host=self.get_host(),
            username=self.get_username(),
            password=self.get_password(),
        )

        self.ui_service = UiEventService(session)
        self.lcd_service = LcdEventService()
        self.dispatcher = EventDispatcher(self.ui_service, self.lcd_service, self)

        self.call_monitor = CallMonitorService(self, self.dispatcher)
        self.call_monitor.attach_api(self.api)

        self.phonebook_refresh = PhonebookRefreshService(self.api, self)

    # ------------------------------------------------------------------
    # Settings helpers
    # ------------------------------------------------------------------

    def _load_settings_from_file(self):
        """Read persisted Enigma2 settings so values are available on first
        launch before the config system has fully initialised."""
        if not os.path.exists(SETTINGS_FILE):
            return
        values = {}
        try:
            with open(SETTINGS_FILE, "r") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or not line.startswith("config.plugins.fritzcall."):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    values[key] = value.strip()
        except Exception:
            return

        host = values.get("config.plugins.fritzcall.host")
        username = values.get("config.plugins.fritzcall.username")
        password = values.get("config.plugins.fritzcall.password")
        output_target = values.get("config.plugins.fritzcall.output_target")
        timeout = values.get("config.plugins.fritzcall.message_timeout_sec")
        refresh = values.get("config.plugins.fritzcall.phonebook_refresh_min")

        if host:
            config.plugins.fritzcall.host.value = host
        if username is not None:
            config.plugins.fritzcall.username.value = username
        if password is not None:
            config.plugins.fritzcall.password.value = password
        if output_target:
            config.plugins.fritzcall.output_target.value = output_target
        if timeout:
            config.plugins.fritzcall.message_timeout_sec.value = timeout
        if refresh:
            try:
                config.plugins.fritzcall.phonebook_refresh_min.value = int(refresh)
            except Exception:
                pass

    def get_host(self):
        return (config.plugins.fritzcall.host.value or "fritz.box").strip()

    def get_username(self):
        return (config.plugins.fritzcall.username.value or "").strip()

    def get_password(self):
        return (config.plugins.fritzcall.password.value or "").strip()

    def settings_complete(self):
        return bool(self.get_host())

    def get_settings(self):
        """Return settings as a dict for backwards compatibility with services."""
        return {
            "host": self.get_host(),
            "username": self.get_username(),
            "password": self.get_password(),
            "output_target": config.plugins.fritzcall.output_target.value or "both",
            "message_timeout_sec": int(config.plugins.fritzcall.message_timeout_sec.value or 8),
            "phonebook_refresh_min": int(config.plugins.fritzcall.phonebook_refresh_min.value or 60),
        }

    def start(self):
        self.call_monitor.start()
        self.phonebook_refresh.start()

    def stop(self):
        self.call_monitor.stop()
        self.phonebook_refresh.stop()

    def apply_settings(self):
        """Apply changed settings to running services (called from SettingsScreen)."""
        self.api.host = self.get_host()
        self.api.username = self.get_username()
        self.api.password = self.get_password()
        self.api._sid = None  # force re-login with new credentials
        self.api._phonebook_cache = {}
        # Restart call monitor so it reconnects to the (potentially new) host
        self.call_monitor.stop()
        self.call_monitor.start()


# ---------------------------------------------------------------------------
# Global instance management
# ---------------------------------------------------------------------------

def get_app(session):
    global _APP
    if _APP is None:
        _APP = AppContext(session)
        _APP.start()
    else:
        # Re-attach the current session to UI service (e.g. after standby)
        _APP.session = session
        _APP.ui_service.session = session
    return _APP


def autostart(reason, **kwargs):
    global _APP
    if reason == 0:
        session = kwargs.get("session")
        if session:
            get_app(session)
    elif reason == 1 and _APP is not None:
        _APP.stop()
        _APP = None


def main(session, **kwargs):
    app = get_app(session)
    if app.settings_complete():
        session.open(CallHistoryScreen, app)
    else:
        session.open(SettingsScreen, app, True)


def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="FritzCall",
            description=_("FritzCall – Anrufer-Benachrichtigung & Anrufliste"),
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="plugin.png",
            fnc=main,
        ),
        PluginDescriptor(
            where=PluginDescriptor.WHERE_AUTOSTART,
            fnc=autostart,
        ),
    ]
