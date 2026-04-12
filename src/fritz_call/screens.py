# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os

from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Components.config import config, configfile, getConfigListEntry
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.Directories import SCOPE_PLUGINS, resolveFilename

try:
    from enigma import (
        RT_HALIGN_LEFT,
        RT_HALIGN_RIGHT,
        RT_VALIGN_CENTER,
        eListboxPythonMultiContent,
        gFont,
    )
except Exception:
    RT_HALIGN_LEFT = 0
    RT_HALIGN_RIGHT = 0
    RT_VALIGN_CENTER = 0
    eListboxPythonMultiContent = None
    gFont = None

try:
    from Components.Input import Input
    from Screens.InputBox import InputBox
except Exception:
    Input = None
    InputBox = None

from . import _
from .core import (
    CALL_TYPE_INCOMING,
    CALL_TYPE_MISSED,
    CALL_TYPE_OUTGOING,
    FILTER_ALL,
    FILTER_INCOMING,
    FILTER_MISSED,
    FILTER_OUTGOING,
    FILTER_REJECTED,
    _REJECTED_TYPES,
    filter_calls,
    format_call_type_label,
)

SUPPORT_LINE = "Support this plugin: https://buymeacoffee.com/madoe21"

# ---------------------------------------------------------------------------
# Column layout constants (pixels, relative to list widget left edge)
# ---------------------------------------------------------------------------
_COL_ICON_X = 0
_COL_ICON_W = 36
_COL_DATE_X = 40
_COL_DATE_W = 150
_COL_NAME_X = 194
_COL_NAME_W = 260
_COL_REGION_X = 458
_COL_REGION_W = 180
_COL_DEVICE_X = 642
_COL_DEVICE_W = 160
_COL_OWN_X = 806
_COL_OWN_W = 170
_COL_DUR_X = 980
_COL_DUR_W = 100
_ROW_H = 30

# Colours
_COL_IN = 0x00CC44       # green – incoming answered
_COL_OUT = 0x4499FF      # blue – outgoing
_COL_MISSED = 0xFF4444   # red – missed
_COL_REJECTED = 0xFF8800 # orange – rejected
_COL_TEXT = 0xCCCCCC      # default text
_COL_DIM = 0x888888       # dimmed text


def _type_color(call_type):
    if call_type == CALL_TYPE_INCOMING:
        return _COL_IN
    elif call_type == CALL_TYPE_OUTGOING:
        return _COL_OUT
    elif call_type == CALL_TYPE_MISSED:
        return _COL_MISSED
    elif call_type in _REJECTED_TYPES:
        return _COL_REJECTED
    return _COL_TEXT


# ---------------------------------------------------------------------------
# Call history screen  (main entry point, tab-style filtering)
# ---------------------------------------------------------------------------

class CallHistoryScreen(Screen):
    """Main screen – shows the call list with columns, cycled via LEFT/RIGHT.
    Settings and Info are accessible via colour buttons only."""

    skin = """
        <screen name="CallHistoryScreen" position="center,60" size="1200,660" title="FritzCall">
            <widget source="title" render="Label"
                    position="20,10" size="1160,35" font="Regular;30" />
            <widget name="hint" position="20,50" size="1160,26" font="Regular;20" />
            <widget name="hdr_icon"   position="20,80"  size="36,26"  font="Regular;18" />
            <widget name="hdr_date"   position="60,80"  size="150,26" font="Regular;18" />
            <widget name="hdr_name"   position="214,80" size="260,26" font="Regular;18" />
            <widget name="hdr_region" position="478,80" size="180,26" font="Regular;18" />
            <widget name="hdr_device" position="662,80" size="160,26" font="Regular;18" />
            <widget name="hdr_own"    position="826,80" size="170,26" font="Regular;18" />
            <widget name="hdr_dur"    position="1000,80" size="100,26" font="Regular;18" halign="right" />
            <widget name="list" position="20,108" size="1160,450" scrollbarMode="showOnDemand" />
            <widget source="support" render="Label"
                    position="20,566" size="1160,24" font="Regular;18"
                    foregroundColor="#666666" />
            <ePixmap pixmap="skin_default/buttons/red.png"
                     position="20,596" size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"
                     position="260,596" size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png"
                     position="500,596" size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/blue.png"
                     position="740,596" size="220,30" alphatest="on" />
            <widget source="key_red" render="Label"
                    position="20,596" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
            <widget source="key_green" render="Label"
                    position="260,596" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
            <widget source="key_yellow" render="Label"
                    position="500,596" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
            <widget source="key_blue" render="Label"
                    position="740,596" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
        </screen>"""

    _FILTERS = [FILTER_ALL, FILTER_OUTGOING, FILTER_INCOMING, FILTER_MISSED, FILTER_REJECTED]
    _FILTER_LABELS = [
        (FILTER_ALL,      "Alle"),
        (FILTER_OUTGOING, "Ausgehend"),
        (FILTER_INCOMING, "Ankommend"),
        (FILTER_MISSED,   "Verpasst"),
        (FILTER_REJECTED, "Abgewiesen"),
    ]

    def __init__(self, session, app):
        Screen.__init__(self, session)
        self.app = app
        self._all_calls = []
        self._filtered = []
        self._tab_index = 0
        self._use_multicontent = eListboxPythonMultiContent is not None

        self["title"] = StaticText(_("FritzCall"))
        self["hint"] = Label("")

        # Column headers
        self["hdr_icon"] = Label("")
        self["hdr_date"] = Label(_("Datum"))
        self["hdr_name"] = Label(_("Name / Rufnummer"))
        self["hdr_region"] = Label(_("Ortsnetz"))
        self["hdr_device"] = Label(_("Telefoniegerät"))  # Nebenstelle
        self["hdr_own"] = Label(_("Eigene Rufnr."))
        self["hdr_dur"] = Label(_("Dauer"))

        if self._use_multicontent:
            self["list"] = MenuList([], content=eListboxPythonMultiContent)
        else:
            self["list"] = MenuList([])

        if gFont is not None:
            try:
                self["list"].l.setFont(0, gFont("Regular", 20))
                self["list"].l.setItemHeight(_ROW_H)
            except Exception:
                pass

        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Close"))
        self["key_green"] = StaticText(_("Refresh"))
        self["key_yellow"] = StaticText(_("Settings"))
        self["key_blue"] = StaticText(_("Information"))

        self["actions"] = ActionMap(
            ["ColorActions", "OkCancelActions", "DirectionActions"],
            {
                "ok": self.key_ok,
                "cancel": self.close,
                "red": self.close,
                "green": self._load,
                "yellow": self.open_settings,
                "blue": self.open_info,
                "left": self.key_left,
                "right": self.key_right,
            },
            -1,
        )

        self.onShow.append(self._load)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load(self):
        try:
            calls = self.app.api.get_call_list()
            if calls:
                self.app.store.save_call_cache(calls)
                self._all_calls = calls
            else:
                self._all_calls = self.app.store.get_call_cache()
        except Exception:
            self._all_calls = self.app.store.get_call_cache()
        self._apply_tab()

    def _apply_tab(self):
        filter_type = self._FILTERS[self._tab_index]
        self._filtered = filter_calls(self._all_calls, filter_type)
        self._render()
        self._update_header()

    def _update_header(self):
        parts = []
        for i, (_ftype, label) in enumerate(self._FILTER_LABELS):
            if i == self._tab_index:
                parts.append("[ %s ]" % label)
            else:
                parts.append("  %s  " % label)
        self["hint"].setText("  ".join(parts))
        active_label = self._FILTER_LABELS[self._tab_index][1]
        self["title"].setText(_("FritzCall") + u" \u2013 " + active_label)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self):
        calls = self._filtered
        if not calls:
            if self._use_multicontent:
                self["list"].setList([self._empty_item(_("No calls available"))])
            else:
                self["list"].setList([_("No calls available")])
            return

        if self._use_multicontent:
            self["list"].setList([self._build_item(c) for c in calls])
        else:
            self["list"].setList([self._format_plain(c) for c in calls])

    def _empty_item(self, label):
        return [
            None,
            MultiContentEntryText(
                pos=(0, 0), size=(1160, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=label, color=_COL_DIM,
            ),
        ]

    def _build_item(self, call):
        call_type = call.get("type", 0)
        color = _type_color(call_type)
        icon = format_call_type_label(call_type)
        date = (call.get("date") or "-")[:18]
        name = call.get("name") or ""
        number = call.get("number") or ""
        name_display = name if name else number
        if name and number:
            name_display = u"%s (%s)" % (name, number)
        name_display = name_display[:30] or "-"
        region = (call.get("region") or "-")[:20]
        device = (call.get("extension") or "-")[:18]
        own = (call.get("own_number") or "-")[:18]
        duration = (call.get("duration") or "-")[:10]

        return [
            call,
            MultiContentEntryText(
                pos=(_COL_ICON_X, 0), size=(_COL_ICON_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=icon, color=color,
            ),
            MultiContentEntryText(
                pos=(_COL_DATE_X, 0), size=(_COL_DATE_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=date, color=_COL_TEXT,
            ),
            MultiContentEntryText(
                pos=(_COL_NAME_X, 0), size=(_COL_NAME_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=name_display, color=color,
            ),
            MultiContentEntryText(
                pos=(_COL_REGION_X, 0), size=(_COL_REGION_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=region, color=_COL_DIM,
            ),
            MultiContentEntryText(
                pos=(_COL_DEVICE_X, 0), size=(_COL_DEVICE_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=device, color=_COL_DIM,
            ),
            MultiContentEntryText(
                pos=(_COL_OWN_X, 0), size=(_COL_OWN_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=own, color=_COL_DIM,
            ),
            MultiContentEntryText(
                pos=(_COL_DUR_X, 0), size=(_COL_DUR_W, _ROW_H),
                font=0, flags=RT_HALIGN_RIGHT | RT_VALIGN_CENTER,
                text=duration, color=_COL_TEXT,
            ),
        ]

    def _format_plain(self, call):
        """Fallback for systems without MultiContent support."""
        call_type = call.get("type", 0)
        icon = format_call_type_label(call_type)
        date = (call.get("date") or "")[:16]
        display = call.get("display_name") or "?"
        duration = call.get("duration") or ""
        return u"%s %-16s %-22s %s" % (icon, date, display[:22], duration)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def key_left(self):
        self._tab_index = (self._tab_index - 1) % len(self._FILTERS)
        self._apply_tab()

    def key_right(self):
        self._tab_index = (self._tab_index + 1) % len(self._FILTERS)
        self._apply_tab()

    def key_ok(self):
        if not self._filtered:
            return
        try:
            index = int(self["list"].getSelectionIndex())
        except Exception:
            try:
                index = int(self["list"].getSelectedIndex())
            except Exception:
                index = 0
        if 0 <= index < len(self._filtered):
            self.session.open(CallDetailScreen, self._filtered[index])

    def open_settings(self):
        self.session.openWithCallback(
            lambda *_: self._load(),
            SettingsScreen,
            self.app,
            False,
        )

    def open_info(self):
        self.session.open(InfoScreen)


# ---------------------------------------------------------------------------
# Call detail screen
# ---------------------------------------------------------------------------

class CallDetailScreen(Screen):
    skin = """
        <screen name="CallDetailScreen" position="center,200" size="800,320"
                title="FritzCall – Detail">
            <widget source="title"  render="Label"
                    position="20,10"  size="760,35" font="Regular;28" />
            <widget name="body"     position="20,55"  size="760,210"
                    scrollbarMode="showOnDemand" />
            <ePixmap pixmap="skin_default/buttons/red.png"
                     position="20,275" size="220,30" alphatest="on" />
            <widget source="key_red" render="Label"
                    position="20,275" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
        </screen>"""

    def __init__(self, session, call):
        Screen.__init__(self, session)
        self["title"] = StaticText(call.get("display_name", "?"))
        self["key_red"] = StaticText(_("Close"))

        _TYPE_MAP = {
            1: _("Ankommend"),
            2: _("Verpasst"),
            3: _("Ausgehend"),
            9: _("Abgewiesen"),
            10: _("Abgewiesen"),
            11: _("Blockiert"),
        }
        call_type = _TYPE_MAP.get(call.get("type", 0), "?")
        lines = [
            "%s:  %s" % (_("Datum"), call.get("date", "?")),
            "%s:  %s" % (_("Name"), call.get("name") or "-"),
            "%s:  %s" % (_("Rufnummer"), call.get("number", "?")),
            "%s:  %s" % (_("Ortsnetz"), call.get("region") or "-"),
            "%s:  %s" % (_("Telefoniegerät"), call.get("extension") or "-"),  # Nebenstelle
            "%s:  %s" % (_("Eigene Rufnummer"), call.get("own_number", "?")),
            "%s:  %s" % (_("Dauer"), call.get("duration", "?")),
            "%s:  %s" % (_("Typ"), call_type),
        ]
        self["body"] = ScrollLabel("\n".join(lines))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {"cancel": self.close, "ok": self.close, "red": self.close},
            -1,
        )


# ---------------------------------------------------------------------------
# Settings screen  (ConfigListScreen-based)
# ---------------------------------------------------------------------------

class SettingsScreen(Screen, ConfigListScreen):
    """Settings screen using Enigma2 config system.

    String fields (host, username, password) are edited via InputBox on OK.
    Choice fields (output_target, message_timeout_sec) cycle with LEFT/RIGHT.
    """

    skin = """
        <screen name="FritzCallSettingsScreen" position="center,100" size="980,560"
                title="FritzCall Einstellungen">
            <widget source="title" render="Label" position="20,10" size="940,36" font="Regular;30" />
            <widget name="config" position="20,56" size="940,330" scrollbarMode="showOnDemand" />
            <widget source="hint" render="Label" position="20,396" size="940,60" font="Regular;20" />
            <widget source="support" render="Label" position="20,464" size="940,24"
                    font="Regular;18" foregroundColor="#666666" />
            <ePixmap pixmap="skin_default/buttons/red.png"
                     position="20,500" size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"
                     position="250,500" size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png"
                     position="480,500" size="220,30" alphatest="on" />
            <widget source="key_red" render="Label"
                    position="20,500" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
            <widget source="key_green" render="Label"
                    position="250,500" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
            <widget source="key_yellow" render="Label"
                    position="480,500" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
        </screen>"""

    _HELP = {
        "host": "Enter Fritz!Box hostname or IP address",
        "username": "Enter Fritz!Box username (leave empty if none)",
        "password": "Enter Fritz!Box password",
        "output_target": "Choose where notifications are displayed",
        "message_timeout_sec": "How long notifications stay visible",
    }

    def __init__(self, session, app, open_main_on_save):
        Screen.__init__(self, session)
        self.app = app
        self.open_main_on_save = bool(open_main_on_save)

        self["title"] = StaticText(_("Fritz!Box Settings"))
        self["hint"] = StaticText("")
        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Save"))
        self["key_yellow"] = StaticText(_("Test connection"))

        self._entries = [
            getConfigListEntry(_("Fritz!Box Host/IP"), config.plugins.fritzcall.host),
            getConfigListEntry(_("Username"), config.plugins.fritzcall.username),
            getConfigListEntry(_("Password"), config.plugins.fritzcall.password),
            getConfigListEntry(_("Output target"), config.plugins.fritzcall.output_target),
            getConfigListEntry(_("Message timeout"), config.plugins.fritzcall.message_timeout_sec),
        ]
        ConfigListScreen.__init__(self, self._entries, session=session)

        try:
            self["config"].onSelectionChanged.append(self._update_hint)
        except Exception:
            pass
        self._update_hint()

        self["actions"] = ActionMap(
            ["SetupActions", "ColorActions", "OkCancelActions", "WizardActions"],
            {
                "save": self.key_green,
                "cancel": self.key_red,
                "green": self.key_green,
                "red": self.key_red,
                "yellow": self.key_yellow,
                "ok": self.key_ok,
                "back": self.key_red,
            },
            -2,
        )

    # ------------------------------------------------------------------
    # Key handlers
    # ------------------------------------------------------------------

    def key_ok(self):
        if Input is None or InputBox is None:
            try:
                ConfigListScreen.keyOK(self)
            except Exception:
                pass
            return

        current = self["config"].getCurrent()
        if not current:
            return
        cfg_item = current[1]

        if cfg_item is config.plugins.fritzcall.host:
            self.session.openWithCallback(
                lambda v: self._on_text_input(v, config.plugins.fritzcall.host),
                InputBox, title=_("Fritz!Box Host/IP"),
                text=config.plugins.fritzcall.host.value or "",
                maxSize=64, type=Input.TEXT,
            )
        elif cfg_item is config.plugins.fritzcall.username:
            self.session.openWithCallback(
                lambda v: self._on_text_input(v, config.plugins.fritzcall.username),
                InputBox, title=_("Username"),
                text=config.plugins.fritzcall.username.value or "",
                maxSize=64, type=Input.TEXT,
            )
        elif cfg_item is config.plugins.fritzcall.password:
            self.session.openWithCallback(
                lambda v: self._on_text_input(v, config.plugins.fritzcall.password),
                InputBox, title=_("Password"),
                text=config.plugins.fritzcall.password.value or "",
                maxSize=64, type=Input.TEXT,
            )
        else:
            try:
                ConfigListScreen.keyOK(self)
            except Exception:
                pass

    def key_green(self):
        host = (config.plugins.fritzcall.host.value or "").strip()
        if not host:
            self.session.open(
                MessageBox,
                _("Please configure the Fritz!Box connection first"),
                MessageBox.TYPE_ERROR,
                timeout=5,
            )
            return

        for entry in self["config"].list:
            entry[1].save()
        config.plugins.fritzcall.save()
        try:
            configfile.save()
        except Exception:
            pass

        self.app.apply_settings()

        self.session.open(
            MessageBox, _("Settings saved"), MessageBox.TYPE_INFO, timeout=3
        )

        if self.open_main_on_save:
            self.session.open(CallHistoryScreen, self.app)
        self.close()

    def key_red(self):
        for entry in self["config"].list:
            try:
                entry[1].cancel()
            except Exception:
                pass
        self.close()

    def key_yellow(self):
        """Test the connection using current (unsaved) field values."""
        ok = self.app.api.test_connection()
        msg = _("Connection test successful") if ok else _("Connection test failed")
        self.session.open(MessageBox, msg, MessageBox.TYPE_INFO, timeout=4)

    # ------------------------------------------------------------------
    # Input callbacks
    # ------------------------------------------------------------------

    def _on_text_input(self, value, cfg_entry):
        if value is None:
            return
        cfg_entry.value = str(value).strip()

    # ------------------------------------------------------------------
    # Help text
    # ------------------------------------------------------------------

    def _update_hint(self):
        current = self["config"].getCurrent()
        if not current:
            return
        item = current[1]
        key = None
        if item is config.plugins.fritzcall.host:
            key = "host"
        elif item is config.plugins.fritzcall.username:
            key = "username"
        elif item is config.plugins.fritzcall.password:
            key = "password"
        elif item is config.plugins.fritzcall.output_target:
            key = "output_target"
        elif item is config.plugins.fritzcall.message_timeout_sec:
            key = "message_timeout_sec"
        if key:
            self["hint"].setText(_(self._HELP[key]))


# ---------------------------------------------------------------------------
# Info screen
# ---------------------------------------------------------------------------

class InfoScreen(Screen):
    skin = """
        <screen name="InfoScreen" position="center,90" size="1000,620"
                title="FritzCall Info">
            <widget source="title" render="Label"
                    position="20,10" size="960,35" font="Regular;30" />
            <widget name="body"    position="20,55" size="690,510"
                    scrollbarMode="showOnDemand" />
            <widget name="qr"      position="740,100" size="240,240"
                    alphatest="blend" />
            <widget source="support" render="Label"
                    position="20,555" size="960,24" font="Regular;18"
                    foregroundColor="#666666" />
            <ePixmap pixmap="skin_default/buttons/red.png"
                     position="20,580" size="220,30" alphatest="on" />
            <widget source="key_red" render="Label"
                    position="20,580" size="220,30" font="Regular;22"
                    halign="center" valign="center" transparent="1" />
        </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["title"] = StaticText(_("Information"))
        self["key_red"] = StaticText(_("Close"))
        self["support"] = StaticText(SUPPORT_LINE)
        self["body"] = ScrollLabel(self._info_text())
        self["qr"] = Pixmap()
        self.onLayoutFinish.append(self._load_qr)

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "ColorActions"],
            {
                "cancel": self.close,
                "ok": self.close,
                "red": self.close,
                "up": self["body"].pageUp,
                "down": self["body"].pageDown,
                "left": self["body"].pageUp,
                "right": self["body"].pageDown,
            },
            -1,
        )

    @staticmethod
    def _info_text():
        return "\n".join([
            "FritzCall Plugin",
            "",
            "Zeigt eingehende Anrufe als Benachrichtigung auf dem",
            "Bildschirm (UI) und/oder dem LCD-Display an.",
            "Namen werden aus dem FritzBox-Telefonbuch aufgelöst",
            "(Google-Sync, FRITZ!Box-Kontakte usw.).",
            "",
            "Anruf-Monitor aktivieren:",
            "  #96*5* auf einem FritzBox-Telefon wählen",
            "  (deaktivieren: #96*4*)",
            "",
            "Anrufliste:",
            "  Alle / Verpasst / Angenommen / Ausgehend",
            "",
            _("Controls") + ":",
            "  ROT/Exit = beenden",
            "  GRÜN     = Aktualisieren",
            "  GELB     = Einstellungen",
            "  BLAU     = Info",
            "  ◄/►      = Tabs (Alle / Verpasst / Angenommen / Ausgehend)",
            "  OK       = Detail-Ansicht",
            "",
            "Einstellungen:",
            "  OK       = Text eingeben",
            "  ◄/►      = Wert ändern",
            "  GRÜN     = Speichern",
            "  GELB     = Verbindungstest",
            "",
            "GitHub : https://github.com/madoe21/enigma2-fritzcall",
            "Support: https://buymeacoffee.com/madoe21",
        ])

    def _load_qr(self):
        candidates = [
            resolveFilename(SCOPE_PLUGINS, "Extensions/fritz_call/res/qr_buymeacoffee.png"),
            os.path.join(os.path.dirname(__file__), "res", "qr_buymeacoffee.png"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    self["qr"].instance.setPixmapFromFile(path)
                    return
                except Exception:
                    pass
