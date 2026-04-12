# -*- coding: utf-8 -*-
from __future__ import absolute_import

import gettext

from Components.Language import language
from Tools.Directories import SCOPE_PLUGINS, resolveFilename

PLUGIN_DOMAIN = "fritz_call"
PLUGIN_PATH = "Extensions/fritz_call/locale"

_DE_FALLBACK = {
    "FritzCall": "FritzCall",
    "Call History": "Anrufliste",
    "All Calls": "Alle Anrufe",
    "All": "Alle",
    "Missed": "Verpasst",
    "Answered": "Angenommen",
    "Outgoing": "Ausgehend",
    "Settings": "Einstellungen",
    "Information": "Informationen",
    "Back": "Zurück",
    "Save": "Speichern",
    "Exit": "Beenden",
    "Refresh": "Aktualisieren",
    "FritzBox Host": "FritzBox Host",
    "Username": "Benutzername",
    "Password": "Passwort",
    "Output target": "Ausgabeziel",
    "UI only": "Nur UI",
    "LCD only": "Nur LCD",
    "UI + LCD": "UI + LCD",
    "Message timeout (s)": "Meldungsdauer (s)",
    "Settings saved": "Einstellungen gespeichert",
    "No calls available": "Keine Anrufe verfügbar",
    "Incoming call": "Eingehender Anruf",
    "Outgoing call": "Ausgehender Anruf",
    "Missed call": "Verpasster Anruf",
    "Test connection": "Verbindung testen",
    "Connection test successful": "Verbindungstest erfolgreich",
    "Connection test failed": "Verbindungstest fehlgeschlagen",
    "Duration": "Dauer",
    "Caller": "Anrufer",
    "Number": "Nummer",
    "Date": "Datum",
    "Unknown": "Unbekannt",
    "Controls": "Steuerung",
    "Left/Right changes value": "Links/Rechts ändert den Wert",
    "Data source": "Datenquelle",
    "Thanks": "Dank",
    "Browse call history": "Anrufliste anzeigen",
    "RED=All GREEN=Missed YELLOW=Answered BLUE=Outgoing": "ROT=Alle GRÜN=Verpasst GELB=Angenommen BLAU=Ausgehend",
    "Call monitor active": "Anrufmonitor aktiv",
    "Call monitor inactive": "Anrufmonitor inaktiv",
    "Enable call monitor on FritzBox by dialing #96*5*": "Anrufmonitor an FritzBox aktivieren: #96*5* wählen",
    "Loading...": "Wird geladen...",
    "Error loading call list": "Fehler beim Laden der Anrufliste",
    "Phone": "Telefon",
    "Line": "Leitung",
}


def localeInit():
    gettext.bindtextdomain(
        PLUGIN_DOMAIN, resolveFilename(SCOPE_PLUGINS, PLUGIN_PATH)
    )


def _(txt):
    translated = gettext.dgettext(PLUGIN_DOMAIN, txt)
    if translated != txt:
        return translated
    try:
        lang = language.getLanguage()[:2]
    except Exception:
        lang = "en"
    if lang == "de":
        return _DE_FALLBACK.get(txt, txt)
    return txt


localeInit()
try:
    language.addCallback(localeInit)
except Exception:
    pass
