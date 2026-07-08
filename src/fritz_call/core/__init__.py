# -*- coding: utf-8 -*-
"""
Platform-neutral core: call data models, parsing, formatting.

This module has NO Enigma2 or Kodi imports and can be reused
unchanged in any Python runtime.
"""
from __future__ import absolute_import

# ---------------------------------------------------------------------------
# Call monitor event types (FritzBox TCP port 1012)
# ---------------------------------------------------------------------------
MONITOR_RING = "RING"          # Incoming call ringing
MONITOR_CALL = "CALL"          # Outgoing call initiated
MONITOR_CONNECT = "CONNECT"    # Call answered
MONITOR_DISCONNECT = "DISCONNECT"  # Call ended

# ---------------------------------------------------------------------------
# Call list entry types (from FritzBox call list CSV "Typ" column)
# ---------------------------------------------------------------------------
CALL_TYPE_INCOMING = 1    # Ankommend (answered incoming call)
CALL_TYPE_MISSED = 2      # Verpasst (missed incoming call)
CALL_TYPE_OUTGOING = 3    # Ausgehend (outgoing call)
CALL_TYPE_REJECTED_9 = 9  # Abgewiesen (active call deflection)
CALL_TYPE_REJECTED = 10   # Abgewiesen (rejected)
CALL_TYPE_BLOCKED = 11    # Abgewiesen (blocked)

_REJECTED_TYPES = (CALL_TYPE_REJECTED_9, CALL_TYPE_REJECTED, CALL_TYPE_BLOCKED)

# ---------------------------------------------------------------------------
# History filter constants
# ---------------------------------------------------------------------------
FILTER_ALL = "all"
FILTER_OUTGOING = "outgoing"
FILTER_INCOMING = "incoming"
FILTER_MISSED = "missed"
FILTER_REJECTED = "rejected"


def parse_call_monitor_event(line):
    """Parse one text line from FritzBox call-monitor port 1012.

    Protocol format (semicolon-separated):
      RING:       DD.MM.YY HH:MM:SS;RING;ConnID;CallerNr;CalledNr;SIP;
      CALL:       DD.MM.YY HH:MM:SS;CALL;ConnID;Extension;CalledNr;SIP;
      CONNECT:    DD.MM.YY HH:MM:SS;CONNECT;ConnID;Extension;Number;
      DISCONNECT: DD.MM.YY HH:MM:SS;DISCONNECT;ConnID;Duration;

    Returns a dict or None.
    """
    if not line:
        return None
    parts = line.split(";")
    if len(parts) < 4:
        return None

    timestamp = parts[0].strip()
    event_type = parts[1].strip().upper()
    call_id = parts[2].strip()

    result = {
        "timestamp": timestamp,
        "type": event_type,
        "call_id": call_id,
        "raw": line,
    }

    if event_type == MONITOR_RING and len(parts) >= 6:
        # RING: timestamp;RING;ConnID;CallerNr;CalledNr;SIP
        result["caller"] = parts[3].strip()
        result["called"] = parts[4].strip()
        result["line"] = parts[5].strip() if len(parts) > 5 else ""

    elif event_type == MONITOR_CALL and len(parts) >= 6:
        # CALL: timestamp;CALL;ConnID;Extension;CalledNr;SIP
        result["extension"] = parts[3].strip()
        result["callee"] = parts[4].strip()
        result["line"] = parts[5].strip()

    elif event_type == MONITOR_CONNECT and len(parts) >= 5:
        result["extension"] = parts[3].strip()
        result["number"] = parts[4].strip()

    elif event_type == MONITOR_DISCONNECT and len(parts) >= 4:
        result["duration"] = parts[3].strip()

    return result


def parse_call_list_csv(csv_text):
    """Parse the FritzBox call list CSV (supports both old and new firmware).

    Returns a list of raw dicts (column name → value).
    """
    calls = []
    if not csv_text:
        return calls

    lines = csv_text.splitlines()
    start = 0
    # Some firmware versions prepend "sep=;" line
    if lines and lines[0].startswith("sep="):
        start = 1

    header = None
    for line in lines[start:]:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if header is None:
            header = parts
            continue
        # Pad short rows
        if len(parts) < len(header):
            parts = parts + [""] * (len(header) - len(parts))
        entry = {header[i]: parts[i] for i in range(len(header))}
        calls.append(entry)

    return calls


def normalize_call(raw):
    """Normalize a raw CSV row dict to a standard call dict.

    Handles German (Typ/Datum/Rufnummer) and English (Type/Date/Number)
    column labels so the rest of the codebase works with one schema.
    """
    def _pick(*keys):
        for k in keys:
            v = raw.get(k, "").strip()
            if v:
                return v
        return ""

    type_str = _pick("Typ", "Type")
    try:
        call_type = int(type_str)
    except (ValueError, TypeError):
        call_type = 0

    name = _pick("Name")
    number = _pick("Rufnummer", "Number")
    own_number = _pick("Eigene Rufnummer", "Own Number")
    date = _pick("Datum", "Date")
    duration = _pick("Dauer", "Duration")
    extension = _pick("Nebenstelle", "Extension")
    region = _pick("Landes-/Ortsnetzbereich", "Region", "Ortsnetz")

    return {
        "type": call_type,
        "date": date,
        "name": name,
        "number": number,
        "own_number": own_number,
        "extension": extension,
        "duration": duration,
        "region": region,
        "display_name": name if name else (number if number else "Unknown"),
    }


def filter_calls(calls, filter_type):
    """Return a filtered subset of normalised call dicts."""
    if filter_type == FILTER_ALL:
        return calls
    elif filter_type == FILTER_OUTGOING:
        return [c for c in calls if c.get("type") == CALL_TYPE_OUTGOING]
    elif filter_type == FILTER_INCOMING:
        return [c for c in calls if c.get("type") == CALL_TYPE_INCOMING]
    elif filter_type == FILTER_MISSED:
        return [c for c in calls if c.get("type") == CALL_TYPE_MISSED]
    elif filter_type == FILTER_REJECTED:
        return [c for c in calls if c.get("type") in _REJECTED_TYPES]
    return calls


def format_call_type_label(call_type):
    if call_type == CALL_TYPE_INCOMING:
        return u"[\u2714]"    # [✔] angenommen
    elif call_type == CALL_TYPE_OUTGOING:
        return u"[\u2192]"    # [→] ausgehend
    elif call_type == CALL_TYPE_MISSED:
        return u"[\u2716]"    # [✖] verpasst
    elif call_type in _REJECTED_TYPES:
        return u"[\u2298]"    # [⊘] abgewiesen
    return u"[\u2013]"        # [–] unbekannt


def format_call_row(call):
    """One-line display string for a call list entry."""
    icon = format_call_type_label(call.get("type", 0))
    display = call.get("display_name", "?")
    date = call.get("date", "")
    duration = call.get("duration", "")
    if duration and duration not in ("0:00", "0:00:00", ""):
        return "%s %-20s  %s  %s" % (icon, display[:20], date, duration)
    return "%s %-20s  %s" % (icon, display[:20], date)


def format_call_notification(event, name=None):
    """Compose the popup/LCD text for a live call-monitor event."""
    ev_type = event.get("type", "")
    if ev_type == MONITOR_RING:
        number = event.get("caller", "?")
        display = name if name else number
        return "Incoming call:\n%s" % display
    elif ev_type == MONITOR_CALL:
        number = event.get("callee", "?")
        display = name if name else number
        return "Outgoing call:\n%s" % display
    return ""


def normalize_number(number):
    """Strip spaces/dashes for phonebook lookup."""
    if not number:
        return ""
    return "".join(c for c in number if c.isdigit() or c in ("+",))
